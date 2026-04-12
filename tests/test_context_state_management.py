from __future__ import annotations

import json
from pathlib import Path

import yaml

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

    task["context"]["software-requirement-orchestrator"] = {
        "handoff_summary": "REQ-001 login must support password auth and emit audit logs.",
    }
    task["stages"]["software-requirement-orchestrator"].update(
        {
            "status": "passed",
            "summary": "A much longer raw summary that should not be preferred when a handoff summary exists.",
            "verdict": "PASS",
            "artifact_paths": [str(Path(task["run_dir"]) / "software-requirement-orchestrator" / "requirements_spec.md")],
        }
    )

    prompt = runner._build_prompt(
        task,
        "cockpit-middleware-architect",
        {
            "software-requirement-orchestrator": {
                "summary": task["stages"]["software-requirement-orchestrator"]["summary"],
                "verdict": "PASS",
                "artifact_paths": task["stages"]["software-requirement-orchestrator"]["artifact_paths"],
            }
        },
    )

    context_snapshot = Path(task["run_dir"]) / "context" / "cockpit-middleware-architect.md"

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
        task["current_stage"] = "cockpit-middleware-architect"
        task["stages"]["cockpit-middleware-architect"]["status"] = "waiting_human"
        task["stages"]["cockpit-middleware-architect"]["started_at"] = "2026-04-11T10:00:00"
        task["stages"]["cockpit-middleware-architect"]["ended_at"] = "2026-04-11T10:05:00"
        runner._persist_runtime()

    resumed = runner.resume_task(task["id"], prioritize=True)

    assert resumed["status"] == "queued"
    assert resumed["stages"]["cockpit-middleware-architect"]["status"] == "pending"
    assert resumed["stages"]["cockpit-middleware-architect"]["started_at"] is None
    assert resumed["stages"]["cockpit-middleware-architect"]["ended_at"] is None
    assert runner._next_queued_task()["id"] == task["id"]


def test_interrupted_stage_returns_task_to_queue(tmp_path: Path):
    runner = make_runner(tmp_path)
    task = runner.submit_request("Handle the urgent rewrite", title="Interrupt me")

    with runner.lock:
        task["status"] = "running"
        task["current_stage"] = "software-requirement-orchestrator"
        runner.runtime["current_task_id"] = task["id"]
        runner._persist_runtime()

    runner.claude.run_agent = lambda **_: AgentRunResult(
        success=False,
        output_text="partial output",
        interrupted=True,
        interrupt_reason="Interrupted by scheduler",
    )

    completed = runner._run_stage_with_retries(task, "software-requirement-orchestrator", {"request_text": task["request_text"]})

    assert completed is False
    assert task["status"] == "queued"
    assert runner.runtime["current_task_id"] is None
    assert task["stages"]["software-requirement-orchestrator"]["status"] == "pending"
    assert task["stages"]["software-requirement-orchestrator"]["summary"] == "Interrupted by scheduler"


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
        task["current_stage"] = "software-requirement-orchestrator"
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

    completed = runner._run_stage_with_retries(task, "software-requirement-orchestrator", {"request_text": task["request_text"]})

    assert completed is False
    assert task["status"] == "paused"
    assert runner.runtime["current_task_id"] is None
    assert task["stages"]["software-requirement-orchestrator"]["status"] == "pending"


