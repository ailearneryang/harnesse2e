"""External integration adapters for Claude Code CLI, Feishu, and Gerrit."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional


EventCallback = Callable[[Dict], None]


@dataclass
class AgentRunResult:
    success: bool
    output_text: str
    transcript: List[Dict] = field(default_factory=list)
    command: List[str] = field(default_factory=list)
    return_code: int = 0
    error: Optional[str] = None
    verdict: Optional[str] = None
    tokens_estimate: int = 0
    duration_seconds: float = 0.0


class ClaudeCLIAdapter:
    """Runs Claude Code CLI if available, otherwise falls back to simulation."""

    def __init__(self, settings: Dict):
        self.settings = settings

    def run_agent(
        self,
        agent_id: str,
        prompt: str,
        cwd: str,
        event_callback: Optional[EventCallback] = None,
        stage: Optional[str] = None,
    ) -> AgentRunResult:
        command_text = self.settings.get("command", "claude")
        simulate = self.settings.get("simulate", False)
        command_parts = shlex.split(command_text)
        binary = command_parts[0] if command_parts else "claude"

        if simulate or shutil.which(binary) is None:
            return self._simulate(agent_id, prompt, stage, event_callback)

        cli_command = list(command_parts)
        output_format = self.settings.get("output_format", "json")
        cli_command.extend([
            "-p",
            prompt,
            "--output-format",
            output_format,
        ])

        # stream-json requires --verbose in Claude Code CLI 2.x
        if output_format == "stream-json":
            cli_command.append("--verbose")

        # Use project-level agent definition if available
        if agent_id:
            cli_command.extend(["--agent", agent_id])

        # Auto-accept edits so non-interactive -p mode doesn't hang on permission prompts
        cli_command.extend(["--permission-mode", "auto"])

        model = self.settings.get("model")
        if model:
            cli_command.extend(["--model", model])

        max_turns = self.settings.get("max_turns")
        if max_turns:
            cli_command.extend(["--max-turns", str(max_turns)])

        start_time = datetime.now()
        transcript: List[Dict] = []
        output_lines: List[str] = []

        process = subprocess.Popen(
            cli_command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip("\n")
            if not line:
                continue
            event = self._parse_stream_line(line, agent_id, stage)
            transcript.append(event)
            if event_callback:
                event_callback(event)

            text_value = (event.get("text") or "").strip()
            # Only collect meaningful output, skip bare type labels and system/user noise
            if text_value and text_value not in ("system", "assistant", "user", "result"):
                output_lines.append(text_value)

        process.wait()
        duration = (datetime.now() - start_time).total_seconds()
        output_text = "\n".join(output_lines).strip()
        verdict = self._extract_verdict(output_text)

        if process.returncode != 0:
            # max_turns exceeded still produces useful output — treat as soft success
            is_max_turns = any(
                isinstance(e, dict) and e.get("payload", {}).get("subtype") == "error_max_turns"
                for e in transcript
            )
            soft_success = is_max_turns and bool(output_text)
            return AgentRunResult(
                success=soft_success,
                output_text=output_text,
                transcript=transcript,
                command=cli_command,
                return_code=process.returncode,
                error=None if soft_success else f"Claude CLI exited with code {process.returncode}",
                verdict=verdict,
                tokens_estimate=self._estimate_tokens(prompt, output_text),
                duration_seconds=duration,
            )

        return AgentRunResult(
            success=True,
            output_text=output_text,
            transcript=transcript,
            command=cli_command,
            return_code=process.returncode,
            verdict=verdict,
            tokens_estimate=self._estimate_tokens(prompt, output_text),
            duration_seconds=duration,
        )

    def _parse_stream_line(self, line: str, agent_id: str, stage: Optional[str]) -> Dict:
        try:
            payload = json.loads(line)
            event_type = payload.get("type", "json")
            text_value = ""

            if event_type == "result":
                # --output-format json returns final result here
                text_value = payload.get("result", "")
            elif event_type == "assistant":
                # stream-json: {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
                msg = payload.get("message") or {}
                content_blocks = msg.get("content") or []
                parts = []
                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                text_value = "\n".join(parts)
            else:
                text_value = payload.get("text") or payload.get("content") or ""

            if isinstance(text_value, list):
                text_value = "\n".join(str(item) for item in text_value)
            return {
                "type": event_type,
                "agent_id": agent_id,
                "stage": stage,
                "payload": payload,
                "message": text_value or event_type,
                "text": text_value,
            }
        except json.JSONDecodeError:
            return {
                "type": "stdout",
                "agent_id": agent_id,
                "stage": stage,
                "message": line,
                "text": line,
            }

    def _simulate(
        self,
        agent_id: str,
        prompt: str,
        stage: Optional[str],
        event_callback: Optional[EventCallback],
    ) -> AgentRunResult:
        template = self._simulation_output(agent_id, stage)
        transcript: List[Dict] = []
        for message in template["events"]:
            event = {
                "type": "simulation",
                "agent_id": agent_id,
                "stage": stage,
                "message": message,
                "text": message,
            }
            transcript.append(event)
            if event_callback:
                event_callback(event)
            time.sleep(0.8)  # visible delay for UI feedback

        output_text = template["output"]
        verdict = self._extract_verdict(output_text)
        return AgentRunResult(
            success=True,
            output_text=output_text,
            transcript=transcript,
            command=[self.settings.get("command", "claude"), "--simulate"],
            verdict=verdict,
            tokens_estimate=self._estimate_tokens(prompt, output_text),
            duration_seconds=1.0,
        )

    def _simulation_output(self, agent_id: str, stage: Optional[str]) -> Dict:
        stage_name = stage or agent_id
        if stage_name in {"code_review", "security_review", "testing"}:
            output = (
                f"{agent_id} completed checks for {stage_name}.\n"
                "Findings are within tolerance.\n"
                "VERDICT: PASS"
            )
        elif stage_name == "delivery":
            output = "Delivery stage prepared Gerrit submission metadata.\nVERDICT: PASS"
        else:
            output = (
                f"{agent_id} produced an artifact for {stage_name}.\n"
                "Key assumptions, risks, and next actions were captured for handoff.\n"
                "VERDICT: PASS"
            )
        return {
            "events": [
                f"{agent_id} accepted the task.",
                f"{agent_id} is working on {stage_name}.",
                f"{agent_id} finished {stage_name}.",
            ],
            "output": output,
        }

    def _extract_verdict(self, text: str) -> Optional[str]:
        upper = text.upper()
        if "VERDICT: PASS" in upper:
            return "PASS"
        if "VERDICT: FAIL" in upper:
            return "FAIL"
        if "VERDICT: NEED_HUMAN" in upper:
            return "NEED_HUMAN"
        return None

    def _estimate_tokens(self, prompt: str, output_text: str) -> int:
        return max(1, int((len(prompt) + len(output_text)) / 4))


class FeishuAdapter:
    """Minimal Feishu integration for inbound requests and outbound notifications."""

    def __init__(self, settings: Dict):
        self.settings = settings

    def extract_request(self, payload: Dict) -> Dict:
        event = payload.get("event", payload)
        message = event.get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = {"text": content}
        elif isinstance(content, dict):
            parsed = content
        else:
            parsed = {}

        text = parsed.get("text") or parsed.get("content") or event.get("text") or ""
        title = event.get("title") or "Feishu Request"
        return {
            "source": "feishu",
            "title": title,
            "text": text.strip(),
            "sender": event.get("sender", {}),
            "chat_id": message.get("chat_id") or event.get("open_chat_id"),
            "raw": payload,
        }

    def send_text(self, chat_id: str, text: str) -> Dict:
        if not self.settings.get("enabled"):
            return {"success": False, "error": "Feishu integration disabled"}

        webhook = self.settings.get("webhook")
        if not webhook:
            return {"success": False, "error": "Missing Feishu webhook URL"}

        body = json.dumps({"msg_type": "text", "content": {"text": text}}).encode("utf-8")
        request = urllib.request.Request(
            webhook,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = response.read().decode("utf-8")
            return {"success": True, "chat_id": chat_id, "response": payload}
        except (urllib.error.URLError, TimeoutError) as exc:
            return {"success": False, "error": str(exc)}


class GerritAdapter:
    """Pushes the current HEAD to Gerrit when configured."""

    def __init__(self, settings: Dict):
        self.settings = settings

    def submit_change(self, repo_dir: str, task_id: str, summary: str) -> Dict:
        if not self.settings.get("enabled"):
            return {"success": False, "status": "disabled", "message": "Gerrit integration disabled"}

        if not os.path.isdir(os.path.join(repo_dir, ".git")):
            return {"success": False, "status": "unavailable", "message": "Target repo is not a git repository"}

        remote = self.settings.get("remote", "origin")
        branch = self.settings.get("branch", "master")
        topic = urllib.parse.quote(self.settings.get("topic_prefix", "harness") + "-" + task_id)
        ref = f"HEAD:refs/for/{branch}%topic={topic}"

        process = subprocess.run(
            ["git", "push", remote, ref],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        return {
            "success": process.returncode == 0,
            "status": "submitted" if process.returncode == 0 else "failed",
            "command": ["git", "push", remote, ref],
            "stdout": process.stdout.strip(),
            "stderr": process.stderr.strip(),
            "summary": summary,
        }