from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from engine.integrations import ClaudeCLIAdapter


class BlockingStdout:
    def __init__(self):
        self._released = threading.Event()

    def readline(self) -> str:
        self._released.wait()
        return ""

    def release(self) -> None:
        self._released.set()


class BlockingProcess:
    def __init__(self):
        self.stdout = BlockingStdout()
        self.returncode = None
        self.killed = False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9
        self.stdout.release()

    def wait(self, timeout=None):
        start = time.monotonic()
        while self.returncode is None:
            if timeout is not None and time.monotonic() - start > timeout:
                raise TimeoutError("process did not exit")
            time.sleep(0.01)
        return self.returncode


def test_run_agent_times_out_when_stdout_reader_blocks(monkeypatch, tmp_path):
    process = BlockingProcess()

    monkeypatch.setattr("engine.integrations.shutil.which", lambda _: "/usr/bin/claude")
    monkeypatch.setattr("engine.integrations.subprocess.Popen", lambda *args, **kwargs: process)

    adapter = ClaudeCLIAdapter(
        {
            "command": "claude",
            "simulate": False,
            "output_format": "stream-json",
            "idle_timeout_seconds": 1,
            "hard_timeout_seconds": 5,
            "max_turns": 1,
        }
    )

    result = adapter.run_agent(agent_id="planner", prompt="hello", cwd=str(tmp_path), stage="intake")

    assert result.success is False
    assert "idle timeout" in (result.error or "")
    assert process.killed is True


def test_run_agent_returns_failure_when_process_cannot_start(monkeypatch, tmp_path):
    monkeypatch.setattr("engine.integrations.shutil.which", lambda _: "/usr/bin/claude")

    def raise_popen_error(*args, **kwargs):
        raise FileNotFoundError("[Errno 2] No such file or directory: '/bad/cwd'")

    monkeypatch.setattr("engine.integrations.subprocess.Popen", raise_popen_error)

    adapter = ClaudeCLIAdapter(
        {
            "command": "claude",
            "simulate": False,
            "output_format": "stream-json",
            "idle_timeout_seconds": 1,
            "hard_timeout_seconds": 5,
        }
    )

    result = adapter.run_agent(agent_id="planner", prompt="hello", cwd=str(tmp_path / "missing"), stage="intake")

    assert result.success is False
    assert result.return_code == -1
    assert "failed to start" in (result.error or "")