"""
斜杠命令解析与处理。
返回要发送给用户的回复文本。
"""

import asyncio
import getpass
import json
import os
import shlex
import subprocess
import sys
import inspect
from datetime import datetime
from typing import Optional, Tuple

from bot_config import CLI_BACKEND, CLI_BIN, DEFAULT_CWD, HARNESS_API_BASE_URL
from session_store import SessionStore, scan_cli_sessions, generate_summary, _get_api_token, _write_custom_title

PLUGINS_DIR = os.path.expanduser("~/.claude/plugins")


VALID_MODES = {
    "default": "每次工具调用需确认",
    "acceptEdits": "自动接受文件编辑，其余需确认",
    "plan": "只规划不执行工具",
    "bypassPermissions": "全部自动执行（无确认）",
    "dontAsk": "全部自动执行（静默）",
}

MODE_ALIASES = {
    "bypass": "bypassPermissions",
    "accept": "acceptEdits",
    "auto": "bypassPermissions",
}

MODEL_ALIASES = {
    "best": "gpt-5.4",
    "fast": "gpt-5.4-mini",
    "mini": "gpt-5-mini",
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

HELP_TEXT = """\
📖 **可用命令**

**Bot 管理：**
`/help` — 显示此帮助
`/stop` — 停止当前正在运行的任务
`/new` 或 `/clear` — 开始新 session
`/resume` — 查看历史 sessions / `/resume [序号]` 恢复
`/model [名称]` — 切换模型（opus / sonnet / haiku 或完整 ID）
`/mode [模式]` — 切换权限模式（default / plan / acceptEdits / bypassPermissions）
`/status` — 显示当前 session 信息
`/cd [路径]` — 切换工具执行的工作目录
`/ls [路径]` — 查看当前工作目录下的文件/目录
`/workspace` 或 `/ws` — 保存/切换群组工作空间

**查看能力：**
`/skills` — 列出当前仓库可见的 Skills / 指令
`/mcp` — 查看 MCP 配置入口说明
`/usage` — 查看当前 CLI 的用量查询方式


**Skill / Prompt 透传（直接转发给 CLI 执行）：**
`/commit` — 提交代码
其他 `/xxx` — 自动转发给 CLI 处理

**MCP 工具：** 已配置的 MCP servers 自动可用，直接对话即可调用。

**发送任意普通消息即可与 Copilot 对话。**\
"""


def parse_command(text: str) -> Optional[Tuple[str, str]]:
    """
    尝试解析斜杠命令，或者将普通的包含特定关键词的话转换为命令。
    返回 (command, args) 或 None（不是命令）。
    """
    text = text.strip()
    
    # 匹配自然语言的快捷方式，把没有斜杠的 "帮我写/帮我做/新建需求" 都转到 /harness
    magic_starters = ["新建需求", "提需求"]
    
    # 正规的斜杠命令处理
    if text.startswith("/"):
        parts = text[1:].split(None, 1)
        cmd = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""
        return cmd, args
        
    # 自然语言快捷方式处理
    for starter in magic_starters:
        if text.startswith(starter):
            return "harness", text

    return None


# Bot 自身处理的命令，其余 /xxx 转发给 CLI
BOT_COMMANDS = {
    "help", "h", "new", "clear", "resume", "model", "mode", "status", "cd", "ls",
    "workspace", "ws", "skills", "mcp", "usage", "stop", "harness", "task", "job", "run"
}


async def _build_session_list(user_id: str, chat_id: str, store: SessionStore, cli_all: list[dict] | None = None) -> list[dict]:
    """构建合并、去重、排序后的 session 列表（不含当前 session）。
    /resume 列表展示和 /resume N 选择都用这一个函数，保证索引一致。"""
    cur_sid = (await store.get_current_raw(user_id, chat_id)).get("session_id")

    if cli_all is None:
        cli_all = scan_cli_sessions(30)
    cli_preview_map = {s["session_id"]: s for s in cli_all}

    feishu_sessions = [
        {**s, "source": "feishu"} for s in await store.list_sessions(user_id, chat_id)
    ]
    for s in feishu_sessions:
        cli_info = cli_preview_map.get(s["session_id"])
        if cli_info and cli_info.get("preview"):
            s["preview"] = cli_info["preview"]

    feishu_ids = {s["session_id"] for s in feishu_sessions}
    cli_sessions = [
        s for s in cli_all
        if s["session_id"] not in feishu_ids and len(s.get("preview", "")) > 5
    ]
    all_sessions = feishu_sessions + cli_sessions

    seen = set()
    if cur_sid:
        seen.add(cur_sid)
    deduped = []
    for s in all_sessions:
        sid = s["session_id"]
        if sid not in seen:
            seen.add(sid)
            deduped.append(s)

    deduped.sort(key=lambda s: s.get("started_at", ""), reverse=True)
    return deduped[:15]


def _strip_md(text: str) -> str:
    """去除 markdown 格式 + 压成单行纯文本"""
    text = " ".join(text.split())
    while text.startswith("#"):
        text = text.lstrip("#").lstrip()
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = text.replace("<", "").replace(">", "")
    return text.strip()


async def _format_session_list(user_id: str, chat_id: str, store: SessionStore):
    """生成历史 sessions 列表，每个会话一个按钮。返回 dict(text, buttons) 或 str。"""
    from session_store import _clean_preview

    cur = await store.get_current_raw(user_id, chat_id)
    cur_sid = cur.get("session_id")

    cli_all = scan_cli_sessions(30)
    cli_preview_map = {s["session_id"]: s for s in cli_all}
    all_sessions = await _build_session_list(user_id, chat_id, store, cli_all=cli_all)

    if not cur_sid and not all_sessions:
        return "暂无历史 sessions。"

    # 收集已缓存的摘要，缺失的后台生成（不阻塞列表展示）
    summaries = {}
    missing = []
    all_sids = [cur_sid] if cur_sid else []
    all_sids += [s["session_id"] for s in all_sessions]
    for sid in all_sids:
        cached = store.get_summary(user_id, sid)
        if cached:
            summaries[sid] = cached
        else:
            missing.append(sid)
    if missing:
        for sid in missing[:5]:
            asyncio.create_task(store._bg_generate_summary(user_id, sid))

    def _desc(sid: str, preview_raw: str) -> str:
        s = summaries.get(sid, "")
        if s:
            s = _strip_md(s)
            return s if len(s) <= 30 else s[:28] + ".."
        p = _clean_preview(preview_raw or "")
        if not p:
            return "（无预览）"
        p = _strip_md(p)
        return p if len(p) <= 30 else p[:28] + ".."

    def _fmt_time(raw: str) -> str:
        t = raw[:16].replace("T", " ")
        if len(t) >= 16:
            t = t[5:16].replace("-", "/")
        return t

    # 当前 session 信息
    lines = []
    if cur_sid:
        cli_info = cli_preview_map.get(cur_sid)
        preview = (cli_info.get("preview") if cli_info and cli_info.get("preview")
                   else cur.get("preview") or "")
        lines.append(f"当前：{_desc(cur_sid, preview)} ({_fmt_time(cur.get('started_at', ''))})")

    lines.append(f"共 {len(all_sessions)} 个历史会话")

    # 每个历史会话一个按钮
    buttons = []
    for s in all_sessions[:10]:
        sid = s["session_id"]
        preview = s.get("preview", "")
        desc = _desc(sid, preview)
        time_str = _fmt_time(s.get("started_at", ""))
        buttons.append({
            "text": f"{desc} ({time_str})",
            "value": {"action": "resume_session", "sid": sid, "cid": chat_id},
        })

    if buttons:
        return {"text": "\n".join(lines), "buttons": buttons}
    return "\n".join(lines)


def _candidate_skill_sources() -> list[tuple[str, str]]:
    project_root = os.path.abspath(DEFAULT_CWD)
    return [
        ("dir", os.path.join(project_root, ".claude", "skills")),
        ("dir", os.path.join(project_root, "openclaw", "skills")),
        ("dir", os.path.expanduser("~/.claude/skills")),
        ("dir", os.path.expanduser("~/.claude/plugins")),
        ("file", os.path.join(project_root, "AGENTS.md")),
        ("file", os.path.join(project_root, ".github", "copilot-instructions.md")),
    ]


def _list_skills(chat_id: str = ""):
    """扫描仓库与本地技能目录，返回 dict(text, buttons) 或 str"""
    skills = []
    for source_type, path in _candidate_skill_sources():
        if source_type == "file":
            if os.path.isfile(path):
                skills.append((os.path.splitext(os.path.basename(path))[0], _read_skill_desc(path)))
            continue
        if not os.path.isdir(path):
            continue
        for root, _, files in os.walk(path):
            for fname in files:
                if fname not in {"SKILL.md", "AGENTS.md"} and not fname.endswith(".md"):
                    continue
                fpath = os.path.join(root, fname)
                name = os.path.basename(root) if fname == "SKILL.md" else os.path.splitext(fname)[0]
                desc = _read_skill_desc(fpath)
                skills.append((name, desc))

    if not skills:
        return "暂无可见的 skills / 指令文件。"

    skills.sort(key=lambda x: x[0])
    # 去重
    seen = set()
    unique = []
    for name, desc in skills:
        if name not in seen:
            seen.add(name)
            unique.append((name, desc))

    buttons = [
        {"text": f"/{name}", "value": {"action": "reply", "reply": f"/{name}", "cid": chat_id}}
        for name, desc in unique[:15]
    ]
    return {
        "text": f"🛠 **可用 Skills / 指令** ({len(unique)} 个)",
        "buttons": buttons,
    }


def _read_skill_desc(fpath: str) -> str:
    """从 skill/command 的 md 文件中提取 description"""
    try:
        with open(fpath, encoding="utf-8") as f:
            in_frontmatter = False
            for line in f:
                line = line.strip()
                if line == "---" and not in_frontmatter:
                    in_frontmatter = True
                    continue
                if line == "---" and in_frontmatter:
                    break
                if in_frontmatter and line.startswith("description:"):
                    return line[len("description:"):].strip().strip('"')
    except OSError:
        pass
    return ""


def _get_usage() -> str:
    if CLI_BACKEND == "claude":
        return (
            "📊 **Usage**\n\n"
            "Claude 路线的自动用量查询已下线。"
            "如需查看，请直接在终端进入交互式 CLI 后执行相应命令。"
        )
    return (
        "📊 **Usage**\n\n"
        "Copilot CLI 的用量信息建议在交互式终端里查看：\n"
        "1. 运行 `copilot`\n"
        "2. 输入 `/usage`\n"
        "3. 如需更详细上下文，可再用 `/context`"
    )



def _list_mcp() -> str:
    if CLI_BACKEND == "claude":
        try:
            result = subprocess.run(
                [CLI_BIN, "mcp", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = result.stdout.strip()
        except Exception as e:
            return f"❌ 获取 MCP 列表失败：{e}"
        if not output:
            return "暂无已配置的 MCP servers。"
        return f"🔌 **已配置的 MCP Servers**\n\n{output}"

    return (
        "🔌 **MCP 配置**\n\n"
        "Copilot CLI 的 MCP 管理入口在交互式会话里。\n"
        "请在终端运行 `copilot` 后输入 `/mcp` 查看或修改。"
    )


async def _list_directory(user_id: str, chat_id: str, store: SessionStore, args: str) -> str:
    cur = await store.get_current_raw(user_id, chat_id)
    base_dir = cur.get("cwd", DEFAULT_CWD)
    raw_target = args.strip()

    if not raw_target:
        target = base_dir
        display_target = "."
    elif os.path.isabs(raw_target):
        target = os.path.expanduser(raw_target)
        display_target = target
    else:
        target = os.path.abspath(os.path.join(base_dir, os.path.expanduser(raw_target)))
        display_target = raw_target

    if not os.path.exists(target):
        return f"❌ 路径不存在：`{display_target}`\n当前工作目录：`{base_dir}`"

    if not os.path.isdir(target):
        return f"❌ 目标不是目录：`{display_target}`"

    try:
        entries = []
        with os.scandir(target) as it:
            for entry in it:
                suffix = "/" if entry.is_dir() else ""
                entries.append((not entry.is_dir(), entry.name.lower(), f"`{entry.name}{suffix}`"))
    except OSError as e:
        return f"❌ 读取目录失败：{e}"

    entries.sort()
    preview = [item[2] for item in entries[:50]]
    hidden_count = max(0, len(entries) - len(preview))

    lines = [
        "📁 **目录内容**",
        f"请求路径：`{display_target}`",
        f"绝对路径：`{target}`",
    ]
    if not preview:
        lines.append("（空目录）")
        return "\n".join(lines)

    lines.append("")
    lines.extend(preview)
    if hidden_count:
        lines.append("")
        lines.append(f"…… 还有 {hidden_count} 项未显示")
    return "\n".join(lines)


async def _format_workspace_list(user_id: str, chat_id: str, store: SessionStore):
    cur = await store.get_current_raw(user_id, chat_id)
    current_name = cur.get("workspace", "")
    current_cwd = cur.get("cwd", "~")
    workspaces = store.list_workspaces(user_id)

    lines = ["🗂 **工作空间**"]
    lines.append(f"当前：`{current_name or '（未命名）'}` → `{current_cwd}`")

    buttons = []
    if workspaces:
        for name, path in workspaces.items():
            marker = " ✓" if name == current_name else ""
            buttons.append({
                "text": f"📁 {name}{marker}",
                "value": {"action": "run_cmd", "cmd": f"/ws use {name}", "cid": chat_id},
            })

    if buttons:
        lines.append(f"已保存 {len(workspaces)} 个，点击切换：")
        return {"text": "\n".join(lines), "buttons": buttons}

    lines.append("还没有已保存的工作空间。")
    lines.append("`/ws save 名称 [路径]` 保存")
    return "\n".join(lines)


async def _handle_workspace_command(
    args: str,
    user_id: str,
    chat_id: str,
    store: SessionStore,
) -> str:
    if not args:
        return await _format_workspace_list(user_id, chat_id, store)

    try:
        parts = shlex.split(args)
    except ValueError as e:
        return f"❌ 参数解析失败：{e}"

    if not parts:
        return await _format_workspace_list(user_id, chat_id, store)

    action = parts[0].lower()

    if action in {"list", "ls"}:
        return await _format_workspace_list(user_id, chat_id, store)

    if action in {"save", "add"}:
        if len(parts) < 2:
            return "⚠️ 用法：`/ws save 名称 [路径]`"
        name = parts[1]
        path = (await store.get_current_raw(user_id, chat_id)).get("cwd", DEFAULT_CWD)
        if len(parts) >= 3:
            path = os.path.expanduser(parts[2])
        if not os.path.isdir(path):
            return f"❌ 路径不存在：`{path}`"
        await store.save_workspace(user_id, name, path)
        return f"✅ 已保存工作空间 `{name}` → `{path}`"

    if action == "use":
        if len(parts) != 2:
            return "⚠️ 用法：`/ws use 名称`"
        name = parts[1]
        path = await store.bind_workspace(user_id, chat_id, name)
        if not path:
            return f"❌ 未找到工作空间：`{name}`，先用 `/ws save {name} 路径` 保存。"
        return (
            f"✅ 当前群组已绑定工作空间 `{name}`\n"
            f"工作目录：`{path}`\n"
            "如需清空旧上下文，可继续发送 `/new`。"
        )

    if action == "set":
        if len(parts) != 2:
            return "⚠️ 用法：`/ws set 路径`"
        path = os.path.expanduser(parts[1])
        if not os.path.isdir(path):
            return f"❌ 路径不存在：`{path}`"
        old_name = (await store.get_current_raw(user_id, chat_id)).get("workspace", "")
        await store.set_cwd(user_id, chat_id, path)
        suffix = "，并解除原工作空间绑定" if old_name else ""
        return f"✅ 当前群组工作目录已切换为 `{path}`{suffix}"

    if action in {"remove", "delete", "rm"}:
        if len(parts) != 2:
            return "⚠️ 用法：`/ws remove 名称`"
        name = parts[1]
        if not await store.delete_workspace(user_id, name):
            return f"❌ 未找到工作空间：`{name}`"
        return f"✅ 已删除工作空间 `{name}`"

    return (
        f"❌ 未知子命令：`{action}`\n"
        "可用：`list`、`save`、`use`、`set`、`remove`"
    )


async def handle_command(
    cmd: str,
    args: str,
    user_id: str,
    chat_id: str,
    store: SessionStore,
) -> Optional[str]:
    """处理命令，返回回复文本。返回 None 表示不是 bot 命令，应转发给 CLI。"""

    if cmd not in BOT_COMMANDS:
        return None  # 不认识的 /xxx → 转发给 CLI（如 /commit 等 skill）

    if cmd == "ws":
        cmd = "workspace"

    if cmd in ("help", "h"):
        return HELP_TEXT

    elif cmd in ("new", "clear"):
        # /new [mode] — 开新 session，可选指定模式
        new_mode = None
        if args:
            alias = MODE_ALIASES.get(args.lower(), args)
            if alias in VALID_MODES:
                new_mode = alias

        old_title = await store.new_session(user_id, chat_id)
        if new_mode:
            await store.set_permission_mode(user_id, chat_id, new_mode)

        cur = await store.get_current(user_id, chat_id)
        parts = []
        if old_title:
            parts.append(f"✅ 已开始新 session。\n上个会话：「{old_title}」")
        else:
            parts.append("✅ 已开始新 session。")
        parts.append(f"当前模式：**{cur.permission_mode}**")
        return {
            "text": "\n".join(parts),
            "buttons": [
                {"text": "📋 规划", "value": {"action": "set_mode", "mode": "plan", "cid": chat_id}},
                {"text": "✏️ 接受编辑", "value": {"action": "set_mode", "mode": "acceptEdits", "cid": chat_id}},
                {"text": "🚀 全自动", "value": {"action": "set_mode", "mode": "bypassPermissions", "cid": chat_id}},
                {"text": "🔒 需确认", "value": {"action": "set_mode", "mode": "default", "cid": chat_id}},
            ],
        }

    elif cmd == "resume":
        if not args:
            return await _format_session_list(user_id, chat_id, store)
        # 如果是数字序号，先在合并列表中找到对应 session_id
        try:
            idx = int(args) - 1
            all_sessions = await _build_session_list(user_id, chat_id, store)
            if 0 <= idx < len(all_sessions):
                args = all_sessions[idx]["session_id"]
            else:
                return f"❌ 序号 {int(args)} 超出范围（共 {len(all_sessions)} 条）。"
        except ValueError:
            pass  # 直接用 session ID 字符串
        session_id, old_title = await store.resume_session(user_id, chat_id, args)
        if not session_id:
            return f"❌ 未找到 session：`{args}`，用 `/resume` 查看列表。"
        # 用摘要作为会话名，没有就用 ID 前缀
        name = store.get_summary(user_id, session_id) or f"#{session_id[:8]}"
        reply = f"✅ 已恢复会话「{name}」，继续对话吧。"
        if old_title:
            reply += f"\n上个会话：「{old_title}」"
        return reply

    elif cmd == "model":
        if not args:
            cur = await store.get_current(user_id, chat_id)
            return {
                "text": f"当前模型：**{cur.model}**",
                "buttons": [
                    {"text": "🧠 Opus", "value": {"action": "run_cmd", "cmd": "/model opus", "cid": chat_id}},
                    {"text": "⚡ Sonnet", "value": {"action": "run_cmd", "cmd": "/model sonnet", "cid": chat_id}},
                    {"text": "🐇 Haiku", "value": {"action": "run_cmd", "cmd": "/model haiku", "cid": chat_id}},
                ],
            }
        model = MODEL_ALIASES.get(args.lower(), args)
        await store.set_model(user_id, chat_id, model)
        return f"✅ 已切换模型为 `{model}`"

    elif cmd == "status":
        cur = await store.get_current_raw(user_id, chat_id)
        sid = cur.get("session_id") or "（新 session）"
        model = cur.get("model", "未知")
        cwd = cur.get("cwd", "~")
        workspace = cur.get("workspace") or "（未绑定）"
        started = cur.get("started_at", "")[:16].replace("T", " ")
        mode = cur.get("permission_mode") or "bypassPermissions"
        return (
            f"📊 **当前 Session 状态**\n"
            f"Session ID: `{sid}`\n"
            f"模型: `{model}`\n"
            f"权限模式: `{mode}`\n"
            f"工作空间: `{workspace}`\n"
            f"工作目录: `{cwd}`\n"
            f"开始时间: {started}"
        )

    elif cmd == "mode":
        if not args:
            cur = await store.get_current(user_id, chat_id)
            return {
                "text": f"当前模式：**{cur.permission_mode}**\n{VALID_MODES.get(cur.permission_mode, '')}",
                "buttons": [
                    {"text": "📋 规划", "value": {"action": "set_mode", "mode": "plan", "cid": chat_id}},
                    {"text": "✏️ 接受编辑", "value": {"action": "set_mode", "mode": "acceptEdits", "cid": chat_id}},
                    {"text": "🚀 全自动", "value": {"action": "set_mode", "mode": "bypassPermissions", "cid": chat_id}},
                    {"text": "🔒 需确认", "value": {"action": "set_mode", "mode": "default", "cid": chat_id}},
                ],
            }
        mode = MODE_ALIASES.get(args.lower(), args)
        if mode not in VALID_MODES:
            return f"❌ 未知模式：`{args}`\n可选：{', '.join(f'`{m}`' for m in VALID_MODES)}"
        await store.set_permission_mode(user_id, chat_id, mode)
        return f"✅ 已切换为 **{mode}** — {VALID_MODES[mode]}"

    elif cmd == "cd":
        if not args:
            return "⚠️ 用法：`/cd [路径]`"
        path = os.path.expanduser(args)
        if not os.path.isdir(path):
            return f"❌ 路径不存在：`{path}`"
        old_name = (await store.get_current_raw(user_id, chat_id)).get("workspace", "")
        await store.set_cwd(user_id, chat_id, path)
        suffix = "，并解除原工作空间绑定" if old_name else ""
        return f"✅ 工作目录已切换为 `{path}`{suffix}"

    elif cmd == "ls":
        return await _list_directory(user_id, chat_id, store, args)

    elif cmd == "workspace":
        return await _handle_workspace_command(args, user_id, chat_id, store)

    elif cmd == "skills":
        return _list_skills(chat_id)

    elif cmd == "mcp":
        return _list_mcp()

    elif cmd == "usage":
        return _get_usage()

    elif cmd in ("harness", "task", "job", "run"):
        import urllib.request
        import json
        if not args:
            return "❌ 请提供需求内容，例如：`/harness 帮我写一个贪吃蛇`"
        
        # 把刚发的附件加进 context 里
        recent_file = None
        peek_recent_file = getattr(store, "peek_recent_file", None)
        if callable(peek_recent_file):
            result = peek_recent_file(user_id, chat_id)
            recent_file = await result if inspect.isawaitable(result) else result
        if recent_file:
            args = f"{args}\n[附件内容路径]: {recent_file}"
            clear_recent_file = getattr(store, "clear_recent_file", None)
            if callable(clear_recent_file):
                result = clear_recent_file(user_id, chat_id)
                if inspect.isawaitable(result):
                    await result

        try:
            # Generate a title from the first 20 characters of the request
            title = (args.split('\n')[0][:20] + "...") if args else "Feishu Request"
            
            req = urllib.request.Request(
                f"{HARNESS_API_BASE_URL}/api/requests",
                data=json.dumps({
                    "title": title,
                    "text": args, 
                    "source": "feishu-bot",
                    "metadata": {
                        "chat_id": chat_id,
                        "sender_open_id": user_id,
                        "entrypoint": "feishu-bot",
                    },
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())
                task_id = result.get("id", "unknown")
                return f"✅ 已成功向 Harness Pipeline 投递需求！\n\nTask ID: `{task_id}`\n\n您可以前往 [Harness Dashboard](http://localhost:8080) 查看详细进度。"
        except Exception as e:
            return f"❌ 投递 Harness 需求失败: {e}"

    elif cmd == "stop":
        return "⏹ /stop 命令在消息队列外处理，如果看到这条说明当前没有运行中的任务。"

    else:
        return None  # fallback: 转发给 Claude
