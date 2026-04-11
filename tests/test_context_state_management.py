from __future__ import annotations

from pathlib import Path

from engine.integrations import AgentRunResult
from engine.pipeline_runner import PipelineRunner


def make_runner(tmp_path: Path) -> PipelineRunner:
    (tmp_path / "agents").mkdir(parents=True, exist_ok=True)
    return PipelineRunner(str(tmp_path))


def test_submit_request_creates_state_and_handoff_artifacts(tmp_path: Path):
    runner = make_runner(tmp_path)

    task = runner.submit_request("Implement login flow", title="Login")
    run_dir = Path(task["run_dir"])

    state_path = run_dir / "STATE.md"
    handoff_path = run_dir / "HANDOFF.json"

    assert state_path.exists()
    assert handoff_path.exists()
    assert "Task State" in state_path.read_text(encoding="utf-8")
    assert '"next_action"' in handoff_path.read_text(encoding="utf-8")


def test_build_prompt_writes_context_snapshot_and_uses_distilled_context(tmp_path: Path):
    runner = make_runner(tmp_path)
    task = runner.submit_request("Implement login flow", title="Login")

    task["context"]["requirements"] = {
        "handoff_summary": "REQ-001 login must support password auth and emit audit logs.",
    }
    task["stages"]["requirements"].update(
        {
            "status": "passed",
            "summary": "A much longer raw summary that should not be preferred when a handoff summary exists.",
            "verdict": "PASS",
            "artifact_paths": [str(Path(task["run_dir"]) / "requirements" / "requirements_spec.md")],
        }
    )

    prompt = runner._build_prompt(task, "design", {"requirements": {"summary": task["stages"]["requirements"]["summary"], "verdict": "PASS", "artifact_paths": task["stages"]["requirements"]["artifact_paths"]}})

    context_snapshot = Path(task["run_dir"]) / "context" / "design.md"

    assert "REQ-001 login must support password auth" in prompt
    assert context_snapshot.exists()
    assert "## Task State" in context_snapshot.read_text(encoding="utf-8")


def test_prioritized_submit_requests_current_task_to_yield(tmp_path: Path):
    runner = make_runner(tmp_path)
    current = runner.submit_request("Finish the long-running refactor", title="Current")

    with runner.lock:
        current["status"] = "running"
        runner.runtime["current_task_id"] = current["id"]
        runner._persist_runtime()

    urgent = runner.submit_request("Ship the hotfix now", title="Urgent", prioritize=True)

    assert current["yield_requested"] is True
    assert urgent["title"] == "Urgent"
    assert runner._next_queued_task()["id"] == urgent["id"]


def test_resume_waiting_human_task_requeues_stage(tmp_path: Path):
    runner = make_runner(tmp_path)
    task = runner.submit_request("Review the risky change", title="Needs human")

    with runner.lock:
        task["status"] = "waiting_human"
        task["current_stage"] = "design"
        task["stages"]["design"]["status"] = "waiting_human"
        task["stages"]["design"]["started_at"] = "2026-04-11T10:00:00"
        task["stages"]["design"]["ended_at"] = "2026-04-11T10:05:00"
        runner._persist_runtime()

    resumed = runner.resume_task(task["id"], prioritize=True)

    assert resumed["status"] == "queued"
    assert resumed["stages"]["design"]["status"] == "pending"
    assert resumed["stages"]["design"]["started_at"] is None
    assert resumed["stages"]["design"]["ended_at"] is None
    assert runner._next_queued_task()["id"] == task["id"]


def test_interrupted_stage_returns_task_to_queue(tmp_path: Path):
    runner = make_runner(tmp_path)
    task = runner.submit_request("Handle the urgent rewrite", title="Interrupt me")

    with runner.lock:
        task["status"] = "running"
        task["current_stage"] = "requirements"
        runner.runtime["current_task_id"] = task["id"]
        runner._persist_runtime()

    runner.claude.run_agent = lambda **_: AgentRunResult(
        success=False,
        output_text="partial output",
        interrupted=True,
        interrupt_reason="Interrupted by scheduler",
    )

    completed = runner._run_stage_with_retries(task, "requirements", {"request_text": task["request_text"]})

    assert completed is False
    assert task["status"] == "queued"
    assert runner.runtime["current_task_id"] is None
    assert task["stages"]["requirements"]["status"] == "pending"
    assert task["stages"]["requirements"]["summary"] == "Interrupted by scheduler"


def test_pause_queued_task_keeps_it_out_of_scheduler(tmp_path: Path):
    runner = make_runner(tmp_path)
    task = runner.submit_request("Pause this before it starts", title="Queued task")

    paused = runner.pause_task(task["id"], reason="Pause before running")

    assert paused["status"] == "paused"
    assert runner._next_queued_task() is None


def test_interrupted_stage_can_pause_task(tmp_path: Path):
    runner = make_runner(tmp_path)
    task = runner.submit_request("Pause me mid-flight", title="Pause running")

    with runner.lock:
        task["status"] = "running"
        task["current_stage"] = "requirements"
        task["yield_requested"] = True
        task["yield_reason"] = "Pause requested"
        task["yield_target_status"] = "paused"
        runner.runtime["current_task_id"] = task["id"]
        runner._persist_runtime()

    runner.claude.run_agent = lambda **_: AgentRunResult(
        success=False,
        output_text="partial output",
        interrupted=True,
        interrupt_reason="Pause requested",
    )

    completed = runner._run_stage_with_retries(task, "requirements", {"request_text": task["request_text"]})

    assert completed is False
    assert task["status"] == "paused"
    assert runner.runtime["current_task_id"] is None
    assert task["stages"]["requirements"]["status"] == "pending"