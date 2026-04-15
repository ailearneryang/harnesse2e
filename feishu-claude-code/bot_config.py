import os
import shutil

from dotenv import load_dotenv

# Ensure we load the .env file that sits next to this module so
# repo-local settings (like DEFAULT_MODEL / CLI_BACKEND) are applied.
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(PROJECT_DIR, ".env"))
LEGACY_SESSIONS_DIR = os.path.expanduser("~/.feishu-claude")


def _resolve_default_cwd() -> str:
    configured = os.getenv("DEFAULT_CWD", "~")
    expanded = os.path.expanduser(configured)
    if os.path.isabs(expanded):
        return expanded
    return os.path.abspath(os.path.join(PROJECT_DIR, expanded))


def _resolve_sessions_dir() -> str:
    configured = os.getenv("SESSIONS_DIR")
    if configured:
        return os.path.expanduser(configured)
    preferred = os.path.expanduser("~/.feishu-copilot")
    if os.path.isdir(preferred) or not os.path.isdir(LEGACY_SESSIONS_DIR):
        return preferred
    return LEGACY_SESSIONS_DIR


FEISHU_APP_ID = os.environ["FEISHU_APP_ID"]
FEISHU_APP_SECRET = os.environ["FEISHU_APP_SECRET"]
ADMIN_OPEN_ID = os.getenv("ADMIN_OPEN_ID")

CLI_BACKEND = (os.getenv("CLI_BACKEND", "copilot") or "copilot").strip().lower()
if CLI_BACKEND not in {"copilot", "claude"}:
    CLI_BACKEND = "copilot"

COPILOT_CLI = os.getenv("COPILOT_CLI_PATH") or shutil.which("copilot") or "copilot"
CLAUDE_CLI = os.getenv("CLAUDE_CLI_PATH") or shutil.which("claude") or "claude"
CLI_BIN = COPILOT_CLI if CLI_BACKEND == "copilot" else CLAUDE_CLI

DEFAULT_MODEL = os.getenv(
    "DEFAULT_MODEL",
    "gpt-5.4" if CLI_BACKEND == "copilot" else "claude-opus-4-6",
)
DEFAULT_CWD = _resolve_default_cwd()
PERMISSION_MODE = os.getenv("PERMISSION_MODE", "bypassPermissions")
CALLBACK_PUBLIC_URL = os.getenv("CALLBACK_PUBLIC_URL", "").rstrip("/")
HARNESS_API_BASE_URL = os.getenv("HARNESS_API_BASE_URL", "http://localhost:8080").rstrip("/")

SESSIONS_DIR = _resolve_sessions_dir()

# 卡片按钮回调 HTTP 端口（需 ngrok 暴露）
CALLBACK_PORT = int(os.getenv("CALLBACK_PORT", "9981"))

# 流式卡片更新：每积累多少字符推送一次
STREAM_CHUNK_SIZE = int(os.getenv("STREAM_CHUNK_SIZE", "20"))
