"""
CLI runner for Feishu chat integration.

Copilot CLI is the default backend. Claude Code remains available as a
compatibility backend because the bot still supports older environments.
"""

import asyncio
import json
import os
from typing import Callable, Optional

from bot_config import CLAUDE_CLI, CLI_BACKEND, COPILOT_CLI, PERMISSION_MODE

IDLE_TIMEOUT = 300  # 5 分钟无任何输出视为挂死


def _extract_text_content(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts)
    return ""


async def _fire_callback(cb, *args):
    if cb is None:
        return
    if asyncio.iscoroutinefunction(cb):
        await cb(*args)
    else:
        cb(*args)


def _build_command(
    message: str,
    active_session_id: Optional[str],
    model: Optional[str],
    cwd: str,
    permission_mode: Optional[str],
) -> tuple[list[str], bool]:
    if CLI_BACKEND == "copilot":
        cmd = [
            COPILOT_CLI,
            "-p",
            message,
            "--allow-all-tools",
            "--allow-all-paths",
            "--add-dir",
            cwd,
        ]
        if model:
            cmd.extend(["--model", model])
        return cmd, False

    cmd = [
        CLAUDE_CLI,
        "--print",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--permission-mode",
        permission_mode or PERMISSION_MODE,
    ]
    if active_session_id:
        cmd += ["--resume", active_session_id]
    if model:
        cmd += ["--model", model]
    return cmd, True


async def run_backend(
    message: str,
    session_id: Optional[str] = None,
    model: Optional[str] = None,
    cwd: Optional[str] = None,
    permission_mode: Optional[str] = None,
    on_text_chunk: Optional[Callable[[str], None]] = None,
    on_tool_use: Optional[Callable[[str, dict], None]] = None,
    on_process_start: Optional[Callable[[asyncio.subprocess.Process], None]] = None,
) -> tuple[str, Optional[str], bool]:
    """
    调用后端 CLI 并尽量以统一方式流式解析输出。

    Returns:
        (full_response_text, session_id, used_fresh_session_fallback)
    """

    resolved_cwd = cwd or os.path.expanduser("~")

    async def _run_once(active_session_id: Optional[str]) -> tuple[str, Optional[str], int, str]:
        cmd, uses_stdin = _build_command(
            message=message,
            active_session_id=active_session_id,
            model=model,
            cwd=resolved_cwd,
            permission_mode=permission_mode,
        )

        env = os.environ.copy()
        env.pop("CLAUDECODE", None)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=resolved_cwd,
            env=env,
            limit=10 * 1024 * 1024,
        )

        await _fire_callback(on_process_start, proc)

        if uses_stdin and proc.stdin is not None:
            proc.stdin.write((message + "\n").encode())
            await proc.stdin.drain()
            proc.stdin.close()
        elif proc.stdin is not None:
            proc.stdin.close()

        full_text = ""
        new_session_id = active_session_id
        pending_tool_name = ""
        pending_tool_input_json = ""

        try:
            while True:
                try:
                    raw_line = await asyncio.wait_for(proc.stdout.readline(), timeout=IDLE_TIMEOUT)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    raise RuntimeError(
                        f"{CLI_BACKEND} 执行超时（{IDLE_TIMEOUT}秒无输出），已终止进程"
                    )

                if not raw_line:
                    break

                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    full_text = f"{full_text}\n{line}".strip() if full_text else line
                    await _fire_callback(on_text_chunk, line)
                    continue

                event_type = data.get("type")

                if event_type == "system":
                    sid = data.get("session_id")
                    if sid:
                        new_session_id = sid
                    continue

                if event_type == "stream_event":
                    evt = data.get("event", {})
                    evt_type = evt.get("type")

                    if evt_type == "content_block_delta":
                        delta = evt.get("delta", {})
                        delta_type = delta.get("type")

                        if delta_type == "text_delta":
                            chunk = delta.get("text", "")
                            if chunk:
                                full_text += chunk
                                await _fire_callback(on_text_chunk, chunk)

                        elif delta_type == "input_json_delta":
                            pending_tool_input_json += delta.get("partial_json", "")

                    elif evt_type == "content_block_start":
                        block = evt.get("content_block", {})
                        if block.get("type") == "tool_use":
                            pending_tool_name = block.get("name", "")
                            pending_tool_input_json = ""
                            await _fire_callback(on_tool_use, pending_tool_name, {})

                    elif evt_type == "content_block_stop":
                        if pending_tool_name and pending_tool_input_json:
                            try:
                                inp = json.loads(pending_tool_input_json)
                            except json.JSONDecodeError:
                                inp = {}
                            await _fire_callback(on_tool_use, pending_tool_name, inp)
                        pending_tool_name = ""
                        pending_tool_input_json = ""
                    continue

                if event_type == "result":
                    sid = data.get("session_id")
                    if sid:
                        new_session_id = sid
                    final_text = _extract_text_content(data.get("result", ""))
                    if final_text:
                        full_text = final_text
                    continue

                text_value = _extract_text_content(data.get("content"))
                if not text_value:
                    text_value = data.get("text", "")
                if text_value:
                    full_text = f"{full_text}\n{text_value}".strip() if full_text else text_value
                    await _fire_callback(on_text_chunk, text_value)

        except RuntimeError:
            raise

        stderr_output = await proc.stderr.read()
        await proc.wait()
        stderr_text = stderr_output.decode("utf-8", errors="replace").strip()
        return full_text.strip(), new_session_id, proc.returncode, stderr_text

    final_text, new_session_id, returncode, stderr_text = await _run_once(session_id)
    used_fresh_session_fallback = False

    if (
        CLI_BACKEND == "claude"
        and session_id
        and returncode != 0
        and not stderr_text
        and not final_text
    ):
        print("[run_backend] resume failed without stderr, retrying with fresh session", flush=True)
        final_text, new_session_id, returncode, stderr_text = await _run_once(None)
        used_fresh_session_fallback = True

    if returncode != 0:
        detail = stderr_text or "no stderr"
        if final_text:
            detail += f" (partial output length={len(final_text)})"
        if final_text:
            return final_text, new_session_id, used_fresh_session_fallback
        raise RuntimeError(f"{CLI_BACKEND} exited with code {returncode}: {detail}")

    return final_text, new_session_id, used_fresh_session_fallback


async def run_copilot(*args, **kwargs):
    return await run_backend(*args, **kwargs)


async def run_claude(*args, **kwargs):
    return await run_backend(*args, **kwargs)
