from __future__ import annotations

from pathlib import Path

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