def test_runtime_agents_follow_pipeline_and_claude_agents_only(tmp_path: Path):
    developer_dir = tmp_path / ".claude" / "agents" / "developer"
    developer_dir.mkdir(parents=True, exist_ok=True)
    (developer_dir / "developer.md").write_text(
        "---\nname: Developer Override\ndescription: Metadata from claude agent file\nmodel: sonnet\n---\n",
        encoding="utf-8",
    )

    observer_dir = tmp_path / ".claude" / "agents" / "custom-observer"
    observer_dir.mkdir(parents=True, exist_ok=True)
    (observer_dir / "custom-observer.md").write_text(
        "---\nname: Custom Observer\ndescription: Watches pipeline state\nmodel: opus\n---\n",
        encoding="utf-8",
    )

    (tmp_path / "pipeline.yaml").write_text(
        yaml.safe_dump(
            {
                "stages": [
                    {"id": "intake", "agent": "planner"},
                    {"id": "development", "agent": "developer"},
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    runner = PipelineRunner(str(tmp_path))

    assert set(runner.agents) == {"planner", "developer", "debugger", "custom-observer"}
    assert runner.agents["developer"]["name"] == "Developer Override"
    assert runner.agents["developer"]["role"] == "Metadata from claude agent file"
    assert runner.agents["custom-observer"]["model"] == "opus"


def test_legacy_yaml_files_do_not_participate_in_runtime(tmp_path: Path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "agents.yaml").write_text(
        yaml.safe_dump(
            {"agents": [{"id": "developer", "name": "Legacy Developer Override"}]},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (agents_dir / "identities.yaml").write_text(
        yaml.safe_dump(
            {
                "developer": "legacy developer system prompt",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    developer_dir = tmp_path / ".claude" / "agents" / "developer"
    developer_dir.mkdir(parents=True, exist_ok=True)
    (developer_dir / "developer.md").write_text(
        "---\nname: Claude Developer\ndescription: Defined in claude agent\nmodel: sonnet\n---\n",
        encoding="utf-8",
    )

    (tmp_path / "pipeline.yaml").write_text(
        yaml.safe_dump(
            {"stages": [{"id": "development", "agent": "developer"}]},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    runner = PipelineRunner(str(tmp_path))

    assert runner._agent_identity("developer") is None
    assert runner.agents["developer"]["name"] == "Claude Developer"


def test_legacy_runtime_agent_ids_are_migrated(tmp_path: Path):
    developer_dir = tmp_path / ".claude" / "agents" / "software-requirement-orchestrator"
    developer_dir.mkdir(parents=True, exist_ok=True)
    (developer_dir / "software-requirement-orchestrator.md").write_text(
        "---\nname: Software Requirement Orchestrator\ndescription: Current requirement agent\nmodel: opus\n---\n",
        encoding="utf-8",
    )

    architect_dir = tmp_path / ".claude" / "agents" / "cockpit-middleware-architect"
    architect_dir.mkdir(parents=True, exist_ok=True)
    (architect_dir / "cockpit-middleware-architect.md").write_text(
        "---\nname: Cockpit Middleware Architect\ndescription: Current design agent\nmodel: opus\n---\n",
        encoding="utf-8",
    )

    legacy_runtime = {
        "tasks": [
            {
                "id": "task-1",
                "title": "Legacy Task",
                    "request_text": "legacy request",
                    "source": "web",
                    "source_metadata": {},
                "status": "completed",
                "current_stage": "design",
                "spec_file": "task-1.md",
                "run_dir": str(tmp_path / "runs" / "task-1"),
                "pipeline_snapshot": [
                    {"id": "requirements", "agent": "requirements-analyst"},
                    {"id": "design", "agent": "system-architect"},
                ],
                "stages": {
                    "requirements": {"agent_id": "requirements-analyst", "status": "passed"},
                    "design": {"agent_id": "system-architect", "status": "passed"},
                },
            }
        ],
        "current_task_id": None,
    }
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "runtime_state.json").write_text(
        json.dumps(legacy_runtime, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    runner = PipelineRunner(str(tmp_path))

    migrated_task = runner.runtime["tasks"][0]
    assert migrated_task["stages"]["requirements"]["agent_id"] == "software-requirement-orchestrator"
    assert migrated_task["stages"]["design"]["agent_id"] == "cockpit-middleware-architect"
    assert migrated_task["pipeline_snapshot"][0]["agent"] == "software-requirement-orchestrator"
    assert migrated_task["pipeline_snapshot"][1]["agent"] == "cockpit-middleware-architect"
    assert "requirements-analyst" not in runner.agents
    assert "system-architect" not in runner.agents


def test_pipeline_templates_keep_a_single_default_after_restart(tmp_path: Path):
    runner = make_runner(tmp_path)

    result = runner.template_manager.create_template(
        name="My Default Flow",
        stages=[
            {"id": "intake", "agent": "planner"},
            {"id": "development", "agent": "developer"},
        ],
        set_as_default=True,
    )

    restarted = PipelineRunner(str(tmp_path))
    templates = restarted.template_manager.list_templates(include_stages=False)
    default_templates = [template["id"] for template in templates["templates"] if template["is_default"]]

    assert default_templates == [result["id"]]
    assert templates["default_id"] == result["id"]


def test_submit_request_creates_pipeline_stage_directories(tmp_path: Path):
    runner = make_runner(tmp_path)

    task = runner.submit_request("Create the task layout", title="Layout")
    run_dir = Path(task["run_dir"])

    assert (run_dir / "software-requirement-orchestrator").exists()
    assert (run_dir / "cockpit-middleware-architect").exists()


def test_canonical_requirement_and_design_artifacts_use_stage_directories(tmp_path: Path):
    runner = make_runner(tmp_path)
    task = runner.submit_request("Generate requirement and design docs", title="Artifacts")
    transcript_dir = Path(task["run_dir"]) / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)

    requirement_transcript = transcript_dir / "software-requirement-orchestrator.json"
    runner._save_text(str(requirement_transcript), "{}")
    requirement_paths = runner._materialize_stage_artifacts(
        task,
        "software-requirement-orchestrator",
        "requirements summary",
        "Requirement body",
        str(requirement_transcript),
    )

    design_transcript = transcript_dir / "cockpit-middleware-architect.json"
    runner._save_text(str(design_transcript), "{}")
    design_paths = runner._materialize_stage_artifacts(
        task,
        "cockpit-middleware-architect",
        "design summary",
        "Design body",
        str(design_transcript),
    )

    requirement_doc = Path(task["run_dir"]) / "software-requirement-orchestrator" / "requirements_spec.md"
    architecture_doc = Path(task["run_dir"]) / "cockpit-middleware-architect" / "architecture.md"
    api_doc = Path(task["run_dir"]) / "cockpit-middleware-architect" / "api_design.md"
    data_doc = Path(task["run_dir"]) / "cockpit-middleware-architect" / "data_model.md"

    assert requirement_doc.exists()
    assert architecture_doc.exists()
    assert api_doc.exists()
    assert data_doc.exists()
    assert str(requirement_doc) in requirement_paths
    assert str(architecture_doc) in design_paths


def test_existing_legacy_requirement_and_design_files_are_repaired_for_canonical_stages(tmp_path: Path):
    runner = make_runner(tmp_path)
    task = runner.submit_request("Repair prior run artifacts", title="Repair")
    run_dir = Path(task["run_dir"])

    runner._save_text(str(run_dir / "requirements" / "requirements_spec.md"), "legacy requirements")
    runner._save_text(str(run_dir / "design" / "architecture.md"), "legacy architecture")
    runner._save_text(str(run_dir / "design" / "api_design.md"), "legacy api")
    runner._save_text(str(run_dir / "design" / "data_model.md"), "legacy data")

    requirement_paths = runner._collect_task_artifact_paths(task, "software-requirement-orchestrator")
    design_paths = runner._collect_task_artifact_paths(task, "cockpit-middleware-architect")

    assert (run_dir / "software-requirement-orchestrator" / "requirements_spec.md").read_text(encoding="utf-8") == "legacy requirements"
    assert (run_dir / "cockpit-middleware-architect" / "architecture.md").read_text(encoding="utf-8") == "legacy architecture"
    assert (run_dir / "cockpit-middleware-architect" / "api_design.md").read_text(encoding="utf-8") == "legacy api"
    assert (run_dir / "cockpit-middleware-architect" / "data_model.md").read_text(encoding="utf-8") == "legacy data"
    assert str(run_dir / "software-requirement-orchestrator" / "requirements_spec.md") in requirement_paths
    assert str(run_dir / "cockpit-middleware-architect" / "architecture.md") in design_paths