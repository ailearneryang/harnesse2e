import asyncio
import json
import os
import re
import uuid
from datetime import datetime
from typing import Optional

from bot_config import CLI_BACKEND, DEFAULT_CWD, DEFAULT_MODEL, PERMISSION_MODE, SESSIONS_DIR

TRANSCRIPTS_DIR = os.path.join(SESSIONS_DIR, "transcripts")

COPILOT_MODEL_ALIASES = {
    "best": "gpt-5.4",
    "gpt-5.4": "gpt-5.4",
    "fast": "gpt-5.4-mini",
    "mini": "gpt-5.4-mini",
    "gpt-5.4-mini": "gpt-5.4-mini",
    "gpt-5-mini": "gpt-5.4-mini",
    # Historical typo persisted in older sessions.
    "gpt-5-min": "gpt-5.4",
}


def _normalize_model_for_backend(model: str) -> str:
    value = (model or "").strip()
    if not value:
        return DEFAULT_MODEL

    lower = value.lower()
    if CLI_BACKEND == "copilot" and lower.startswith(("claude-", "anthropic/claude-")):
        return DEFAULT_MODEL
    if CLI_BACKEND == "copilot":
        if lower in COPILOT_MODEL_ALIASES:
            return COPILOT_MODEL_ALIASES[lower]
        if lower.startswith(("gpt-", "openai/", "o1", "o3", "o4")):
            return lower
    if CLI_BACKEND == "claude" and lower.startswith(("gpt-", "openai/", "o1", "o3", "o4")):
        return DEFAULT_MODEL
    return value


def _ensure_transcripts_dir() -> None:
    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)


def _transcript_path(session_id: str) -> str:
    _ensure_transcripts_dir()
    return os.path.join(TRANSCRIPTS_DIR, f"{session_id}.jsonl")


def scan_cli_sessions(limit: int = 30) -> list[dict]:
    """
    扫描 bot 自己维护的 transcripts 目录。
    Copilot 默认不暴露可恢复的本地会话文件，因此这里统一使用 bot transcript。
    """
    _ensure_transcripts_dir()
    results = []
    for fname in os.listdir(TRANSCRIPTS_DIR):
        if not fname.endswith(".jsonl"):
            continue
        session_id = fname[:-6]
        fpath = os.path.join(TRANSCRIPTS_DIR, fname)
        results.append((os.path.getmtime(fpath), session_id, fpath))

    results.sort(key=lambda x: x[0], reverse=True)
    return [_parse_session_file(fpath, session_id, mtime) for mtime, session_id, fpath in results[:limit]]

def _clean_preview(text: str) -> str:
    """清洗 preview 文本，去掉系统注入内容"""
    # 去掉 [环境：...] 前缀
    text = re.sub(r'^\[环境：[^\]]*\]\s*', '', text)
    # 去掉 <local-command-caveat>...</local-command-caveat> 及其后的系统文本
    text = re.sub(r'<local-command-caveat>.*?</local-command-caveat>\s*', '', text, flags=re.DOTALL)
    # 去掉 <system-reminder>...</system-reminder>
    text = re.sub(r'<system-reminder>.*?</system-reminder>\s*', '', text, flags=re.DOTALL)
    # 去掉其他 XML-like 系统标签
    text = re.sub(r'<[a-z_-]+>.*?</[a-z_-]+>\s*', '', text, flags=re.DOTALL)
    return text.strip()


def _parse_session_file(fpath: str, session_id: str, mtime: float) -> dict:
    """从 bot transcript 提取 preview / cwd / started_at。"""
    preview = ""
    cwd = ""
    started_at = datetime.fromtimestamp(mtime).isoformat()

    try:
        with open(fpath, encoding="utf-8", errors="replace") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    d = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                entry_type = d.get("type")
                if entry_type == "custom-title" and d.get("customTitle"):
                    preview = d["customTitle"][:50]
                    continue
                if entry_type != "message" or d.get("role") != "user":
                    continue
                if not cwd and d.get("cwd"):
                    cwd = d["cwd"]
                if d.get("timestamp"):
                    started_at = d["timestamp"][:19].replace("T", " ")
                text = str(d.get("content", "")).strip()
                if text:
                    text = _clean_preview(text)
                    if text:
                        preview = text[:50]
                        break
    except OSError:
        pass

    return {
        "session_id": session_id,
        "started_at": started_at,
        "cwd": cwd,
        "preview": preview,
        "source": "terminal",
    }

