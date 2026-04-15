"""Task-scoped context resolution and session continuity artifacts."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Optional


STAGE_CONTEXT_MANIFEST = {
    "intake": [],
    "planning": ["intake"],
    "requirements": ["planning"],
    "design": ["planning", "requirements"],
    "development": ["requirements", "design"],
    "code_review": ["requirements", "design", "development", "debugger"],
    "security_review": ["requirements", "design", "development", "code_review", "debugger"],
    "safety_review": ["requirements", "design", "development", "code_review", "security_review", "debugger"],
    "testing": ["requirements", "design", "development", "debugger"],
    "delivery": ["code_review", "security_review", "safety_review", "testing"],
    "build_verification": ["delivery", "testing"],
}


class TaskContextManager:
    """Keeps task state digest, handoff files, and prompt context compact."""

    def __init__(self, harness_dir: str, max_summary_chars: int = 900, max_section_chars: int = 1600):
        self.harness_dir = harness_dir
        self.max_summary_chars = max_summary_chars
        self.max_section_chars = max_section_chars

    def sync_task_files(self, task: Dict, reason: str = "") -> Dict[str, str]:
        run_dir = task.get("run_dir")
        if not run_dir:
            return {}

        state_path = os.path.join(run_dir, "STATE.md")
        handoff_path = os.path.join(run_dir, "HANDOFF.json")
        self._write_text(state_path, self.build_state_markdown(task))
        self._write_json(handoff_path, self.build_handoff(task, reason=reason))
        return {"state": state_path, "handoff": handoff_path}

    def build_stage_context(
        self,
        task: Dict,
        stage: str,
        runtime_context: Dict,
        memory_context: str = "",
        retry_info: Optional[Dict] = None,
    ) -> str:
        sections = [
            f"Task ID: {task.get('id', '')}",
            f"Task Title: {task.get('title', '')}",
            f"Current Stage: {stage}",
            "",
            "## Task State",
            self._build_prompt_state_digest(task),
            "",
            "## User Request",
            self._truncate(task.get("request_text", ""), self.max_section_chars),
        ]

        attachment_section = self._format_attachments(task)
        if attachment_section:
            sections.extend(["", attachment_section])

        if memory_context:
            sections.extend(["", memory_context.strip()])

        current_stage_context = self._render_current_stage_feedback(task, stage)
        if current_stage_context:
            sections.extend(["", current_stage_context])

        dependency_sections = self._build_dependency_sections(task, stage, runtime_context)
        if dependency_sections:
            sections.extend([""] + dependency_sections)

        if retry_info:
            sections.extend(
                [
                    "",
                    "## Retry Context",
                    f"Attempt: {retry_info.get('attempt')} / {retry_info.get('max_retries')}",
                    f"Previous verdict: {retry_info.get('previous_verdict')}",
                    self._truncate(retry_info.get("previous_summary", ""), self.max_summary_chars),
                ]
            )

        prompt_text = "\n".join(part for part in sections if part is not None).strip() + "\n"
        self._write_context_snapshot(task, stage, prompt_text)
        return prompt_text

    def build_state_markdown(self, task: Dict) -> str:
        completed = self._stages_by_status(task, {"passed", "completed"})
        failed = self._stages_by_status(task, {"failed"})
        pending = self._pending_stages(task)
        blockers = self._collect_blockers(task)
        next_action = self._next_action(task)
        current_stage = task.get("current_stage") or "-"
        current_stage_state = (task.get("stages") or {}).get(current_stage, {})
        current_summary = self._truncate(current_stage_state.get("summary", ""), self.max_summary_chars)

        lines = [
            "# Task State",
            "",
            "## Identity",
            f"- Task ID: {task.get('id', '')}",
            f"- Title: {task.get('title', '')}",
            f"- Status: {task.get('status', 'unknown')}",
            f"- Current Stage: {current_stage}",
            f"- Updated At: {task.get('updated_at') or task.get('created_at') or datetime.now().isoformat()}",
            "",
            "## Current Position",
            f"- Completed Stages: {', '.join(completed) if completed else 'None'}",
            f"- Pending Stages: {', '.join(pending) if pending else 'None'}",
            f"- Failed Stages: {', '.join(failed) if failed else 'None'}",
            f"- Next Action: {next_action}",
        ]

        if current_summary:
            lines.extend(["", "## Current Stage Summary", current_summary])

        if blockers:
            lines.extend(["", "## Blockers"])
            lines.extend(f"- {blocker}" for blocker in blockers[:5])

        recent = self._recent_stage_updates(task)
        if recent:
            lines.extend(["", "## Recent Stage Outcomes"])
            for item in recent[:5]:
                lines.append(f"- [{item['stage']}] {item['status']}: {item['summary']}")

        return "\n".join(lines).strip() + "\n"

    def build_handoff(self, task: Dict, reason: str = "") -> Dict:
        current_stage = task.get("current_stage")
        resume_artifact = None
        if current_stage:
            stage_state = (task.get("stages") or {}).get(current_stage, {})
            artifact_paths = stage_state.get("artifact_paths") or []
            if artifact_paths:
                resume_artifact = self._relativize(artifact_paths[0])

        return {
            "task_id": task.get("id"),
            "title": task.get("title"),
            "status": task.get("status"),
            "current_stage": current_stage,
            "updated_at": task.get("updated_at") or datetime.now().isoformat(),
            "completed_stages": self._stages_by_status(task, {"passed", "completed"}),
            "pending_stages": self._pending_stages(task),
            "failed_stages": self._stages_by_status(task, {"failed"}),
            "blockers": self._collect_blockers(task),
            "next_action": self._next_action(task),
            "resume_artifact": resume_artifact,
            "reason": reason,
            "context_notes": self._truncate(self._recent_context_notes(task), self.max_section_chars),
        }

    def _build_dependency_sections(self, task: Dict, stage: str, runtime_context: Dict) -> List[str]:
        dependencies = STAGE_CONTEXT_MANIFEST.get(stage)
        if dependencies is None:
            dependencies = self._fallback_dependencies(task, stage)

        sections: List[str] = []
        for dependency in dependencies:
            section = self._render_stage_context(task, dependency, runtime_context)
            if section:
                sections.append(section)
        return sections

    def _render_stage_context(self, task: Dict, dependency: str, runtime_context: Dict) -> str:
        stage_payload = runtime_context.get(dependency, {})
        stage_state = (task.get("stages") or {}).get(dependency, {})
        task_context = (task.get("context") or {}).get(dependency, {})

        handoff = task_context.get("handoff_summary")
        summary = handoff or stage_payload.get("summary") or stage_state.get("summary") or ""
        summary = self._truncate(summary, self.max_summary_chars)
        verdict = stage_payload.get("verdict") or stage_state.get("verdict") or "-"
        artifact_paths = stage_payload.get("artifact_paths") or stage_state.get("artifact_paths") or []
        relevant_artifacts = [self._relativize(path) for path in artifact_paths[:3] if path]

        details = [f"## {dependency} Context", f"Verdict: {verdict}"]
        if summary:
            details.append(summary)
        if relevant_artifacts:
            details.append("Artifacts:")
            details.extend(f"- {path}" for path in relevant_artifacts)

        if len(details) <= 2:
            return ""
        return "\n".join(details)

    def _render_current_stage_feedback(self, task: Dict, stage: str) -> str:
        task_context = (task.get("context") or {}).get(stage, {})
        feedback = self._truncate(task_context.get("human_feedback", ""), self.max_summary_chars)
        if not feedback:
            return ""

        details = ["## Human Feedback", feedback]
        updated_at = task_context.get("human_feedback_updated_at")
        if updated_at:
            details.append(f"Updated At: {updated_at}")
        return "\n".join(details)

    def _build_prompt_state_digest(self, task: Dict) -> str:
        blockers = self._collect_blockers(task)
        completed = self._stages_by_status(task, {"passed", "completed"})
        pending = self._pending_stages(task)
        lines = [
            f"Status: {task.get('status', 'unknown')}",
            f"Current stage: {task.get('current_stage') or '-'}",
            f"Completed: {', '.join(completed) if completed else 'None'}",
            f"Pending: {', '.join(pending) if pending else 'None'}",
            f"Next action: {self._next_action(task)}",
        ]
        if blockers:
            lines.append("Blockers:")
            lines.extend(f"- {blocker}" for blocker in blockers[:3])
        return "\n".join(lines)

    def _format_attachments(self, task: Dict) -> str:
        attachments = task.get("attachments") or []
        if not attachments:
            return ""

        lines = ["## Uploaded Files"]
        for index, attachment in enumerate(attachments, start=1):
            lines.append(
                f"{index}. {attachment.get('name') or attachment.get('stored_name') or f'attachment-{index}'} "
                f"({attachment.get('content_type') or 'unknown'}, {attachment.get('size_bytes') or 0} bytes)"
            )
            if attachment.get("path"):
                lines.append(f"Path: {self._relativize(attachment['path'])}")
            preview = (attachment.get("preview") or "").strip()
            if preview:
                lines.append("Preview:")
                lines.append(self._truncate(preview, 600))
            else:
                lines.append("Preview unavailable; inspect the file directly if needed.")
        return "\n".join(lines)

    def _collect_blockers(self, task: Dict) -> List[str]:
        blockers: List[str] = []
        for approval in task.get("approvals", []):
            if approval.get("status") == "pending":
                blockers.append(f"Approval pending at {approval.get('stage')}: {approval.get('reason', '')}".strip())

        for stage_name, stage_state in (task.get("stages") or {}).items():
            if stage_state.get("status") == "failed":
                blockers.append(f"Stage {stage_name} failed: {self._truncate(stage_state.get('summary', ''), 180)}")
            if stage_state.get("verdict") == "NEED_HUMAN":
                blockers.append(f"Stage {stage_name} requires human intervention")

        return blockers[:8]

    def _pending_stages(self, task: Dict) -> List[str]:
        return [
            stage_name
            for stage_name, stage_state in (task.get("stages") or {}).items()
            if stage_state.get("status") not in {"passed", "completed"}
        ]

    def _stages_by_status(self, task: Dict, statuses: set[str]) -> List[str]:
        return [
            stage_name
            for stage_name, stage_state in (task.get("stages") or {}).items()
            if stage_state.get("status") in statuses
        ]

    def _recent_stage_updates(self, task: Dict) -> List[Dict[str, str]]:
        updates: List[Dict[str, str]] = []
        for stage_name, stage_state in (task.get("stages") or {}).items():
            ended_at = stage_state.get("ended_at") or stage_state.get("started_at") or ""
            summary = self._truncate(stage_state.get("summary", ""), 180)
            if not ended_at and not summary:
                continue
            updates.append(
                {
                    "stage": stage_name,
                    "status": stage_state.get("status", "pending"),
                    "summary": summary or "No summary captured",
                    "ended_at": ended_at,
                }
            )
        updates.sort(key=lambda item: item.get("ended_at", ""), reverse=True)
        return updates

    def _recent_context_notes(self, task: Dict) -> str:
        notes: List[str] = []
        for item in self._recent_stage_updates(task)[:3]:
            notes.append(f"[{item['stage']}] {item['summary']}")
        return "\n".join(notes)

    def _fallback_dependencies(self, task: Dict, stage: str) -> List[str]:
        ordered = []
        for item in task.get("pipeline_snapshot") or []:
            stage_id = item if isinstance(item, str) else item.get("id")
            if not stage_id or stage_id == stage:
                break
            ordered.append(stage_id)
        return ordered[-4:]

    def _next_action(self, task: Dict) -> str:
        if task.get("status") == "failed":
            return f"Retry task from stage {task.get('current_stage') or 'unknown'}"
        if task.get("status") == "waiting_human":
            return "Resolve the pending approval and resume the runner"
        if task.get("status") == "completed":
            return "Archive or review final artifacts"
        current_stage = task.get("current_stage")
        if current_stage:
            return f"Continue {current_stage}"
        pending = self._pending_stages(task)
        if pending:
            return f"Start {pending[0]}"
        return "Wait for the next task"

    def _write_context_snapshot(self, task: Dict, stage: str, prompt_text: str) -> None:
        run_dir = task.get("run_dir")
        if not run_dir:
            return
        path = os.path.join(run_dir, "context", f"{stage}.md")
        self._write_text(path, prompt_text)

    def _truncate(self, text: str, limit: int) -> str:
        value = (text or "").strip()
        if len(value) <= limit:
            return value
        return value[: limit - 3].rstrip() + "..."

    def _relativize(self, path: str) -> str:
        try:
            return os.path.relpath(path, self.harness_dir)
        except ValueError:
            return path

    def _write_text(self, path: str, content: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def _write_json(self, path: str, payload: Dict) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
