"""External integration adapters for the agent CLI, Feishu, and Gerrit."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import queue
import shlex
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

from state_store import StateStore


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
    usage: Dict = field(default_factory=dict)
    budget_exceeded: bool = False
    interrupted: bool = False
    interrupt_reason: Optional[str] = None


class CopilotCLIAdapter:
    """Runs the configured agent CLI if available, otherwise falls back to simulation."""

    def __init__(self, settings: Dict):
        self.settings = settings
        self._interrupt_lock = threading.Lock()
        self._active_process: Optional[subprocess.Popen] = None
        self._interrupt_requested = False
        self._interrupt_reason: Optional[str] = None

    def request_interrupt(self, reason: str = "Interrupted by scheduler") -> bool:
        with self._interrupt_lock:
            self._interrupt_requested = True
            self._interrupt_reason = reason
            process = self._active_process
        if process is None:
            return False
        try:
            process.kill()
            return True
        except Exception:
            return False

    def _bind_active_process(self, process: Optional[subprocess.Popen]) -> None:
        with self._interrupt_lock:
            self._active_process = process

    def _consume_interrupt_request(self) -> tuple[bool, Optional[str]]:
        with self._interrupt_lock:
            interrupted = self._interrupt_requested
            reason = self._interrupt_reason
            self._interrupt_requested = False
            self._interrupt_reason = None
            return interrupted, reason

    def run_agent(
        self,
        agent_id: str,
        prompt: str,
        cwd: str,
        event_callback: Optional[EventCallback] = None,
        stage: Optional[str] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> AgentRunResult:
        command_text = self.settings.get("command", "python3 engine/copilot_shim.py")
        simulate = self.settings.get("simulate", False)
        command_parts = shlex.split(command_text)
        binary = command_parts[0] if command_parts else "python3"

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

        if system_prompt:
            cli_command.extend(["--system-prompt", system_prompt])

        # Claude-compatible stream-json requires --verbose in Claude Code CLI 2.x.
        # Copilot runs through engine/copilot_shim.py and ignores unsupported flags.
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
        total_usage = 0
        hard_timeout_seconds = int(self.settings.get("hard_timeout_seconds", 900))
        idle_timeout_seconds = int(self.settings.get("idle_timeout_seconds", 300))
        budget_limit = max_tokens if max_tokens is not None else int(self.settings.get("max_tokens_per_run", 0) or 0)

        try:
            process = subprocess.Popen(
                cli_command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as exc:
            error_message = f"Agent CLI failed to start: {exc}"
            return AgentRunResult(
                success=False,
                output_text="",
                transcript=[],
                command=cli_command,
                return_code=-1,
                error=error_message,
                verdict="FAIL",
                tokens_estimate=self._estimate_tokens(prompt, ""),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                usage={"total_tokens": 0},
            )

        self._bind_active_process(process)

        assert process.stdout is not None
        output_queue: queue.Queue[tuple[str, Optional[str]]] = queue.Queue()

        def stream_reader() -> None:
            try:
                while True:
                    raw_line = process.stdout.readline()
                    if raw_line == "":
                        output_queue.put(("eof", None))
                        break
                    output_queue.put(("line", raw_line))
            except Exception as exc:
                output_queue.put(("error", str(exc)))

        reader_thread = threading.Thread(target=stream_reader, daemon=True)
        reader_thread.start()

        budget_exceeded = False
        timeout_exceeded = False
        idle_timeout_exceeded = False
        interrupted = False
        stream_error: Optional[str] = None
        interrupt_reason: Optional[str] = None
        start_monotonic = time.monotonic()
        last_output_monotonic = start_monotonic
        while True:
            interrupt_requested, pending_reason = self._consume_interrupt_request()
            if interrupt_requested:
                interrupted = True
                interrupt_reason = pending_reason or "Interrupted by scheduler"
                process.kill()
                break
            if hard_timeout_seconds and time.monotonic() - start_monotonic > hard_timeout_seconds:
                timeout_exceeded = True
                process.kill()
                break
            if idle_timeout_seconds and time.monotonic() - last_output_monotonic > idle_timeout_seconds:
                idle_timeout_exceeded = True
                process.kill()
                break

            try:
                message_type, payload = output_queue.get(timeout=0.5)
            except queue.Empty:
                if process.poll() is not None and not reader_thread.is_alive():
                    break
                continue

            if message_type == "eof":
                break

            if message_type == "error":
                stream_error = payload or "unknown stream error"
                process.kill()
                break

            raw_line = payload or ""
            if not raw_line:
                continue

            last_output_monotonic = time.monotonic()
            line = raw_line.rstrip("\n")
            if not line:
                continue
            event = self._parse_stream_line(line, agent_id, stage)
            transcript.append(event)
            if event_callback:
                event_callback(event)

            usage_tokens = self._extract_usage_tokens(event)
            if usage_tokens:
                total_usage = max(total_usage, usage_tokens)
                if budget_limit and total_usage >= budget_limit:
                    budget_exceeded = True
                    process.kill()
                    break

            if event.get("type") == "stdout_ignored":
                continue

            text_value = (event.get("text") or "").strip()
            if text_value and text_value not in ("system", "assistant", "user", "result"):
                output_lines.append(text_value)

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        finally:
            self._bind_active_process(None)

        duration = (datetime.now() - start_time).total_seconds()
        output_text = "\n".join(output_lines).strip()
        verdict = self._extract_verdict(output_text)
        usage = {"total_tokens": total_usage}

        if interrupted:
            return AgentRunResult(
                success=False,
                output_text=output_text,
                transcript=transcript,
                command=cli_command,
                return_code=process.returncode or -9,
                error=interrupt_reason or "Interrupted by scheduler",
                verdict=verdict,
                tokens_estimate=total_usage or self._estimate_tokens(prompt, output_text),
                duration_seconds=duration,
                usage=usage,
                interrupted=True,
                interrupt_reason=interrupt_reason,
            )

        if stream_error:
            return AgentRunResult(
                success=False,
                output_text=output_text,
                transcript=transcript,
                command=cli_command,
                return_code=process.returncode or -9,
                error=f"Agent CLI stream reader failed: {stream_error}",
                verdict=verdict,
                tokens_estimate=total_usage or self._estimate_tokens(prompt, output_text),
                duration_seconds=duration,
                usage=usage,
            )

        if timeout_exceeded:
            return AgentRunResult(
                success=False,
                output_text=output_text,
                transcript=transcript,
                command=cli_command,
                return_code=process.returncode or -9,
                error=f"Agent CLI exceeded hard timeout of {hard_timeout_seconds}s",
                verdict=verdict,
                tokens_estimate=total_usage or self._estimate_tokens(prompt, output_text),
                duration_seconds=duration,
                usage=usage,
            )

        if idle_timeout_exceeded:
            return AgentRunResult(
                success=False,
                output_text=output_text,
                transcript=transcript,
                command=cli_command,
                return_code=process.returncode or -9,
                error=f"Agent CLI exceeded idle timeout of {idle_timeout_seconds}s without output",
                verdict=verdict,
                tokens_estimate=total_usage or self._estimate_tokens(prompt, output_text),
                duration_seconds=duration,
                usage=usage,
            )

        if budget_exceeded:
            return AgentRunResult(
                success=False,
                output_text=output_text,
                transcript=transcript,
                command=cli_command,
                return_code=process.returncode or -9,
                error=f"Agent CLI exceeded token budget limit ({budget_limit})",
                verdict=verdict,
                tokens_estimate=total_usage or self._estimate_tokens(prompt, output_text),
                duration_seconds=duration,
                usage=usage,
                budget_exceeded=True,
            )

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
                error=None if soft_success else f"Agent CLI exited with code {process.returncode}",
                verdict=verdict,
                tokens_estimate=total_usage or self._estimate_tokens(prompt, output_text),
                duration_seconds=duration,
                usage=usage,
            )

        return AgentRunResult(
            success=True,
            output_text=output_text,
            transcript=transcript,
            command=cli_command,
            return_code=process.returncode,
            verdict=verdict,
            tokens_estimate=total_usage or self._estimate_tokens(prompt, output_text),
            duration_seconds=duration,
            usage=usage,
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
            import re
            clean_line = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line.split('\r')[-1]).strip()
            if not clean_line or re.match(r'^[│└┌├┤┼┴┬─●■✗✔✘◎]\s*', clean_line) or clean_line.endswith("line...") or "lines read" in clean_line.lower() or "lines found" in clean_line.lower() or "lines..." in clean_line.lower() or "no matches found" in clean_line.lower() or clean_line.startswith("Edit output/") or clean_line.startswith("Read ") or clean_line.startswith("Search ") or clean_line.startswith("Extract ") or clean_line.startswith("Check ") or clean_line.startswith("set -euo pipefail") or "/var/folders/" in clean_line or "cd /" in clean_line:
                return {
                    "type": "stdout_ignored",
                    "agent_id": agent_id,
                    "stage": stage,
                    "message": clean_line or line,
                    "text": clean_line or line,
                }
            return {
                "type": "stdout",
                "agent_id": agent_id,
                "stage": stage,
                "message": clean_line,
                "text": clean_line,
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
            command=[self.settings.get("command", "python3 engine/copilot_shim.py"), "--simulate"],
            verdict=verdict,
            tokens_estimate=self._estimate_tokens(prompt, output_text),
            duration_seconds=1.0,
            usage={"total_tokens": self._estimate_tokens(prompt, output_text)},
        )

    def _extract_usage_tokens(self, event: Dict) -> int:
        payload = event.get("payload") or {}
        candidates = [payload]
        if isinstance(payload.get("message"), dict):
            candidates.append(payload["message"])
        for candidate in candidates:
            usage = candidate.get("usage")
            if isinstance(usage, dict):
                for key in ("total_tokens", "totalTokens", "output_tokens", "outputTokens"):
                    value = usage.get(key)
                    if isinstance(value, int):
                        return value
            for key in ("usage", "total_tokens", "totalTokens"):
                value = candidate.get(key)
                if isinstance(value, int):
                    return value
        return 0

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


ClaudeCLIAdapter = CopilotCLIAdapter


class FeishuAdapter:
    """Minimal Feishu integration for inbound requests and outbound notifications."""

    def __init__(self, settings: Dict, state_store: Optional[StateStore] = None):
        self.settings = settings
        self.state_store = state_store
        self._rate_lock = threading.Lock()
        self._recent_requests: Dict[str, List[float]] = {}

    def validate_webhook(self, raw_body: bytes, headers: Dict[str, str], remote_addr: str = "unknown") -> Dict:
        if not self.settings.get("enabled"):
            return {"ok": True, "dedup_key": None}

        rate_limit = int(self.settings.get("rate_limit_per_minute", 30))
        if rate_limit > 0 and not self._allow_request(remote_addr, rate_limit):
            return {"ok": False, "error": "Feishu webhook rate limit exceeded", "status": 429}

        secret = self.settings.get("signing_secret") or ""
        if secret:
            timestamp = headers.get("X-Lark-Request-Timestamp") or headers.get("X-Timestamp") or ""
            signature = headers.get("X-Lark-Signature") or headers.get("X-Signature") or ""
            if not timestamp or not signature:
                return {"ok": False, "error": "Missing Feishu signature headers", "status": 401}
            if not self._verify_signature(secret, timestamp, raw_body, signature):
                return {"ok": False, "error": "Invalid Feishu signature", "status": 401}

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {"ok": False, "error": "Invalid JSON payload", "status": 400}

        dedup_key = self._build_dedup_key(payload, headers, raw_body)
        ttl = int(self.settings.get("dedup_ttl_seconds", 3600))
        if dedup_key and self.state_store and not self.state_store.claim_webhook_event(dedup_key, "feishu", ttl_seconds=ttl):
            return {"ok": False, "error": "Duplicate Feishu event", "status": 202, "dedup_key": dedup_key}

        return {"ok": True, "payload": payload, "dedup_key": dedup_key}

    def _allow_request(self, remote_addr: str, rate_limit: int) -> bool:
        now = time.time()
        cutoff = now - 60
        with self._rate_lock:
            timestamps = [ts for ts in self._recent_requests.get(remote_addr, []) if ts >= cutoff]
            if len(timestamps) >= rate_limit:
                self._recent_requests[remote_addr] = timestamps
                return False
            timestamps.append(now)
            self._recent_requests[remote_addr] = timestamps
            return True

    def _verify_signature(self, secret: str, timestamp: str, raw_body: bytes, signature: str) -> bool:
        body_text = raw_body.decode("utf-8", errors="replace")
        payload = f"{timestamp}\n{body_text}".encode("utf-8")
        digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
        expected_base64 = base64.b64encode(digest).decode("utf-8")
        expected_hex = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected_base64) or hmac.compare_digest(signature, expected_hex)

    def _build_dedup_key(self, payload: Dict, headers: Dict[str, str], raw_body: bytes) -> str:
        candidates = [
            headers.get("X-Request-Id"),
            headers.get("X-Lark-Request-Id"),
            payload.get("header", {}).get("event_id") if isinstance(payload.get("header"), dict) else None,
            payload.get("event_id"),
            payload.get("uuid"),
        ]
        message = payload.get("event", {}).get("message", {}) if isinstance(payload.get("event"), dict) else {}
        if isinstance(message, dict):
            candidates.extend([message.get("message_id"), message.get("chat_id")])
        for candidate in candidates:
            if candidate:
                return str(candidate)
        return hashlib.sha256(raw_body).hexdigest()

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


class HILAdapter:
    """Stub interface for future HIL and vehicle-bus integration."""

    def __init__(self, settings: Dict):
        self.settings = settings

    def describe_capabilities(self) -> Dict:
        return {
            "enabled": bool(self.settings.get("enabled", False)),
            "status": "stub",
            "supported_backends": ["canoe", "carla", "lgsvl", "ecu-rig"],
            "message": "HIL adapter placeholder ready for CAN/LIN, simulator, and ECU integration.",
        }


class BuildVerificationAdapter:
    """Stub CI/CD bridge for build, static analysis, and release verification."""

    def __init__(self, settings: Dict):
        self.settings = settings

    def run(self, task_id: str, repo_dir: str) -> Dict:
        if not self.settings.get("enabled"):
            return {
                "success": True,
                "status": "stub",
                "task_id": task_id,
                "repo_dir": repo_dir,
                "checks": ["build", "static-analysis", "sbom", "signing"],
                "message": "Build verification adapter is configured as a stub.",
            }
        return {
            "success": False,
            "status": "unimplemented",
            "task_id": task_id,
            "repo_dir": repo_dir,
            "message": "External CI integration is enabled in config but not implemented yet.",
        }