def _find_session_file(session_id: str) -> Optional[str]:
    fpath = _transcript_path(session_id)
    return fpath if os.path.isfile(fpath) else None


def _extract_conversation_context(fpath: str, max_chars: int = 2000) -> str:
    """从 bot transcript 提取最近对话文本。"""
    parts = []
    total = 0
    try:
        with open(fpath, encoding="utf-8", errors="replace") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    d = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if d.get("type") != "message":
                    continue
                text = str(d.get("content", "")).strip()
                if not text:
                    continue
                text = _clean_preview(text)
                if not text:
                    continue
                role = "用户" if d.get("role") == "user" else "助手"
                part = f"{role}: {text}"
                parts.append(part)
                total += len(part)
                if total >= max_chars:
                    break
    except OSError:
        pass
    return "\n".join(parts)


def _get_api_token() -> Optional[str]:
    """兼容旧导入，Copilot 路线下不再直接访问 Claude token。"""
    return None


def generate_summary(session_id: str, token: Optional[str] = None) -> str:
    """为指定 session 生成本地摘要，避免依赖特定云厂商 API。"""
    fpath = _find_session_file(session_id)
    if not fpath:
        return ""
    context = _extract_conversation_context(fpath)
    if not context:
        return ""
    first_line = context.splitlines()[0].replace("用户: ", "").replace("助手: ", "").strip()
    if not first_line:
        return ""
    compact = re.sub(r"\s+", " ", first_line)
    return compact[:18] + ("…" if len(compact) > 18 else "")


