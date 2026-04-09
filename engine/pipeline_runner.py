"""Harness orchestration service with realtime UI, Feishu intake, and Gerrit delivery."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import sys
import threading
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import yaml
except ImportError:
    yaml = None

try:
    from flask import Flask, Response, jsonify, request, send_from_directory
except ImportError as exc:
    raise RuntimeError("Flask is required to run the harness dashboard") from exc

from distillers.context_distiller import ContextDistiller
from event_bus import EventBus
from integrations import BuildVerificationAdapter, ClaudeCLIAdapter, FeishuAdapter, GerritAdapter, HILAdapter
from memory_store import MemoryStore
from memory_extractor import MemoryExtractor, MemoryInjector
from reviewers.change_impact_analyzer import ChangeImpactAnalyzer
from reviewers.consistency_checker import ConsistencyChecker
from state_store import StateStore
from state_machine import PipelineEngine


DEFAULT_PIPELINE_ORDER = [
    "intake",
    "planning",
    "requirements",
    "design",
    "development",
    "code_review",
    "security_review",
    "safety_review",
    "testing",
    "delivery",
    "build_verification",
]

DEFAULT_AGENTS = [
    {"id": "planner", "name": "Planner", "model": "claude-opus", "role": "scope tasks and define a sprint contract"},
    {"id": "requirements-analyst", "name": "Requirements Analyst", "model": "claude-opus", "role": "turn requests into a traceable requirement spec"},
    {"id": "system-architect", "name": "System Architect", "model": "claude-opus", "role": "design architecture, APIs, and data flow"},
    {"id": "developer", "name": "Developer", "model": "claude-sonnet", "role": "implement changes in the target workspace"},
    {"id": "code-reviewer", "name": "Code Reviewer", "model": "claude-opus", "role": "independently review code quality and logic"},
    {"id": "security-reviewer", "name": "Security Reviewer", "model": "claude-opus", "role": "independently review security and compliance risks"},
    {"id": "safety-reviewer", "name": "Safety Reviewer", "model": "claude-opus", "role": "review ISO 26262, AUTOSAR, and vehicle safety compliance impacts"},
    {"id": "qa-engineer", "name": "QA Engineer", "model": "claude-sonnet", "role": "execute validation, tests, and acceptance checks"},
    {"id": "debugger", "name": "Debugger", "model": "claude-sonnet", "role": "apply narrow fixes after failed review or QA"},
    {"id": "build-verifier", "name": "Build Verifier", "model": "system", "role": "trigger downstream build, static analysis, SBOM, and signing checks"},
    {"id": "delivery-manager", "name": "Delivery Manager", "model": "system", "role": "submit changes to Gerrit and notify Feishu"},
]

STAGE_TO_AGENT = {
    "intake": "planner",
    "planning": "planner",
    "requirements": "requirements-analyst",
    "design": "system-architect",
    "development": "developer",
    "code_review": "code-reviewer",
    "security_review": "security-reviewer",
    "safety_review": "safety-reviewer",
    "testing": "qa-engineer",
    "delivery": "delivery-manager",
    "build_verification": "build-verifier",
    "debugger": "debugger",
}

STAGE_TITLES = {
    "intake": "Request Intake",
    "planning": "Sprint Planning",
    "requirements": "Requirements",
    "design": "System Design",
    "development": "Implementation",
    "code_review": "Code Review",
    "security_review": "Security Review",
    "safety_review": "Safety Review",
    "testing": "QA Testing",
    "delivery": "Gerrit Delivery",
    "build_verification": "Build Verification",
    "debugger": "Targeted Debugging",
}

HUMAN_KEYWORDS = ["security", "auth", "payment", "prod", "生产", "隐私", "删除数据", "权限"]


class PipelineRunner:
    """Coordinates requests, agents, event streaming, and manual approvals."""

    def __init__(self, harness_dir: str):
        self.harness_dir = harness_dir
        self.state_store = StateStore(harness_dir)
        self.data_dir = os.path.join(harness_dir, "data")
        self.tasks_dir = os.path.join(self.data_dir, "tasks")
        self.runs_dir = os.path.join(harness_dir, "runs")
        self.specs_pending = os.path.join(harness_dir, "specs", "pending")
        self.specs_processed = os.path.join(harness_dir, "specs", "processed")
        self.settings_file = os.path.join(self.data_dir, "integration_settings.json")
        self.runtime_file = os.path.join(self.data_dir, "runtime_state.json")
        self.transcript_dir = os.path.join(self.data_dir, "transcripts")
        self.report_dir = os.path.join(self.data_dir, "reports")
        self.lock = threading.RLock()
        self.running = False
        self.paused = False
        self.worker_thread: Optional[threading.Thread] = None

        for directory in [
            self.data_dir,
            self.tasks_dir,
            self.runs_dir,
            self.specs_pending,
            self.specs_processed,
            self.transcript_dir,
            self.report_dir,
            os.path.join(harness_dir, "requirements"),
            os.path.join(harness_dir, "design"),
            os.path.join(harness_dir, "tests", "reports"),
            os.path.join(self.data_dir, "threads"),
        ]:
            os.makedirs(directory, exist_ok=True)

        self.default_pipeline_config = self._load_yaml(
            os.path.join(harness_dir, "pipeline.yaml"),
            {"stages": [{"id": stage} for stage in DEFAULT_PIPELINE_ORDER]},
        )
        self.custom_pipeline_file = os.path.join(self.data_dir, "custom_pipeline.yaml")
        custom = self._load_yaml(self.custom_pipeline_file, None)
        self.pipeline_config = custom if custom else dict(self.default_pipeline_config)
        self.agent_config = self._load_yaml(
            os.path.join(harness_dir, "agents", "agents.yaml"),
            {"agents": []},
        )
        self.settings = self._load_settings()
        self.engine = PipelineEngine(harness_dir, budget_limit=self.settings["budget_limit"])
        self.event_bus = EventBus(self.data_dir)
        self.distiller = ContextDistiller(harness_dir)
        self.memory_store = MemoryStore(harness_dir)
        self.memory_extractor = MemoryExtractor(self.memory_store)
        self.memory_injector = MemoryInjector(self.memory_store)
        self.consistency_checker = ConsistencyChecker(harness_dir)
        self.change_impact_analyzer = ChangeImpactAnalyzer(harness_dir)
        self.claude = ClaudeCLIAdapter(self.settings["claude"])
        self.feishu = FeishuAdapter(self.settings["feishu"], state_store=self.state_store)
        self.gerrit = GerritAdapter(self.settings["gerrit"])
        self.hil = HILAdapter(self.settings["hil"])
        self.build_verifier = BuildVerificationAdapter(self.settings["build_verification"])
        self.agent_identities = self._load_yaml(
            os.path.join(harness_dir, "agents", "identities.yaml"),
            {},
        )

        self.pipeline_order = self._resolve_pipeline_order()
        self.agents = self._build_agent_state()
        self.runtime = self._load_runtime_state()
        self._ensure_runtime_shape()

    def _load_yaml(self, path: str, default: Dict) -> Dict:
        if not os.path.exists(path) or yaml is None:
            return default
        with open(path, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        return loaded if isinstance(loaded, dict) else default

    def _default_settings(self) -> Dict:
        return {
            "target_repo": self.harness_dir,
            "budget_limit": 500000,
            "claude": {
                "command": os.environ.get("HARNESS_CLAUDE_COMMAND", "claude"),
                "model": os.environ.get("HARNESS_CLAUDE_MODEL", ""),
                "max_turns": int(os.environ.get("HARNESS_CLAUDE_MAX_TURNS", "30")),
                "output_format": "stream-json",
                "simulate": os.environ.get("HARNESS_SIMULATE_CLAUDE", "1") == "1",
                "hard_timeout_seconds": int(os.environ.get("HARNESS_CLAUDE_HARD_TIMEOUT", "1800")),
                "idle_timeout_seconds": int(os.environ.get("HARNESS_CLAUDE_IDLE_TIMEOUT", "300")),
                "max_tokens_per_run": int(os.environ.get("HARNESS_CLAUDE_MAX_TOKENS_PER_RUN", "0")),
            },
            "feishu": {
                "enabled": False,
                "webhook": "",
                "signing_secret": "",
                "dedup_ttl_seconds": 3600,
                "rate_limit_per_minute": 30,
            },
            "gerrit": {
                "enabled": False,
                "remote": "origin",
                "branch": "master",
                "topic_prefix": "harness",
            },
            "hil": {
                "enabled": False,
            },
            "build_verification": {
                "enabled": False,
            },
        }

    def _load_settings(self) -> Dict:
        settings = self._default_settings()
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            settings = self._deep_merge(settings, loaded)
        self._save_json(self.settings_file, settings)
        return settings

    def _build_agent_state(self) -> Dict[str, Dict]:
        configured = {agent.get("id"): agent for agent in self.agent_config.get("agents", [])}
        agents: Dict[str, Dict] = {}
        for agent in DEFAULT_AGENTS:
            merged = dict(agent)
            merged.update(configured.get(agent["id"], {}))
            merged.update(
                {
                    "status": "idle",
                    "current_task_id": None,
                    "last_stage": None,
                    "last_message": "",
                    "completed_tasks": 0,
                }
            )
            agents[merged["id"]] = merged
        return agents

    def _resolve_pipeline_order(self) -> List[str]:
        configured = [stage.get("id") for stage in self.pipeline_config.get("stages", []) if stage.get("id")]
        if configured:
            seen = set()
            order = []
            for stage in configured:
                if stage not in seen:
                    order.append(stage)
                    seen.add(stage)
            return order
        return list(DEFAULT_PIPELINE_ORDER)

    def _load_runtime_state(self) -> Dict:
        stored = self.state_store.load_document("runtime_state")
        if stored is not None:
            return stored
        if not os.path.exists(self.runtime_file):
            return {
                "tasks": [],
                "current_task_id": None,
                "started_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        with open(self.runtime_file, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _ensure_runtime_shape(self) -> None:
        self.runtime.setdefault("tasks", [])
        self.runtime.setdefault("current_task_id", None)
        self.runtime.setdefault("started_at", datetime.now().isoformat())
        self.runtime.setdefault("updated_at", datetime.now().isoformat())
        for task in self.runtime["tasks"]:
            task.setdefault("approvals", [])
            task.setdefault("context", {})
            task.setdefault("artifacts", {})
            task.setdefault("gerrit", {})
            task.setdefault("source_metadata", {})
            task.setdefault("run_dir", self._ensure_run_layout(task["id"]))
            stage_defaults = self._empty_stage_map()
            existing = task.setdefault("stages", {})
            for stage_id, stage_payload in stage_defaults.items():
                existing.setdefault(stage_id, stage_payload)
            self._write_run_metadata(task)

    def _empty_stage_map(self) -> Dict[str, Dict]:
        return {
            stage: {
                "title": STAGE_TITLES.get(stage, stage),
                "status": "pending",
                "agent_id": STAGE_TO_AGENT.get(stage, "planner"),
                "attempts": 0,
                "summary": "",
                "verdict": None,
                "started_at": None,
                "ended_at": None,
                "artifact_paths": [],
                "logs": [],
            }
            for stage in self.pipeline_order
        }

    def _task_pipeline_order(self, task: Dict) -> List[str]:
        snapshot = task.get("pipeline_snapshot") or []
        if snapshot:
            order = []
            seen = set()
            for item in snapshot:
                stage_id = item if isinstance(item, str) else item.get("id")
                if stage_id and stage_id not in seen:
                    order.append(stage_id)
                    seen.add(stage_id)
            if order:
                return order
        return list(self.pipeline_order)

    def _persist_runtime(self) -> None:
        self.runtime["updated_at"] = datetime.now().isoformat()
        self.state_store.save_document("runtime_state", self.runtime)
        self._save_json(self.runtime_file, self.runtime)

    def _save_json(self, path: str, payload: Dict) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

    def _save_text(self, path: str, content: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        result = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.worker_thread.start()
        self._emit("runner_started", "Harness runner started", source="system")

    def stop(self) -> None:
        self.running = False
        self._emit("runner_stopped", "Harness runner stopped", source="system")

    def pause(self) -> None:
        self.paused = True
        self._emit("runner_paused", "Harness runner paused", source="system")

    def resume(self) -> None:
        self.paused = False
        self._emit("runner_resumed", "Harness runner resumed", source="system")

    def submit_request(self, text: str, title: Optional[str] = None, source: str = "web", metadata: Optional[Dict] = None) -> Dict:
        task_id = f"task-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        spec_file = f"{task_id}.md"
        spec_path = os.path.join(self.specs_pending, spec_file)
        content = f"# {title or 'User Request'}\n\n{text.strip()}\n"
        self._save_text(spec_path, content)
        run_dir = self._ensure_run_layout(task_id)
        pipeline_snapshot = json.loads(json.dumps(self.pipeline_config.get("stages", []), ensure_ascii=False))
        first_stage = (pipeline_snapshot[0].get("id") if pipeline_snapshot else None) or self.pipeline_order[0]

        task = {
            "id": task_id,
            "title": title or "Untitled request",
            "request_text": text.strip(),
            "source": source,
            "source_metadata": metadata or {},
            "spec_file": spec_file,
            "run_dir": run_dir,
            "status": "queued",
            "current_stage": first_stage,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "approvals": [],
            "context": {},
            "artifacts": {},
            "gerrit": {},
            "stages": self._empty_stage_map(),
            "pipeline_snapshot": pipeline_snapshot,
        }

        with self.lock:
            self.runtime["tasks"].append(task)
            self._persist_runtime()
        self._update_latest_run_link(run_dir)
        self._write_run_metadata(task)

        self._emit("task_submitted", f"New request submitted from {source}", source=source, task_id=task_id, data={"title": task["title"]})
        return task

    def get_runtime_snapshot(self) -> Dict:
        with self.lock:
            tasks = list(reversed(self.runtime["tasks"][-20:]))
            approvals = []
            for task in tasks:
                for approval in task.get("approvals", []):
                    if approval.get("status") == "pending":
                        approvals.append(dict(approval, task_id=task["id"], task_title=task["title"]))
            stats = {
                "total": len(self.runtime["tasks"]),
                "queued": sum(1 for task in self.runtime["tasks"] if task["status"] == "queued"),
                "running": sum(1 for task in self.runtime["tasks"] if task["status"] == "running"),
                "waiting_human": sum(1 for task in self.runtime["tasks"] if task["status"] == "waiting_human"),
                "completed": sum(1 for task in self.runtime["tasks"] if task["status"] == "completed"),
                "failed": sum(1 for task in self.runtime["tasks"] if task["status"] == "failed"),
            }
            return {
                "runner": {
                    "running": self.running,
                    "paused": self.paused,
                    "current_task_id": self.runtime.get("current_task_id"),
                    "updated_at": self.runtime.get("updated_at"),
                },
                "pipeline_order": self.pipeline_order,
                "stats": stats,
                "tasks": tasks,
                "approvals": approvals,
                "agents": list(self.agents.values()),
                "settings": self.settings,
                "events": self.event_bus.latest(200),
                "budget": self.engine.check_budget(),
            }

    def update_settings(self, payload: Dict) -> Dict:
        with self.lock:
            self.settings = self._deep_merge(self.settings, payload)
            self._save_json(self.settings_file, self.settings)
            self.claude = ClaudeCLIAdapter(self.settings["claude"])
            self.feishu = FeishuAdapter(self.settings["feishu"], state_store=self.state_store)
            self.gerrit = GerritAdapter(self.settings["gerrit"])
            self.hil = HILAdapter(self.settings["hil"])
            self.build_verifier = BuildVerificationAdapter(self.settings["build_verification"])
            self._persist_runtime()
        self._emit("settings_updated", "Integration settings updated", source="system")
        return self.settings

    def resolve_approval(self, task_id: str, approval_id: str, resolution: str, note: str = "") -> Dict:
        with self.lock:
            task = self._require_task(task_id)
            for approval in task.get("approvals", []):
                if approval["id"] != approval_id:
                    continue
                approval["status"] = resolution
                approval["resolved_at"] = datetime.now().isoformat()
                approval["note"] = note
                task["updated_at"] = datetime.now().isoformat()
                self._emit("approval_resolved", f"Approval {resolution} for {task['title']}", source="human", task_id=task_id, stage=approval.get("stage"), data={"approval_id": approval_id, "note": note, "resolution": resolution})
                if resolution == "approved":
                    task["status"] = "running"
                elif resolution == "rejected":
                    task["status"] = "failed"
                self._persist_runtime()
                return approval
        raise KeyError(f"Approval {approval_id} not found for task {task_id}")

    def _require_task(self, task_id: str) -> Dict:
        for task in self.runtime["tasks"]:
            if task["id"] == task_id:
                return task
        raise KeyError(f"Task {task_id} not found")

    def _run_loop(self) -> None:
        while self.running:
            if self.paused:
                time.sleep(1)
                continue
            # First check if there's a running task that needs to be resumed
            running_task = self._get_running_task()
            if running_task:
                self._resume_running_task(running_task)
                continue
            # Then check for queued tasks
            next_task = self._next_queued_task()
            if next_task is None:
                time.sleep(1)
                continue
            self._process_task(next_task)

    def _get_running_task(self) -> Optional[Dict]:
        """Get a task that was left in 'running' state (e.g., after restart)."""
        with self.lock:
            current_id = self.runtime.get("current_task_id")
            if current_id:
                for task in self.runtime["tasks"]:
                    if task["id"] == current_id and task["status"] == "running":
                        return task
        return None

    def _resume_running_task(self, task: Dict) -> None:
        """Resume a task that was interrupted (e.g., by a restart)."""
        task_id = task["id"]
        task_pipeline_order = self._task_pipeline_order(task)
        self._emit("task_resumed", f"Resuming interrupted task: {task['title']}", source="pipeline", task_id=task_id)
        
        # Find the stage that was running and reset it
        for stage in task_pipeline_order:
            stage_data = task["stages"].get(stage, {})
            if stage_data.get("status") == "running":
                # This stage was interrupted, mark it for retry
                stage_data["status"] = "pending"
                stage_data["attempts"] = stage_data.get("attempts", 1)  # Keep retry count
                now = datetime.now().isoformat()
                task["updated_at"] = now
                self._persist_runtime()
                break
        
        # Continue processing
        self._continue_task(task)

    def _continue_task(self, task: Dict) -> None:
        """Continue processing a task from where it left off."""
        task_id = task["id"]
        task_pipeline_order = self._task_pipeline_order(task)
        self.engine.snapshot.current_spec = task["spec_file"]
        self._update_latest_run_link(task["run_dir"])
        
        context = {"request_text": task["request_text"]}
        context.update(task.get("context", {}))

        for stage in task_pipeline_order:
            stage_data = task["stages"].get(stage, {})
            if stage_data.get("status") in ("passed", "completed"):
                continue
            
            if not self.running:
                return
            if self.paused:
                return
            
            task["current_stage"] = stage
            self._persist_runtime()
            
            if stage == "delivery":
                if not self._run_delivery_stage(task, context):
                    return
                continue
            if stage == "build_verification":
                if not self._run_build_verification_stage(task, context):
                    return
                continue
            if not self._run_stage_with_retries(task, stage, context):
                return
        
        self._complete_task(task)

    def _next_queued_task(self) -> Optional[Dict]:
        with self.lock:
            for task in self.runtime["tasks"]:
                if task["status"] == "queued":
                    return task
        return None

    def _process_task(self, task: Dict) -> None:
        task_id = task["id"]
        task_pipeline_order = self._task_pipeline_order(task)
        with self.lock:
            task["status"] = "running"
            task["updated_at"] = datetime.now().isoformat()
            self.runtime["current_task_id"] = task_id
            self._persist_runtime()

        self.engine.snapshot.current_spec = task["spec_file"]
        self.engine.reset_for_new_iteration()
        # 确保状态机在正确的初始状态
        if self.engine.snapshot.current_state != "idle":
            self.engine.snapshot.current_state = "idle"
            self.engine._save_state()
        result = self.engine.transition("new_spec")
        if result is None:
            self._fail_task(task, "Failed to transition pipeline to REQUIREMENTS state")
            return
        self._update_latest_run_link(task["run_dir"])
        self._emit("task_started", f"Processing {task['title']}", task_id=task_id, source="pipeline")

        # Rebuild context from previously passed stages
        context = {"request_text": task["request_text"]}
        context.update(task.get("context", {}))

        for stage in task_pipeline_order:
            # Skip stages that already passed (resume support)
            stage_data = task["stages"].get(stage, {})
            if stage_data.get("status") in ("passed", "completed"):
                self._emit("stage_skipped", f"{STAGE_TITLES.get(stage, stage)} already passed, skipping", source="pipeline", task_id=task_id, stage=stage)
                continue

            with self.lock:
                task["current_stage"] = stage
                task["updated_at"] = datetime.now().isoformat()
                self._persist_runtime()

            if self._requires_manual_gate(task, stage):
                approval = self._create_approval(task, stage, "Risky request requires human confirmation before continuing")
                approved = self._wait_for_approval(task, approval)
                if not approved:
                    self._fail_task(task, f"Approval rejected at {stage}")
                    return

            if stage == "delivery":
                if not self._run_delivery_stage(task, context):
                    self._fail_task(task, "Delivery stage failed")
                    return
                continue

            if stage == "build_verification":
                if not self._run_build_verification_stage(task, context):
                    self._fail_task(task, "Build verification stage failed")
                    return
                continue

            if not self._run_stage_with_retries(task, stage, context):
                return

        self._complete_task(task)

    def _run_stage_with_retries(self, task: Dict, stage: str, context: Dict) -> bool:
        stage_state = task["stages"][stage]
        max_retries = self._stage_max_retries(stage)
        budget = self.engine.check_budget()
        if budget["status"] == "exceeded":
            self._fail_task(task, f"Budget hard stop reached before {stage}")
            return False

        previous_summary = None
        previous_verdict = None
        
        for attempt in range(1, max_retries + 1):
            with self.lock:
                now = datetime.now().isoformat()
                task["updated_at"] = now
                stage_state["attempts"] = attempt
                stage_state["status"] = "running"
                stage_state["started_at"] = now
                stage_state["last_event_at"] = now
                stage_state["summary"] = ""
                self._persist_runtime()
            self.engine.start_stage(stage)
            agent_id = stage_state["agent_id"]
            self._set_agent_status(agent_id, "running", task["id"], stage, f"Running {stage}")
            self._emit("stage_started", f"{STAGE_TITLES.get(stage, stage)} started (attempt {attempt}/{max_retries})", source="pipeline", task_id=task["id"], stage=stage)

            # Build prompt with retry context if this is a retry
            retry_info = None
            if attempt > 1 and previous_summary:
                retry_info = {
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "previous_summary": previous_summary,
                    "previous_verdict": previous_verdict,
                }
            prompt = self._build_prompt(task, stage, context, retry_info)
            
            remaining_tokens = max(0, self.engine.snapshot.budget_limit - self.engine.snapshot.total_tokens_used)
            result = self.claude.run_agent(
                agent_id=agent_id,
                prompt=prompt,
                cwd=self.settings["target_repo"],
                stage=stage,
                system_prompt=self._agent_identity(agent_id),
                max_tokens=remaining_tokens,
                event_callback=lambda event: self._record_agent_event(task, stage, agent_id, event),
            )

            transcript_path = self._write_transcript(task, stage, result)
            summary, verdict = self._summarize_result(stage, result.output_text, result.verdict)
            artifact_paths = self._materialize_stage_artifacts(task, stage, summary, result.output_text, transcript_path)
            context[stage] = {"summary": summary, "verdict": verdict, "artifact_paths": artifact_paths}

            passed = result.success and verdict != "FAIL"
            if stage in {"code_review", "security_review", "safety_review", "testing"}:
                passed = passed and verdict != "NEED_HUMAN"

            with self.lock:
                stage_state["status"] = "passed" if passed else "failed"
                stage_state["summary"] = summary
                stage_state["verdict"] = verdict
                stage_state["ended_at"] = datetime.now().isoformat()
                stage_state["artifact_paths"] = artifact_paths
                self._persist_runtime()
            self.engine.complete_stage(stage, token_usage=result.tokens_estimate, success=passed)
            self._set_agent_status(agent_id, "idle", None, stage, summary)

            if result.budget_exceeded:
                self._fail_task(task, f"Budget hard stop triggered during {stage}")
                return False

            if passed:
                self._post_stage_processing(task, stage, summary, artifact_paths)
                self._emit("stage_completed", f"{STAGE_TITLES.get(stage, stage)} passed", source="pipeline", task_id=task["id"], stage=stage, data={"verdict": verdict})
                return True

            # Save failure info for retry
            previous_summary = summary
            previous_verdict = verdict
            
            self._emit("stage_failed", f"{STAGE_TITLES.get(stage, stage)} failed on attempt {attempt}/{max_retries}", source="pipeline", task_id=task["id"], stage=stage, level="error", data={"summary": summary, "verdict": verdict})

            if verdict == "NEED_HUMAN":
                approval = self._create_approval(task, stage, summary or f"Manual action required at {stage}")
                approved = self._wait_for_approval(task, approval)
                if not approved:
                    self._fail_task(task, f"Approval rejected at {stage}")
                    return False

            if attempt < max_retries:
                # Stages that benefit from debugger agent for targeted fixes
                debugger_stages = {"development", "code_review", "security_review", "safety_review", "testing"}
                if stage in debugger_stages:
                    if not self._run_debugger(task, stage, summary, context):
                        break
                else:
                    # For early stages (requirements, design, etc.), allow self-retry with feedback
                    self._emit("stage_retry", f"{STAGE_TITLES.get(stage, stage)} will retry (attempt {attempt + 1}/{max_retries})", 
                              source="pipeline", task_id=task["id"], stage=stage, level="warning")
                    # Continue to next iteration - retry_info will be passed to prompt

        self._fail_task(task, f"Stage {stage} exhausted retries")
        return False

    def _run_debugger(self, task: Dict, failed_stage: str, failure_summary: str, context: Dict) -> bool:
        debugger_stage = {
            "title": STAGE_TITLES["debugger"],
            "status": "running",
            "agent_id": "debugger",
            "attempts": 1,
            "summary": "",
            "verdict": None,
            "started_at": datetime.now().isoformat(),
            "ended_at": None,
            "artifact_paths": [],
            "logs": [],
        }
        task["stages"]["debugger"] = debugger_stage
        self._set_agent_status("debugger", "running", task["id"], "debugger", f"Fixing {failed_stage}")

        # 检查预算
        budget = self.engine.check_budget()
        if budget["status"] == "exceeded":
            self._emit("budget_exceeded", "Budget exceeded before debugger stage", source="system", task_id=task["id"], level="error")
            return False

        prompt = (
            f"Task: {task['title']}\n"
            f"Failed stage: {failed_stage}\n"
            f"Failure summary: {failure_summary}\n"
            "Apply the smallest possible correction plan and report the fix scope.\n"
            "Finish with VERDICT: PASS when a targeted fix is prepared."
        )
        remaining_tokens = max(0, self.engine.snapshot.budget_limit - self.engine.snapshot.total_tokens_used)
        result = self.claude.run_agent(
            agent_id="debugger",
            prompt=prompt,
            cwd=self.settings["target_repo"],
            stage="debugger",
            system_prompt=self._agent_identity("debugger"),
            max_tokens=remaining_tokens,
            event_callback=lambda event: self._record_agent_event(task, "debugger", "debugger", event),
        )
        transcript_path = self._write_transcript(task, "debugger", result)
        summary, verdict = self._summarize_result("debugger", result.output_text, result.verdict)
        artifacts = self._materialize_stage_artifacts(task, "debugger", summary, result.output_text, transcript_path)
        task["stages"]["debugger"].update({"status": "passed" if result.success else "failed", "summary": summary, "verdict": verdict, "ended_at": datetime.now().isoformat(), "artifact_paths": artifacts})
        self._persist_runtime()
        self._set_agent_status("debugger", "idle", None, "debugger", summary)
        context["debugger"] = {"summary": summary, "artifact_paths": artifacts}
        return result.success

    def _run_delivery_stage(self, task: Dict, context: Dict) -> bool:
        stage = "delivery"
        stage_state = task["stages"][stage]
        stage_state["status"] = "running"
        stage_state["started_at"] = datetime.now().isoformat()
        self._set_agent_status("delivery-manager", "running", task["id"], stage, "Preparing Gerrit delivery")

        summary = "All quality gates passed. Preparing Gerrit submission."
        result = self.gerrit.submit_change(self.settings["target_repo"], task["id"], summary)
        task["gerrit"] = result
        artifact_path = os.path.join(task["run_dir"], "delivery", "delivery.md")
        report = [
            f"# Delivery Report - {task['title']}",
            "",
            f"Status: {result.get('status')}",
            f"Success: {result.get('success')}",
            "",
            "## Details",
            json.dumps(result, indent=2, ensure_ascii=False),
        ]
        self._save_text(artifact_path, "\n".join(report))
        stage_state["artifact_paths"] = [artifact_path]
        stage_state["summary"] = result.get("message") or result.get("status") or "Delivery prepared"
        stage_state["verdict"] = "PASS" if result.get("success") or result.get("status") in {"disabled", "unavailable"} else "FAIL"
        stage_state["status"] = "passed" if stage_state["verdict"] == "PASS" else "failed"
        stage_state["ended_at"] = datetime.now().isoformat()
        context[stage] = {"summary": stage_state["summary"], "artifact_paths": [artifact_path]}
        self._persist_runtime()
        self._write_run_metadata(task)
        self._set_agent_status("delivery-manager", "idle", None, stage, stage_state["summary"])
        self._emit("stage_completed", "Delivery stage finished", source="pipeline", task_id=task["id"], stage=stage, data=result)
        return stage_state["verdict"] == "PASS"

    def _run_build_verification_stage(self, task: Dict, context: Dict) -> bool:
        stage = "build_verification"
        stage_state = task["stages"][stage]
        stage_state["status"] = "running"
        stage_state["started_at"] = datetime.now().isoformat()
        self._set_agent_status("build-verifier", "running", task["id"], stage, "Running build verification")
        result = self.build_verifier.run(task["id"], self.settings["target_repo"])
        report_path = os.path.join(task["run_dir"], "reports", "build_verification.json")
        self._save_json(report_path, result)
        stage_state["artifact_paths"] = [report_path]
        stage_state["summary"] = result.get("message", "Build verification completed")
        stage_state["verdict"] = "PASS" if result.get("success") else "FAIL"
        stage_state["status"] = "passed" if result.get("success") else "failed"
        stage_state["ended_at"] = datetime.now().isoformat()
        context[stage] = {"summary": stage_state["summary"], "artifact_paths": [report_path], "hil": self.hil.describe_capabilities()}
        self._persist_runtime()
        self._write_run_metadata(task)
        self._set_agent_status("build-verifier", "idle", None, stage, stage_state["summary"])
        self._emit("stage_completed", "Build verification stage finished", source="pipeline", task_id=task["id"], stage=stage, data=result, level="success" if result.get("success") else "error")
        return bool(result.get("success"))

    def _requires_manual_gate(self, task: Dict, stage: str) -> bool:
        if stage not in {"design", "delivery"}:
            return False
        text = task["request_text"].lower()
        return any(keyword in text for keyword in HUMAN_KEYWORDS)

    def _create_approval(self, task: Dict, stage: str, reason: str) -> Dict:
        approval = {"id": f"approval-{uuid.uuid4().hex[:8]}", "stage": stage, "reason": reason, "status": "pending", "created_at": datetime.now().isoformat()}
        with self.lock:
            task["approvals"].append(approval)
            task["status"] = "waiting_human"
            task["updated_at"] = datetime.now().isoformat()
            self._persist_runtime()
        self._write_handoff(task)
        self._emit("approval_required", reason, source="system", task_id=task["id"], stage=stage, level="warning", data={"approval_id": approval["id"]})
        self.engine.add_alert("warning", stage, reason, action_required=True)
        return approval

    def _wait_for_approval(self, task: Dict, approval: Dict) -> bool:
        while self.running:
            with self.lock:
                current = self._require_task(task["id"])
                for candidate in current.get("approvals", []):
                    if candidate["id"] == approval["id"]:
                        if candidate["status"] == "approved":
                            return True
                        if candidate["status"] == "rejected":
                            return False
            time.sleep(1)
        return False

    def _write_handoff(self, task: Dict) -> None:
        """Persist a HANDOFF.json snapshot so retry/resume has full context."""
        task_dir = os.path.join(self.tasks_dir, task["id"])
        os.makedirs(task_dir, exist_ok=True)
        completed = [
            s for s in self.pipeline_order
            if task["stages"].get(s, {}).get("status") in ("passed", "completed")
        ]
        handoff = {
            "task_id": task["id"],
            "title": task["title"],
            "paused_at": datetime.now().isoformat(),
            "paused_stage": task.get("current_stage"),
            "completed_stages": completed,
            "context_snapshot": {s: v for s, v in task.get("context", {}).items()},
            "resume_hint": (
                f"Resume from {task.get('current_stage')} stage. "
                f"{len(completed)} prior stage(s) are locked and must not be repeated."
            ),
        }
        self._save_json(os.path.join(task_dir, "HANDOFF.json"), handoff)

    def _fail_task(self, task: Dict, reason: str) -> None:
        self._write_handoff(task)
        failed_stage = task.get("current_stage", "unknown")
        with self.lock:
            task["status"] = "failed"
            task["updated_at"] = datetime.now().isoformat()
            self.runtime["current_task_id"] = None
            self._persist_runtime()
        self._write_run_metadata(task, final_status="failed", failure_reason=reason)
        self.engine.add_alert("critical", failed_stage, reason, action_required=True)
        self._emit("task_failed", reason, source="pipeline", task_id=task["id"], level="error")
        self._notify_task_update(task, f"Task failed: {reason}")
        
        # 提取失败经验教训到记忆系统
        try:
            self.memory_extractor.extract_from_failed_task(task, failed_stage, reason)
        except Exception as e:
            self._emit("memory_error", f"Failed to extract lesson: {e}", source="memory", level="warning")

    def retry_task(self, task_id: str) -> Dict:
        """Resume a failed task from the failed stage, keeping passed stages intact."""
        with self.lock:
            task = self._require_task(task_id)
            task_pipeline_order = self._task_pipeline_order(task)
            if task["status"] != "failed":
                raise ValueError(f"Task {task_id} is not failed (status={task['status']})")

            # Find the first non-passed stage to resume from
            resume_stage = None
            for stage_id in task_pipeline_order:
                stage_data = task["stages"].get(stage_id, {})
                if stage_data.get("status") not in ("passed", "completed"):
                    resume_stage = stage_id
                    break

            # Reset the failed stage and all stages after it
            found = False
            for stage_id in task_pipeline_order:
                if stage_id == resume_stage:
                    found = True
                if found:
                    task["stages"][stage_id] = {
                        "title": STAGE_TITLES.get(stage_id, stage_id),
                        "status": "pending",
                        "agent_id": STAGE_TO_AGENT.get(stage_id, "planner"),
                        "attempts": 0,
                        "summary": "",
                        "verdict": None,
                        "started_at": None,
                        "ended_at": None,
                        "artifact_paths": [],
                        "logs": [],
                    }
                    # Remove context for reset stages so they get fresh runs
                    task["context"].pop(stage_id, None)

            task["status"] = "queued"
            task["current_stage"] = resume_stage or task_pipeline_order[0]
            task["updated_at"] = datetime.now().isoformat()
            self._persist_runtime()

        passed = [s for s in task_pipeline_order if task["stages"].get(s, {}).get("status") in ("passed", "completed")]
        self._emit("task_retried", f"Task resumed from {resume_stage} ({len(passed)} stages kept)", source="system", task_id=task_id)
        return task

    def delete_task(self, task_id: str) -> None:
        """Remove a task from the runtime state."""
        with self.lock:
            task = self._require_task(task_id)
            if task["status"] == "running":
                raise ValueError(f"Cannot delete a running task")
            self.runtime["tasks"] = [t for t in self.runtime["tasks"] if t["id"] != task_id]
            self._persist_runtime()
        self._emit("task_deleted", f"Task {task_id} deleted", source="system", task_id=task_id)

    def _complete_task(self, task: Dict) -> None:
        processed_src = os.path.join(self.specs_pending, task["spec_file"])
        processed_dst = os.path.join(self.specs_processed, task["spec_file"])
        if os.path.exists(processed_src):
            shutil.move(processed_src, processed_dst)

        with self.lock:
            task["status"] = "completed"
            task["completed_at"] = datetime.now().isoformat()
            task["updated_at"] = task["completed_at"]
            self.runtime["current_task_id"] = None
            self._persist_runtime()
        self._write_run_metadata(task, final_status="completed")
        self.engine.transition("all_pass")
        self._emit("task_completed", f"Task completed: {task['title']}", source="pipeline", task_id=task["id"], level="success")
        self._notify_task_update(task, f"Task completed: {task['title']}")
        
        # 提取任务摘要到记忆系统
        try:
            self.memory_extractor.extract_from_completed_task(task)
        except Exception as e:
            self._emit("memory_error", f"Failed to extract task summary: {e}", source="memory", level="warning")

    def _notify_task_update(self, task: Dict, text: str) -> None:
        chat_id = task.get("source_metadata", {}).get("chat_id")
        if task["source"] == "feishu" and chat_id:
            self.feishu.send_text(chat_id, text)

    def _stage_max_retries(self, stage: str) -> int:
        """Get max retry count for a stage. Default is 2 for all stages."""
        stage_config = next((item for item in self.pipeline_config.get("stages", []) if item.get("id") == stage), {})
        # Default: 2 retries for all stages (can be overridden in pipeline config)
        return int(stage_config.get("max_retries", 2))

    def _record_agent_event(self, task: Dict, stage: str, agent_id: str, event: Dict) -> None:
        event_type = event.get("type", "")
        text = (event.get("text") or "").strip()

        # Only surface events that carry meaningful content for the UI.
        # Skip: system init, empty assistant chunks, user/permission prompts, bare type labels.
        if not text or event_type in ("system", "user"):
            return
        # Skip if the "message" is just the event type name (e.g. "assistant")
        message = event.get("message") or text
        if message in ("assistant", "system", "user", "result"):
            message = text

        # Truncate very long messages for the feed (full text stays in logs)
        feed_message = message[:300] + ("…" if len(message) > 300 else "")

        with self.lock:
            task_stage = task["stages"].setdefault(stage, self._empty_stage_map().get(stage, {}))
            now = datetime.now().isoformat()
            task["updated_at"] = now
            task_stage["last_event_at"] = now
            task_stage.setdefault("logs", []).append({"timestamp": datetime.now().isoformat(), "message": message})
            task_stage["logs"] = task_stage["logs"][-50:]
            self._persist_runtime()
        self._emit("agent_event", feed_message, source=agent_id, task_id=task["id"], stage=stage, data={"agent_id": agent_id})

    def _set_agent_status(self, agent_id: str, status: str, task_id: Optional[str], stage: Optional[str], message: str) -> None:
        agent = self.agents[agent_id]
        agent["status"] = status
        agent["current_task_id"] = task_id
        agent["last_stage"] = stage
        agent["last_message"] = message
        if status == "idle" and task_id is None and stage:
            agent["completed_tasks"] += 1

    # Stage-level XML prompt specs: (action, expected_files, done_criteria)
    _STAGE_SPECS = {
        "intake": (
            "Produce a concise intake summary and identify risky areas.",
            "Intake summary",
            "Summary written, risky areas identified.",
        ),
        "planning": (
            "Break the request into a sprint contract with clear subtasks, dependencies, and definition of done.",
            "Sprint contract with subtasks and dependencies",
            "Sprint contract complete.",
        ),
        "requirements": (
            "Write a traceable requirement spec with unique F-numbers (F001, F002…), "
            "Given/When/Then acceptance criteria, and quantified non-functional constraints. "
            "No vague terms like 'fast' or 'suitable'.",
            "requirements_spec.md",
            "Every Fxxx has at least one AC. All NFRs have numeric thresholds.",
        ),
        "design": (
            "Create an implementation design covering architecture, APIs, data flow, observability, "
            "and recovery paths. Every design decision MUST trace back to a requirement ID [REQ-Fxxx].",
            "design/architecture.md, design/api_design.md, design/data_model.md",
            "All decisions have requirement traceability. Every API has Request/Response/Error codes.",
        ),
        "development": (
            "Implement the feature in the target repo following the design docs exactly. "
            "API paths, field names, and error codes must match design/api_design.md precisely. "
            "Core modules require ≥80% unit test coverage.",
            "src/ (source code), tests/cases/ (unit tests)",
            "Code matches design docs. Lint passes. Core modules have ≥80% test coverage.",
        ),
        "code_review": (
            "Review the latest changes critically against design docs and requirements. "
            "End your report with VERDICT: PASS, FAIL, or NEED_HUMAN.",
            "Code review report",
            "VERDICT declared.",
        ),
        "security_review": (
            "Review for security issues: secrets exposure, auth bypass, injection vectors, "
            "unsafe side effects. End with VERDICT: PASS, FAIL, or NEED_HUMAN.",
            "Security review report",
            "VERDICT declared.",
        ),
        "safety_review": (
            "Review ISO 26262, AUTOSAR, OTA rollback safety, WP.29, and vehicle-side functional safety impacts. "
            "End with VERDICT: PASS, FAIL, or NEED_HUMAN.",
            "Safety review report",
            "VERDICT declared.",
        ),
        "testing": (
            "First check <adb_probe><status> in context.\n"
            "--- IF status=connected ---\n"
            "Execute REAL on-device IVI integration tests on the connected 台架 using:\n"
            "  .claude/skills/ivi-integration-test/scripts/adb_runner.py   (device connection, logcat, screenshots)\n"
            "  .claude/skills/ivi-integration-test/scripts/hmi_helper.py   (HMI interaction via UIAutomator)\n"
            "  .claude/skills/ivi-integration-test/scripts/perf_capture.py (startup/FPS/memory/CPU)\n"
            "Follow the 5-step workflow in .claude/skills/ivi-integration-test/SKILL.md.\n"
            "Collect logcat to tests/reports/logcat/, screenshots to tests/reports/screenshots/.\n"
            "Write tests/reports/ivi_test_report.md using the report_template.md format.\n"
            "--- IF status=not_connected ---\n"
            "Design test cases (Happy Path, Sad Path, Boundary) for every Fxxx requirement.\n"
            "Write tests/cases/test_plan.md with TC-xxx | precondition | steps | expected | priority.\n"
            "Write tests/reports/test_report.md with execution summary, pass rate, defect list.\n"
            "--- BOTH modes ---\n"
            "End with VERDICT: PASS, FAIL, or NEED_HUMAN.",
            "tests/cases/, tests/reports/ivi_test_report.md (IVI) or tests/reports/test_report.md (standard)",
            "VERDICT declared. All Fxxx requirements have at least one test case.",
        ),
        "build_verification": (
            "Summarize CI build, static analysis, SBOM, and signing checks. End with VERDICT: PASS or FAIL.",
            "Build verification report",
            "VERDICT declared.",
        ),
    }

    def _build_prompt(self, task: Dict, stage: str, context: Dict, retry_info: Optional[Dict] = None) -> str:
        task_dir = os.path.join(self.tasks_dir, task["id"])

        # Load locked decisions persisted in CONTEXT.md
        locked_decisions = self.distiller.load_locked_decisions(task_dir)

        # Build distilled snapshot from completed prior stages
        completed_stages = [
            s for s in self.pipeline_order
            if s != stage and s in context
        ]
        snapshot = self.distiller.build_task_context_snapshot(task, completed_stages)

        # Render prior stages as XML
        prior_stages_xml = ""
        for s, s_data in snapshot.items():
            handoff = s_data.get("handoff_summary", "")
            decisions = s_data.get("key_decisions", [])
            decisions_xml = ""
            if decisions:
                items = "\n".join(
                    f"        - {d.get('id','?')}: {d.get('description','')}"
                    if isinstance(d, dict) else f"        - {d}"
                    for d in decisions
                )
                decisions_xml = f"\n      <decisions>\n{items}\n      </decisions>"
            prior_stages_xml += (
                f"\n    <stage name=\"{s}\">"
                f"\n      <summary>{handoff}</summary>"
                f"{decisions_xml}"
                f"\n    </stage>"
            )

        locked_section = (
            f"\n  <locked_decisions>\n{locked_decisions}\n  </locked_decisions>"
            if locked_decisions else ""
        )

        # Inject memory context (historical experience)
        memory_xml = ""
        try:
            agent_id = STAGE_TO_AGENT.get(stage, stage)
            memory_ctx = self.memory_injector.build_memory_context(stage, task["request_text"], agent_id)
            if memory_ctx:
                memory_xml = f"\n  <memory>\n{self.memory_injector.format_for_prompt(memory_ctx)}\n  </memory>"
        except Exception:
            pass  # Memory injection is optional

        # Retry context
        retry_xml = ""
        if retry_info:
            retry_xml = (
                f"\n  <retry>"
                f"\n    <attempt>{retry_info['attempt']} of {retry_info['max_retries']}</attempt>"
                f"\n    <previous_summary>{retry_info['previous_summary']}</previous_summary>"
                f"\n    <previous_verdict>{retry_info['previous_verdict']}</previous_verdict>"
                f"\n    <instruction>Address the issues from the previous attempt.</instruction>"
                f"\n  </retry>"
            )

        # ADB probe section — injected for the testing stage only
        adb_section = ""
        if stage == "testing" and "adb_probe" in context:
            probe = context["adb_probe"]
            status = "connected" if probe.get("connected") else "not_connected"
            serial = probe.get("serial") or ""
            count = probe.get("device_count", 0)
            raw = probe.get("devices_output", "")
            adb_section = (
                f"\n  <adb_probe>"
                f"\n    <status>{status}</status>"
                f"\n    <serial>{serial}</serial>"
                f"\n    <device_count>{count}</device_count>"
                f"\n    <raw_output>{raw}</raw_output>"
                f"\n  </adb_probe>"
            )

        action, files, done = self._STAGE_SPECS.get(
            stage,
            (f"Complete the {stage} stage.", "Stage output", "Stage complete."),
        )

        return (
            f"<task>\n"
            f"  <id>{task['id']}</id>\n"
            f"  <title>{task['title']}</title>\n"
            f"  <stage>{stage}</stage>\n"
            f"  <request>\n{task['request_text']}\n  </request>\n"
            f"  <context>{locked_section}\n"
            f"    <prior_stages>{prior_stages_xml}\n    </prior_stages>\n"
            f"  </context>"
            f"{memory_xml}"
            f"{retry_xml}"
            f"{adb_section}\n"
            f"  <action>\n{action}\n  </action>\n"
            f"  <files>{files}</files>\n"
            f"  <done>{done}</done>\n"
            f"</task>"
        )

    def _extract_req_ids(self, text: str) -> List[str]:
        """Extract F-number requirement IDs from text."""
        import re as _re
        return list(dict.fromkeys(_re.findall(r'F\d{3}', text)))

    def _summarize_result(self, stage: str, output_text: str, verdict: Optional[str]) -> tuple[str, str]:
        lines = [line.strip() for line in output_text.splitlines() if line.strip()]
        summary = " ".join(lines[:4])[:500] if lines else f"{stage} completed"
        if verdict is None:
            verdict = "PASS"
        return summary, verdict

    def _write_transcript(self, task: Dict, stage: str, result) -> str:
        transcript_path = os.path.join(task["run_dir"], "transcripts", f"{stage}.json")
        payload = {
            "task_id": task["id"],
            "stage": stage,
            "command": result.command,
            "return_code": result.return_code,
            "success": result.success,
            "verdict": result.verdict,
            "output_text": result.output_text,
            "error": result.error,
            "duration_seconds": result.duration_seconds,
            "transcript": result.transcript,
        }
        self._save_json(transcript_path, payload)
        return transcript_path

    def _materialize_stage_artifacts(self, task: Dict, stage: str, summary: str, output_text: str, transcript_path: str) -> List[str]:
        task_dir = os.path.join(self.tasks_dir, task["id"])
        os.makedirs(task_dir, exist_ok=True)
        artifact_paths = [transcript_path]
        run_dir = task["run_dir"]

        if stage == "planning":
            path = os.path.join(run_dir, "planning", "sprint_contract.md")
            self._save_text(path, f"# Sprint Contract - {task['title']}\n\n{output_text}\n")
            artifact_paths.append(path)
        elif stage == "requirements":
            path = os.path.join(run_dir, "requirements", "requirements_spec.md")
            content = self._wrap_output(task, stage, output_text)
            self._save_text(path, content)
            copy_path = os.path.join(task_dir, "requirements_spec.md")
            self._save_text(copy_path, content)
            artifact_paths.extend([path, copy_path])
        elif stage == "design":
            architecture = os.path.join(run_dir, "design", "architecture.md")
            api = os.path.join(run_dir, "design", "api_design.md")
            data_model = os.path.join(run_dir, "design", "data_model.md")
            self._save_text(architecture, self._wrap_output(task, stage, output_text, heading="Architecture"))
            self._save_text(api, self._design_api_content(task, output_text))
            self._save_text(data_model, self._design_data_content(task, output_text))
            artifact_paths.extend([architecture, api, data_model])
        elif stage == "testing":
            path = os.path.join(run_dir, "tests", "reports", "test_report.md")
            self._save_text(path, self._wrap_output(task, stage, output_text))
            self._snapshot_repo_tree("tests", os.path.join(run_dir, "tests", "workspace_snapshot"))
            artifact_paths.append(path)
        elif stage == "development":
            path = os.path.join(run_dir, "src", f"{stage}.md")
            self._save_text(path, self._wrap_output(task, stage, output_text))
            artifact_paths.append(path)
            self._snapshot_repo_tree("src", os.path.join(run_dir, "src", "workspace_snapshot"))
            self._snapshot_repo_tree("tests", os.path.join(run_dir, "tests", "workspace_snapshot"))
            for scan_dir in ["src", "tests"]:
                abs_dir = os.path.join(self.harness_dir, scan_dir)
                if os.path.isdir(abs_dir):
                    artifact_paths.append(abs_dir)
        else:
            path = os.path.join(run_dir, stage, f"{stage}.md")
            self._save_text(path, self._wrap_output(task, stage, output_text))
            artifact_paths.append(path)

        task["artifacts"][stage] = artifact_paths
        self._persist_runtime()
        self._write_run_metadata(task)
        return artifact_paths

    def _post_stage_processing(self, task: Dict, stage: str, summary: str, artifact_paths: List[str]) -> None:
        if stage in {"requirements", "design", "testing"}:
            for path in artifact_paths:
                if path.endswith(".md") and os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as handle:
                        content = handle.read()
                    try:
                        distilled = self.distiller.distill(stage, content, os.path.basename(path))
                        task["context"][stage] = {"handoff_summary": distilled.handoff_summary, "compression_ratio": distilled.compression_ratio}
                        # Save locked decisions to CONTEXT.md so later stages see them
                        if distilled.key_decisions:
                            task_dir = os.path.join(self.tasks_dir, task["id"])
                            self.distiller.save_locked_decisions(task_dir, stage, distilled.key_decisions)
                    except Exception as exc:
                        task["context"].setdefault(stage, {})["distill_error"] = str(exc)
                    break

        # Append requirement-level knowledge threads for cross-task reuse
        if stage in {"requirements", "design"}:
            req_ids = self._extract_req_ids(summary)
            for req_id in req_ids[:5]:
                try:
                    self.distiller.append_thread(req_id, stage, summary[:300])
                except Exception:
                    pass

        if stage in {"design", "testing"}:
            try:
                report = self.consistency_checker.run_all_checks()
                report_path = os.path.join(self.report_dir, f"{task['id']}-{stage}-consistency.json")
                self._save_json(report_path, report)
                task["artifacts"].setdefault(stage, []).append(report_path)
            except Exception as exc:
                task["context"].setdefault(stage, {})["consistency_error"] = str(exc)

        if stage == "requirements":
            try:
                impact = self.change_impact_analyzer.analyze_change(task["request_text"])
                path = os.path.join(self.report_dir, f"{task['id']}-change-impact.md")
                self._save_text(path, impact.analysis_details)
                task["artifacts"].setdefault(stage, []).append(path)
            except Exception as exc:
                task["context"].setdefault(stage, {})["impact_error"] = str(exc)

        self._persist_runtime()
        self._write_run_metadata(task)

    def _ensure_run_layout(self, task_id: str) -> str:
        run_dir = os.path.join(self.runs_dir, task_id)
        for rel in ["requirements", "design", "src", "tests/reports", "planning", "reports", "transcripts", "delivery", "build_verification", "safety_review"]:
            os.makedirs(os.path.join(run_dir, rel), exist_ok=True)
        return run_dir

    def _update_latest_run_link(self, run_dir: str) -> None:
        latest = os.path.join(self.runs_dir, "latest")
        if os.path.lexists(latest):
            os.remove(latest)
        os.symlink(run_dir, latest)

    def _write_run_metadata(self, task: Dict, final_status: Optional[str] = None, failure_reason: str = "") -> None:
        payload = {
            "task_id": task["id"],
            "title": task["title"],
            "source": task["source"],
            "spec_file": task["spec_file"],
            "run_dir": task["run_dir"],
            "status": final_status or task["status"],
            "current_stage": task.get("current_stage"),
            "failure_reason": failure_reason,
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"),
            "budget": self.engine.check_budget(),
            "stages": task.get("stages", {}),
            "artifacts": task.get("artifacts", {}),
        }
        self._save_json(os.path.join(task["run_dir"], "meta.json"), payload)

    def _snapshot_repo_tree(self, relative_dir: str, destination_dir: str) -> None:
        source_dir = os.path.join(self.harness_dir, relative_dir)
        if not os.path.isdir(source_dir):
            return
        if os.path.exists(destination_dir):
            shutil.rmtree(destination_dir)
        shutil.copytree(
            source_dir,
            destination_dir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )

    def _agent_identity(self, agent_id: str) -> Optional[str]:
        identity = self.agent_identities.get(agent_id)
        return identity if isinstance(identity, str) and identity.strip() else None

    def _wrap_output(self, task: Dict, stage: str, output_text: str, heading: Optional[str] = None) -> str:
        title = heading or STAGE_TITLES.get(stage, stage)
        return "\n".join([f"# {title} - {task['title']}", "", f"Generated at: {datetime.now().isoformat()}", "", output_text.strip() or f"No direct output captured for {stage}."])

    def _design_api_content(self, task: Dict, output_text: str) -> str:
        return "\n".join([
            f"# API Design - {task['title']}",
            "",
            "## Suggested Endpoints",
            "- POST /api/requests",
            "- POST /api/feishu/webhook",
            "- GET /api/stream",
            "- POST /api/approvals/{taskId}/{approvalId}/resolve",
            "",
            "## Notes",
            output_text.strip() or "Refer to realtime orchestration and approval APIs.",
        ])

    def _design_data_content(self, task: Dict, output_text: str) -> str:
        return "\n".join([
            f"# Data Model - {task['title']}",
            "",
            "## Runtime Entities",
            "- Task",
            "- StageRecord",
            "- Approval",
            "- Event",
            "- DeliveryRecord",
            "",
            "## Mermaid",
            "```mermaid",
            "erDiagram",
            "  TASK ||--o{ STAGE_RECORD : contains",
            "  TASK ||--o{ APPROVAL : waits_on",
            "  TASK ||--o{ EVENT : emits",
            "```",
            "",
            output_text.strip(),
        ])

    def _emit(self, event_type: str, message: str, source: str = "system", task_id: Optional[str] = None, stage: Optional[str] = None, data: Optional[Dict] = None, level: str = "info") -> None:
        self.event_bus.publish(event_type, message, source=source, data=data, task_id=task_id, stage=stage, level=level)
        if level == "error":
            self.engine._log_error(message, stage=stage)
        else:
            self.engine._log_activity(message, stage=stage)


def create_api_app(runner: PipelineRunner) -> Flask:
    app = Flask(__name__, static_folder=None)
    template_dir = os.path.abspath(os.path.join(runner.harness_dir, "dashboard", "templates"))

    @app.route("/")
    def index():
        return send_from_directory(template_dir, "index.html")

    @app.route("/api/runtime")
    def api_runtime():
        return jsonify(runner.get_runtime_snapshot())

    @app.route("/api/tasks")
    def api_tasks():
        return jsonify(runner.get_runtime_snapshot()["tasks"])

    @app.route("/api/tasks/<task_id>", methods=["GET", "DELETE"])
    def api_task(task_id: str):
        if request.method == "DELETE":
            try:
                runner.delete_task(task_id)
                return jsonify({"ok": True})
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
        return jsonify(runner._require_task(task_id))

    @app.route("/api/tasks/<task_id>/retry", methods=["POST"])
    def api_retry_task(task_id: str):
        try:
            task = runner.retry_task(task_id)
            return jsonify(task)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/tasks/<task_id>/artifacts")
    def api_task_artifacts(task_id: str):
        task = runner._require_task(task_id)
        result = {}
        for stage, paths in task.get("artifacts", {}).items():
            items = []
            for p in paths:
                name = os.path.basename(p)
                content = ""
                if os.path.isfile(p):
                    try:
                        with open(p, "r", encoding="utf-8", errors="replace") as fh:
                            content = fh.read(50000)  # cap at 50KB
                    except Exception:
                        content = "(unable to read)"
                items.append({"path": p, "name": name, "content": content})
            result[stage] = items
        return jsonify(result)

    @app.route("/api/requests", methods=["POST"])
    def api_submit_request():
        payload = request.get_json(force=True, silent=True) or {}
        text = (payload.get("text") or "").strip()
        if not text:
            return jsonify({"error": "text is required"}), 400
        task = runner.submit_request(text=text, title=payload.get("title"), source=payload.get("source", "web"), metadata=payload.get("metadata"))
        return jsonify(task), 201

    @app.route("/api/feishu/webhook", methods=["POST"])
    def api_feishu_webhook():
        raw_body = request.get_data(cache=False) or b"{}"
        validation = runner.feishu.validate_webhook(raw_body, dict(request.headers), remote_addr=request.remote_addr or "unknown")
        if not validation.get("ok"):
            return jsonify({"error": validation.get("error"), "dedup_key": validation.get("dedup_key")}), int(validation.get("status", 400))
        payload = validation.get("payload") or {}
        extracted = runner.feishu.extract_request(payload)
        if not extracted.get("text"):
            return jsonify({"error": "Unable to extract request text from Feishu payload"}), 400
        task = runner.submit_request(text=extracted["text"], title=extracted.get("title"), source="feishu", metadata={"chat_id": extracted.get("chat_id"), "sender": extracted.get("sender")})
        return jsonify({"ok": True, "task_id": task["id"]})

    @app.route("/api/approvals")
    def api_approvals():
        return jsonify(runner.get_runtime_snapshot()["approvals"])

    @app.route("/api/approvals/<task_id>/<approval_id>/resolve", methods=["POST"])
    def api_resolve_approval(task_id: str, approval_id: str):
        payload = request.get_json(force=True, silent=True) or {}
        resolution = payload.get("resolution")
        if resolution not in {"approved", "rejected"}:
            return jsonify({"error": "resolution must be approved or rejected"}), 400
        approval = runner.resolve_approval(task_id, approval_id, resolution, payload.get("note", ""))
        return jsonify(approval)

    @app.route("/api/control/<action>", methods=["POST"])
    def api_control(action: str):
        if action == "pause":
            runner.pause()
        elif action == "resume":
            runner.resume()
        else:
            return jsonify({"error": "unsupported action"}), 400
        return jsonify({"ok": True, "action": action})

    @app.route("/api/settings", methods=["GET", "POST"])
    def api_settings():
        if request.method == "GET":
            return jsonify(runner.settings)
        payload = request.get_json(force=True, silent=True) or {}
        settings = runner.update_settings(payload)
        return jsonify(settings)

    @app.route("/api/pipeline", methods=["GET", "POST"])
    def api_pipeline():
        if request.method == "GET":
            is_custom = os.path.exists(runner.custom_pipeline_file)
            return jsonify({
                "stages": runner.pipeline_config.get("stages", []),
                "default_stages": runner.default_pipeline_config.get("stages", []),
                "order": runner.pipeline_order,
                "is_custom": is_custom,
            })
        payload = request.get_json(force=True, silent=True) or {}
        new_stages = payload.get("stages", [])
        if not new_stages:
            return jsonify({"error": "stages list is required"}), 400
        # 验证所有 stage 有对应的 agent 和 title
        stage_ids = [s.get("id") for s in new_stages if s.get("id")]
        invalid_stages = [s for s in stage_ids if s not in STAGE_TO_AGENT or s not in STAGE_TITLES]
        if invalid_stages:
            return jsonify({"error": f"Unknown stage IDs: {invalid_stages}. Valid stages: {list(STAGE_TO_AGENT.keys())}"}), 400
        # Save to custom file, never touch pipeline.yaml
        runner.pipeline_config = {"stages": new_stages}
        runner.pipeline_order = runner._resolve_pipeline_order()
        if yaml:
            with open(runner.custom_pipeline_file, "w", encoding="utf-8") as fh:
                yaml.dump(runner.pipeline_config, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)
        runner._emit("pipeline_updated", f"Custom pipeline saved: {len(new_stages)} stages", source="system")
        return jsonify({"stages": new_stages, "order": runner.pipeline_order, "is_custom": True})

    @app.route("/api/pipeline/reset", methods=["POST"])
    def api_pipeline_reset():
        """Delete custom pipeline, revert to system default."""
        if os.path.exists(runner.custom_pipeline_file):
            os.remove(runner.custom_pipeline_file)
        runner.pipeline_config = dict(runner.default_pipeline_config)
        runner.pipeline_order = runner._resolve_pipeline_order()
        runner._emit("pipeline_reset", "Pipeline reverted to system default", source="system")
        return jsonify({"stages": runner.pipeline_config.get("stages", []), "order": runner.pipeline_order, "is_custom": False})

    @app.route("/api/events")
    def api_events():
        since = request.args.get("since", 0, type=int)
        return jsonify(runner.event_bus.since(since))

    @app.route("/api/stream")
    def api_stream():
        last_seq = request.args.get("since", 0, type=int)

        def generate():
            nonlocal last_seq
            while True:
                events = runner.event_bus.since(last_seq)
                if events:
                    for event in events:
                        last_seq = max(last_seq, int(event["seq"]))
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                else:
                    yield ": keepalive\n\n"
                time.sleep(1)

        return Response(generate(), mimetype="text/event-stream")

    # ==================== Memory APIs ====================
    
    @app.route("/api/memory/history")
    def api_memory_history():
        """获取任务历史"""
        limit = request.args.get("limit", 50, type=int)
        status = request.args.get("status")
        since = request.args.get("since")
        summaries = runner.memory_store.get_task_history(limit=limit, status=status, since=since)
        return jsonify([{
            "task_id": s.task_id,
            "title": s.title,
            "request_text": s.request_text[:200],
            "status": s.status,
            "duration_seconds": s.duration_seconds,
            "total_tokens": s.total_tokens,
            "stages_passed": s.stages_passed,
            "stages_failed": s.stages_failed,
            "tags": s.tags,
            "created_at": s.created_at,
            "completed_at": s.completed_at,
        } for s in summaries])

    @app.route("/api/memory/statistics")
    def api_memory_statistics():
        """获取任务统计"""
        return jsonify(runner.memory_store.get_task_statistics())

    @app.route("/api/memory/lessons")
    def api_memory_lessons():
        """获取经验教训"""
        stage = request.args.get("stage")
        limit = request.args.get("limit", 20, type=int)
        if stage:
            lessons = runner.memory_store.get_lessons_for_stage(stage, limit=limit)
        else:
            lessons = runner.memory_store.get_all_lessons(limit=limit)
        return jsonify([{
            "lesson_id": l.lesson_id,
            "task_id": l.task_id,
            "stage": l.stage,
            "failure_type": l.failure_type,
            "failure_summary": l.failure_summary,
            "root_cause": l.root_cause,
            "prevention_strategy": l.prevention_strategy,
            "created_at": l.created_at,
        } for l in lessons])

    @app.route("/api/memory/project")
    def api_memory_project():
        """获取项目记忆"""
        category = request.args.get("category")
        limit = request.args.get("limit", 20, type=int)
        memories = runner.memory_store.get_project_memories(category=category, limit=limit)
        return jsonify([{
            "memory_id": m.memory_id,
            "category": m.category,
            "content": m.content,
            "confidence": m.confidence,
            "usage_count": m.usage_count,
            "created_at": m.created_at,
        } for m in memories])

    @app.route("/api/memory/import", methods=["POST"])
    def api_memory_import():
        """从现有任务导入历史记录"""
        imported = 0
        for task in runner.runtime.get("tasks", []):
            if task.get("status") in ("completed", "failed"):
                try:
                    runner.memory_extractor.extract_from_completed_task(task)
                    imported += 1
                except Exception:
                    pass
        return jsonify({"imported": imported})

    @app.route("/api/health")
    def api_health():
        return jsonify({"ok": True, "running": runner.running, "paused": runner.paused})

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Harness orchestration service")
    parser.add_argument("--harness-dir", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parser.add_argument("--web-port", default=8080, type=int)
    parser.add_argument("--once", action="store_true", help="Process a single queued task and exit")
    args = parser.parse_args()

    runner = PipelineRunner(args.harness_dir)
    runner.start()

    def shutdown(*_args):
        runner.stop()
        os._exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    if args.once:
        deadline = time.time() + 120
        while time.time() < deadline:
            if runner.runtime.get("current_task_id") is None and runner._next_queued_task() is None:
                break
            time.sleep(1)
        runner.stop()
        return

    app = create_api_app(runner)
    app.run(host="0.0.0.0", port=args.web_port, threaded=True)


if __name__ == "__main__":
    main()