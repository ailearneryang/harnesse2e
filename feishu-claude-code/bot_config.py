import os
import shutil
from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_default_cwd() -> str:
    configured = os.getenv("DEFAULT_CWD", "~")
    expanded = os.path.expanduser(configured)
    if os.path.isabs(expanded):
        return expanded
    return os.path.abspath(os.path.join(PROJECT_DIR, expanded))

FEISHU_APP_ID = os.environ["FEISHU_APP_ID"]
FEISHU_APP_SECRET = os.environ["FEISHU_APP_SECRET"]
ADMIN_OPEN_ID = os.getenv("ADMIN_OPEN_ID")

CLAUDE_CLI = os.getenv("CLAUDE_CLI_PATH") or shutil.which("claude") or "claude"

DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "claude-opus-4-6")
DEFAULT_CWD = _resolve_default_cwd()
PERMISSION_MODE = os.getenv("PERMISSION_MODE", "bypassPermissions")
CALLBACK_PUBLIC_URL = os.getenv("CALLBACK_PUBLIC_URL", "").rstrip("/")

SESSIONS_DIR = os.path.expanduser("~/.feishu-claude")

# 卡片按钮回调 HTTP 端口（需 ngrok 暴露）
CALLBACK_PORT = int(os.getenv("CALLBACK_PORT", "9981"))

# 流式卡片更新：每积累多少字符推送一次
STREAM_CHUNK_SIZE = int(os.getenv("STREAM_CHUNK_SIZE", "20"))