def _write_custom_title(session_id: str, title: str):
    """将摘要作为 custom-title 写入 bot transcript。"""
    fpath = _find_session_file(session_id)
    if not fpath:
        return
    # 检查是否已有 custom-title 行，幂等
    try:
        with open(fpath, encoding="utf-8", errors="replace") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    d = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if d.get("type") == "custom-title":
                    return  # 已存在，跳过
    except OSError:
        return
    # 追加 custom-title 行
    entry = json.dumps({
        "type": "custom-title",
        "customTitle": title,
        "sessionId": session_id,
    }, ensure_ascii=False)
    try:
        with open(fpath, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except OSError:
        pass


def _append_message(
    session_id: str,
    role: str,
    content: str,
    cwd: str = "",
    model: str = "",
    backend: str = "",
):
    if not content.strip():
        return
    entry = {
        "type": "message",
        "role": role,
        "content": content,
        "cwd": cwd,
        "model": model,
        "backend": backend or CLI_BACKEND,
        "timestamp": datetime.now().isoformat(),
    }
    with open(_transcript_path(session_id), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


SESSIONS_FILE = os.path.join(SESSIONS_DIR, "sessions.json")


class Session:
    def __init__(
        self,
        session_id: Optional[str],
        model: str,
        cwd: str,
        permission_mode: str,
        workspace: str = "",
    ):
        self.session_id = session_id
        self.model = model
        self.cwd = cwd
        self.permission_mode = permission_mode
        self.workspace = workspace


class SessionStore:
    def __init__(self):
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        self._save_lock = asyncio.Lock()  # 保护 _save() 的全局锁
        self._data: dict = self._load()
        self._dedup_all_histories()

    def _load(self) -> dict:
        if os.path.exists(SESSIONS_FILE):
            try:
                with open(SESSIONS_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save(self):
        tmp = SESSIONS_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, SESSIONS_FILE)  # 原子操作，崩溃时不会截断原文件

    async def _save_async(self):
        """异步保存，使用锁保护并发写入（原子写入）"""
        async with self._save_lock:
            tmp = SESSIONS_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, SESSIONS_FILE)

    async def _bg_generate_summary(self, user_id: str, session_id: str):
        """后台生成会话摘要，不阻塞消息流"""
        try:
            summary = await asyncio.to_thread(generate_summary, session_id)
            if summary:
                self._data.setdefault(user_id, {}).setdefault("summaries", {})[session_id] = summary
                await asyncio.to_thread(_write_custom_title, session_id, summary)
                await self._save_async()
        except Exception:
            pass

    def _dedup_all_histories(self):
        """启动时清理所有用户 history 中的重复 session_id"""
        changed = False
        for user in self._data.values():
            for chat_data in user.values():
                if not isinstance(chat_data, dict) or "history" not in chat_data:
                    continue
                history = chat_data.get("history", [])
                seen = set()
                cleaned = []
                # 倒序遍历，保留每个 session_id 最后出现的那条
                for h in reversed(history):
                    sid = h.get("session_id")
                    if sid and sid not in seen:
                        seen.add(sid)
                        cleaned.append(h)
                cleaned.reverse()
                if len(cleaned) != len(history):
                    chat_data["history"] = cleaned
                    changed = True
        if changed:
            self._save()

    def _user(self, user_id: str) -> dict:
        return self._data.setdefault(user_id, {})

    def _default_current(self) -> dict:
        return {
            "session_id": None,
            "model": DEFAULT_MODEL,
            "cwd": DEFAULT_CWD,
            "permission_mode": PERMISSION_MODE,
            "started_at": datetime.now().isoformat(),
            "preview": "",
            "workspace": "",
        }

    def _normalize_chat_key(self, user_id: str, chat_id: str) -> str:
        return "private" if chat_id == user_id else chat_id

    def _ensure_current_defaults(self, current: dict) -> bool:
        changed = False
        defaults = self._default_current()
        for key, value in defaults.items():
            if key not in current:
                current[key] = value
                changed = True
        normalized_model = _normalize_model_for_backend(current.get("model", DEFAULT_MODEL))
        if current.get("model") != normalized_model:
            current["model"] = normalized_model
            changed = True
        return changed

    async def set_recent_file(self, user_id: str, chat_id: str, file_path: str):
        chat_data = await self._ensure_chat_data(user_id, chat_id)
        current = chat_data["current"]
        current["recent_file"] = file_path
        self._save()

    async def peek_recent_file(self, user_id: str, chat_id: str) -> Optional[str]:
        chat_data = await self._ensure_chat_data(user_id, chat_id)
        return chat_data["current"].get("recent_file")

    async def clear_recent_file(self, user_id: str, chat_id: str):
        chat_data = await self._ensure_chat_data(user_id, chat_id)
        if "recent_file" in chat_data["current"]:
            del chat_data["current"]["recent_file"]
            self._save()

    async def _ensure_chat_data(self, user_id: str, chat_id: str) -> dict:
        user = self._user(user_id)
        chat_key = self._normalize_chat_key(user_id, chat_id)
        changed = False

        if chat_key not in user:
            # 兼容旧结构：首次访问私聊时把顶层 current/history 迁入 private。
            if chat_key == "private" and isinstance(user.get("current"), dict):
                user[chat_key] = {
                    "current": user.pop("current"),
                    "history": user.pop("history", []),
                }
            else:
                user[chat_key] = {
                    "current": self._default_current(),
                    "history": [],
                }
            changed = True

        chat_data = user[chat_key]
        if self._ensure_current_defaults(chat_data.setdefault("current", self._default_current())):
            changed = True
        if "history" not in chat_data:
            chat_data["history"] = []
            changed = True

        if changed:
            await self._save_async()

        return chat_data

    def get_summary(self, user_id: str, session_id: str) -> str:
        """获取缓存的摘要"""
        return self._user(user_id).get("summaries", {}).get(session_id, "")

    def get_all_unsummarized(self) -> list[tuple[str, str]]:
        """返回所有缺摘要的 (user_id, session_id) 列表"""
        results = []
        for user_id, user_data in self._data.items():
            summaries = user_data.get("summaries", {})
            for chat_key, chat_data in user_data.items():
                if not isinstance(chat_data, dict) or "history" not in chat_data:
                    continue
                cur_sid = chat_data.get("current", {}).get("session_id")
                if cur_sid and not summaries.get(cur_sid):
                    results.append((user_id, cur_sid))
                for h in chat_data.get("history", []):
                    sid = h.get("session_id", "")
                    if sid and not summaries.get(sid):
                        results.append((user_id, sid))
        return results

    async def batch_set_summaries(self, user_id: str, summaries: dict):
        """批量缓存摘要并保存"""
        user = self._user(user_id)
        user.setdefault("summaries", {}).update(summaries)
        await self._save_async()

    async def get_current(self, user_id: str, chat_id: str) -> Session:
        """Get current session config for a specific chat"""
        cur = await self.get_current_raw(user_id, chat_id)
        return Session(
            session_id=cur.get("session_id"),
            model=cur.get("model", DEFAULT_MODEL),
            cwd=cur.get("cwd", DEFAULT_CWD),
            permission_mode=cur.get("permission_mode", PERMISSION_MODE),
            workspace=cur.get("workspace", ""),
        )

    async def prepare_backend_input(
        self,
        user_id: str,
        chat_id: str,
        user_message: str,
        max_context_chars: int = 5000,
    ) -> tuple[str, str]:
        """
        为 Copilot/Claude 生成本轮输入。

        Copilot 默认不提供可恢复 session，因此这里会把本地 transcript 拼回 prompt，
        从而在 one-shot 调用里维持连续上下文。
        """
        chat_data = await self._ensure_chat_data(user_id, chat_id)
        cur = chat_data["current"]
        session_id = cur.get("session_id")
        if not session_id:
            session_id = f"sid_{uuid.uuid4().hex[:12]}"
            cur["session_id"] = session_id
            cur["started_at"] = datetime.now().isoformat()
            if not cur.get("preview"):
                cur["preview"] = _clean_preview(user_message)[:40]
            await self._save_async()

        transcript_path = _find_session_file(session_id)
        if not transcript_path:
            return session_id, user_message

        context = _extract_conversation_context(transcript_path, max_chars=max_context_chars)
        if not context:
            return session_id, user_message

        prompt = (
            "你正在继续一个飞书中的开发助手会话。以下是最近对话记录，"
            "请保持上下文连续，并只回答最新用户消息。\n\n"
            f"{context}\n\n"
            "## 最新用户消息\n"
            f"{user_message}"
        )
        return session_id, prompt

    async def on_backend_response(
        self,
        user_id: str,
        chat_id: str,
        new_session_id: str,
        first_message: str,
        assistant_message: str = "",
    ):
        """后端回复后更新状态，并把对话写入 bot transcript。"""
        chat_data = await self._ensure_chat_data(user_id, chat_id)
        cur = chat_data["current"]
        old_id = cur.get("session_id")

        if old_id and old_id != new_session_id:
            # 归档旧 session（先去重，避免同一 session_id 重复出现）
            chat_data["history"] = [h for h in chat_data["history"] if h["session_id"] != old_id]
            chat_data["history"].append({
                "session_id": old_id,
                "started_at": cur.get("started_at", ""),
                "preview": cur.get("preview", ""),
            })
            chat_data["history"] = chat_data["history"][-20:]
            cur["started_at"] = datetime.now().isoformat()
            # 异步生成摘要，不阻塞消息流
            summaries = self._data[user_id].get("summaries", {})
            if not summaries.get(old_id):
                asyncio.create_task(self._bg_generate_summary(user_id, old_id))

        cur["session_id"] = new_session_id
        if not cur.get("preview"):
            cur["preview"] = _clean_preview(first_message)[:40]
        await self._save_async()

        _append_message(
            new_session_id,
            "user",
            first_message,
            cwd=cur.get("cwd", ""),
            model=cur.get("model", ""),
        )
        _append_message(
            new_session_id,
            "assistant",
            assistant_message,
            cwd=cur.get("cwd", ""),
            model=cur.get("model", ""),
        )

    async def on_claude_response(
        self,
        user_id: str,
        chat_id: str,
        new_session_id: str,
        first_message: str,
        assistant_message: str = "",
    ):
        await self.on_backend_response(
            user_id=user_id,
            chat_id=chat_id,
            new_session_id=new_session_id,
            first_message=first_message,
            assistant_message=assistant_message,
        )

    async def new_session(self, user_id: str, chat_id: str) -> str:
        """Start a new session for a specific chat, return old session title"""
        chat_data = await self._ensure_chat_data(user_id, chat_id)
        cur = chat_data["current"]
        old_title = ""

        if cur.get("session_id"):
            old_id = cur["session_id"]
            # Archive current session (dedup first)
            chat_data["history"] = [h for h in chat_data.get("history", []) if h["session_id"] != old_id]
            chat_data["history"].append({
                "session_id": old_id,
                "started_at": cur.get("started_at", ""),
                "preview": cur.get("preview", ""),
            })
            chat_data["history"] = chat_data["history"][-20:]

            # 摘要：有缓存就用，没有就后台生成（不阻塞 /new 响应）
            summaries = self._data[user_id].get("summaries", {})
            old_title = summaries.get(old_id, "")
            if not old_title:
                asyncio.create_task(self._bg_generate_summary(user_id, old_id))

        # Create new session
        chat_data["current"] = {
            "session_id": None,
            "model": cur.get("model", DEFAULT_MODEL),
            "cwd": cur.get("cwd", DEFAULT_CWD),
            "permission_mode": cur.get("permission_mode", PERMISSION_MODE),
            "started_at": datetime.now().isoformat(),
            "preview": "",
            "workspace": cur.get("workspace", ""),
        }
        await self._save_async()
        return old_title

    async def set_model(self, user_id: str, chat_id: str, model: str):
        """Set model for a specific chat"""
        chat_data = await self._ensure_chat_data(user_id, chat_id)
        chat_data["current"]["model"] = _normalize_model_for_backend(model)
        await self._save_async()

    async def set_cwd(self, user_id: str, chat_id: str, cwd: str, workspace_name: Optional[str] = None):
        """Set working directory for a specific chat"""
        chat_data = await self._ensure_chat_data(user_id, chat_id)
        chat_data["current"]["cwd"] = cwd
        chat_data["current"]["workspace"] = workspace_name or ""
        await self._save_async()

    async def set_permission_mode(self, user_id: str, chat_id: str, mode: str):
        """Set permission mode for a specific chat"""
        chat_data = await self._ensure_chat_data(user_id, chat_id)
        chat_data["current"]["permission_mode"] = mode
        await self._save_async()

    async def resume_session(self, user_id: str, chat_id: str, index_or_id: str) -> tuple[Optional[str], str]:
        """按序号（1-based）或 session_id 恢复 session，返回 (session_id, old_title)"""
        if user_id not in self._data:
            return None, ""

        chat_key = self._normalize_chat_key(user_id, chat_id)
        if chat_key not in self._data[user_id]:
            return None, ""

        chat_data = await self._ensure_chat_data(user_id, chat_id)
        history = chat_data.get("history", [])

        try:
            idx = int(index_or_id) - 1
            if 0 <= idx < len(history):
                session_id = history[idx]["session_id"]
            else:
                return None, ""
        except ValueError:
            session_id = index_or_id

        # 归档 outgoing session（如果有且不是同一个）
        cur = chat_data["current"]
        old_id = cur.get("session_id")
        old_title = ""
        if old_id and old_id != session_id:
            chat_data["history"] = [h for h in chat_data["history"] if h["session_id"] != old_id]
            chat_data["history"].append({
                "session_id": old_id,
                "started_at": cur.get("started_at", ""),
                "preview": cur.get("preview", ""),
            })
            chat_data["history"] = chat_data["history"][-20:]
            # 获取摘要：优先缓存，否则生成
            summaries = self._data[user_id].get("summaries", {})
            old_title = summaries.get(old_id, "")
            if not old_title:
                asyncio.create_task(self._bg_generate_summary(user_id, old_id))

        # 从 history 中找回原始 preview 和 started_at
        original_preview = ""
        original_started = ""
        for h in chat_data["history"]:
            if h["session_id"] == session_id:
                original_preview = h.get("preview", "")
                original_started = h.get("started_at", "")
                break
        cur["session_id"] = session_id
        cur["preview"] = original_preview
        cur["started_at"] = original_started or datetime.now().isoformat()
        await self._save_async()
        return session_id, old_title

    async def list_sessions(self, user_id: str, chat_id: str) -> list:
        """List all sessions for a specific chat"""
        if user_id not in self._data:
            return []

        chat_key = self._normalize_chat_key(user_id, chat_id)
        if chat_key not in self._data[user_id]:
            return []

        return list(reversed((await self._ensure_chat_data(user_id, chat_id)).get("history", [])))

    def list_workspaces(self, user_id: str) -> dict[str, str]:
        """List saved workspaces for a user"""
        return dict(sorted(self._user(user_id).get("workspaces", {}).items()))

    async def save_workspace(self, user_id: str, name: str, cwd: str):
        """Save or update a named workspace for a user"""
        user = self._user(user_id)
        user.setdefault("workspaces", {})[name] = cwd
        await self._save_async()

    async def delete_workspace(self, user_id: str, name: str) -> bool:
        """Delete a named workspace and clear active bindings that reference it"""
        user = self._user(user_id)
        workspaces = user.setdefault("workspaces", {})
        if name not in workspaces:
            return False

        del workspaces[name]
        for chat_data in user.values():
            if not isinstance(chat_data, dict) or "current" not in chat_data:
                continue
            if chat_data["current"].get("workspace") == name:
                chat_data["current"]["workspace"] = ""
        await self._save_async()
        return True

    async def bind_workspace(self, user_id: str, chat_id: str, name: str) -> Optional[str]:
        """Bind a saved workspace to the current chat"""
        path = self._user(user_id).get("workspaces", {}).get(name)
        if not path:
            return None
        await self.set_cwd(user_id, chat_id, path, workspace_name=name)
        return path

    async def get_current_raw(self, user_id: str, chat_id: str = None) -> dict:
        """Get raw current session data for a specific chat"""
        if chat_id is None:
            chat_id = user_id

        return (await self._ensure_chat_data(user_id, chat_id))["current"]
