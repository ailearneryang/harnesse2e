import os
import sys
import threading
import tempfile
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DIR = os.path.join(ROOT, "engine")
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

import pipeline_runner  # noqa: E402


class DeleteWaitingHumanTaskTests(unittest.TestCase):
    def _make_runner(self):
        runner = pipeline_runner.PipelineRunner.__new__(pipeline_runner.PipelineRunner)
        runner.lock = threading.RLock()
        runner.tasks_dir = "/tmp/fake_tasks"
        runner.runs_dir = "/tmp/fake_runs"
        runner.memory_store = mock.Mock()
        runner.running = True
        runner.runtime = {"tasks": [], "current_task_id": None}
        runner._persist_runtime = mock.Mock()
        runner._emit = mock.Mock()
        runner._require_task = pipeline_runner.PipelineRunner._require_task.__get__(runner, pipeline_runner.PipelineRunner)
        return runner

    def test_delete_waiting_human_task_clears_current_task_id(self):
        runner = self._make_runner()
        runner.runtime["tasks"] = [
            {"id": "task-1", "status": "waiting_human", "title": "approval smoke"},
        ]
        runner.runtime["current_task_id"] = "task-1"

        pipeline_runner.PipelineRunner.delete_task(runner, "task-1")

        self.assertEqual(runner.runtime["tasks"], [])
        self.assertIsNone(runner.runtime["current_task_id"])
        runner._persist_runtime.assert_called()
        runner._emit.assert_called_once()

    def test_wait_for_approval_returns_none_when_task_deleted(self):
        runner = self._make_runner()
        runner.runtime["current_task_id"] = "task-1"
        approval = {"id": "approval-1", "stage": "design"}

        result = pipeline_runner.PipelineRunner._wait_for_approval(
            runner,
            {"id": "task-1"},
            approval,
        )

        self.assertIsNone(result)
        self.assertIsNone(runner.runtime["current_task_id"])
        runner._persist_runtime.assert_called()
        runner._emit.assert_called_once()

    def test_process_task_exits_cleanly_when_waiting_task_is_deleted(self):
        runner = self._make_runner()
        task = {
            "id": "task-1",
            "title": "approval smoke",
            "current_stage": "design",
            "request_text": "prod auth change",
            "spec_file": "task-1.md",
            "run_dir": "./runs/task-1",
            "context": {},
            "stages": {
                "design": {"status": "pending"},
            },
        }
        runner._task_pipeline_order = mock.Mock(return_value=["design"])
        runner._yield_task_if_requested = mock.Mock(return_value=False)
        runner._requires_manual_gate = mock.Mock(return_value=True)
        runner._create_approval = mock.Mock(return_value={"id": "approval-1", "stage": "design"})
        runner._wait_for_approval = mock.Mock(return_value=None)
        runner._fail_task = mock.Mock()
        runner._emit = mock.Mock()
        runner._persist_runtime = mock.Mock()
        runner._update_latest_run_link = mock.Mock()
        runner._write_run_metadata = mock.Mock()
        runner._set_agent_status = mock.Mock()
        runner.engine = mock.Mock()
        runner.engine.snapshot.current_state = "idle"

        pipeline_runner.PipelineRunner._process_task(runner, task)

        runner._fail_task.assert_not_called()


class RuntimeStateMigrationTests(unittest.TestCase):
    def test_ensure_runtime_shape_rehomes_legacy_run_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = pipeline_runner.PipelineRunner.__new__(pipeline_runner.PipelineRunner)
            runner.runs_dir = os.path.join(temp_dir, "runs")
            runner.pipeline_order = ["intake"]
            runner.runtime = {
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "legacy",
                        "source": "web",
                        "spec_file": "task-1.md",
                        "status": "paused",
                        "current_stage": "intake",
                        "created_at": "2026-04-13T14:31:40",
                        "updated_at": "2026-04-13T14:32:22",
                        "run_dir": "/Users/nanyanxin/harnesse2e/runs/task-1",
                        "artifacts": {
                            "request_uploads": [
                                "/Users/nanyanxin/harnesse2e/runs/task-1/uploads/doc.docx",
                            ]
                        },
                        "attachments": [
                            {
                                "name": "doc.docx",
                                "path": "/Users/nanyanxin/harnesse2e/runs/task-1/uploads/doc.docx",
                            }
                        ],
                        "context": {
                            "intake": {
                                "artifact_paths": [
                                    "/Users/nanyanxin/harnesse2e/runs/task-1/intake/intake.md",
                                ]
                            }
                        },
                        "stages": {
                            "intake": {
                                "title": "Request Intake",
                                "status": "pending",
                                "agent_id": "planner",
                                "attempts": 0,
                                "summary": "",
                                "verdict": None,
                                "started_at": None,
                                "ended_at": None,
                                "artifact_paths": [
                                    "/Users/nanyanxin/harnesse2e/runs/task-1/intake/intake.md",
                                ],
                                "logs": [],
                            }
                        },
                        "pipeline_snapshot": [{"id": "intake", "agent": "planner"}],
                    }
                ],
                "current_task_id": None,
            }
            runner._ensure_run_layout = pipeline_runner.PipelineRunner._ensure_run_layout.__get__(runner, pipeline_runner.PipelineRunner)
            runner._remap_task_run_paths = pipeline_runner.PipelineRunner._remap_task_run_paths.__get__(runner, pipeline_runner.PipelineRunner)
            runner._task_pipeline_order = pipeline_runner.PipelineRunner._task_pipeline_order.__get__(runner, pipeline_runner.PipelineRunner)
            runner._task_stage_definitions = pipeline_runner.PipelineRunner._task_stage_definitions.__get__(runner, pipeline_runner.PipelineRunner)
            runner._stage_definitions = pipeline_runner.PipelineRunner._stage_definitions.__get__(runner, pipeline_runner.PipelineRunner)
            runner._empty_stage_map = pipeline_runner.PipelineRunner._empty_stage_map.__get__(runner, pipeline_runner.PipelineRunner)
            runner._stage_agent_id = pipeline_runner.PipelineRunner._stage_agent_id.__get__(runner, pipeline_runner.PipelineRunner)
            runner._canonical_agent_id = pipeline_runner.PipelineRunner._canonical_agent_id.__get__(runner, pipeline_runner.PipelineRunner)
            runner._migrate_legacy_task_agents = pipeline_runner.PipelineRunner._migrate_legacy_task_agents.__get__(runner, pipeline_runner.PipelineRunner)
            runner._repair_stage_artifact_layout = mock.Mock()
            runner._write_run_metadata = mock.Mock()
            runner._persist_runtime = mock.Mock()

            pipeline_runner.PipelineRunner._ensure_runtime_shape(runner)

            task = runner.runtime["tasks"][0]
            expected_run_dir = os.path.join(runner.runs_dir, "task-1")
            self.assertEqual(task["run_dir"], expected_run_dir)
            self.assertEqual(task["artifacts"]["request_uploads"], [os.path.join(expected_run_dir, "uploads", "doc.docx")])
            self.assertEqual(task["attachments"][0]["path"], os.path.join(expected_run_dir, "uploads", "doc.docx"))
            self.assertEqual(task["context"]["intake"]["artifact_paths"], [os.path.join(expected_run_dir, "intake", "intake.md")])
            self.assertEqual(task["stages"]["intake"]["artifact_paths"], [os.path.join(expected_run_dir, "intake", "intake.md")])
            runner._persist_runtime.assert_called_once()


if __name__ == "__main__":
    unittest.main()
