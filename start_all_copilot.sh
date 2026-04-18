#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"
FEISHU_DIR="$DIR/feishu-claude-code"
FEISHU_VENV="$FEISHU_DIR/.venv"
FEISHU_PID_FILE="$DIR/.feishu-bot.pid"
PORT="${1:-8080}"

FEISHU_PID=""

resolve_npm_copilot_bin() {
    local npm_prefix

    if ! command -v npm >/dev/null 2>&1; then
        return 1
    fi

    npm_prefix="$(npm prefix -g 2>/dev/null || true)"
    if [ -n "$npm_prefix" ] && [ -x "$npm_prefix/bin/copilot" ]; then
        printf '%s\n' "$npm_prefix/bin/copilot"
        return 0
    fi

    return 1
}

resolve_copilot_bin() {
    if [ -n "${COPILOT_CLI_PATH:-}" ] && [ -x "${COPILOT_CLI_PATH}" ]; then
        printf '%s\n' "$COPILOT_CLI_PATH"
        return 0
    fi

    if command -v copilot >/dev/null 2>&1; then
        command -v copilot
        return 0
    fi

    for candidate in /opt/homebrew/bin/copilot /usr/local/bin/copilot; do
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done

    if resolve_npm_copilot_bin >/dev/null 2>&1; then
        resolve_npm_copilot_bin
        return 0
    fi

    return 1
}

install_copilot_via_npm() {
    if ! command -v npm >/dev/null 2>&1; then
        echo "Error: GitHub Copilot CLI is not installed, and npm is not available for automatic installation."
        echo "Install Node.js/npm first, then run: npm install -g @github/copilot"
        return 1
    fi

    echo "GitHub Copilot CLI not found. Attempting npm installation via: npm install -g @github/copilot"
    if ! npm install -g @github/copilot; then
        echo "Error: Automatic npm installation failed."
        echo "Please run manually: npm install -g @github/copilot"
        return 1
    fi

    return 0
}

probe_copilot_request() {
    "$COPILOT_CLI_PATH" -p "Reply with OK only." --allow-all-tools --allow-all-paths --add-dir "$DIR" >/dev/null 2>&1
}

login_copilot() {
    echo "GitHub Copilot CLI is installed but not authenticated. Starting login flow..."

    if [ ! -t 0 ] || [ ! -t 1 ]; then
        echo "Error: Copilot login requires an interactive terminal."
        echo "Run manually: copilot login"
        echo "Or provide a token via COPILOT_GITHUB_TOKEN, GH_TOKEN, or GITHUB_TOKEN."
        return 1
    fi

    if ! "$COPILOT_CLI_PATH" login; then
        echo "Error: Copilot login did not complete successfully."
        return 1
    fi

    return 0
}

check_copilot_ready() {
    local copilot_bin

    if ! copilot_bin="$(resolve_copilot_bin)"; then
        if ! install_copilot_via_npm; then
            exit 1
        fi

        if ! copilot_bin="$(resolve_copilot_bin)"; then
            echo "Error: GitHub Copilot CLI was installed but could not be resolved to an executable path."
            echo "Set COPILOT_CLI_PATH explicitly or make sure npm global bin is in PATH."
            exit 1
        fi
    fi

    export COPILOT_CLI_PATH="$copilot_bin"
    echo "Using Copilot CLI: $COPILOT_CLI_PATH"

    if ! "$COPILOT_CLI_PATH" --version >/dev/null 2>&1; then
        echo "Error: GitHub Copilot CLI exists but cannot run normally."
        exit 1
    fi

    echo "Checking Copilot login status..."
    if ! probe_copilot_request; then
        if ! login_copilot; then
            exit 1
        fi

        echo "Re-checking Copilot login status..."
        if ! probe_copilot_request; then
            echo "Error: GitHub Copilot CLI login completed, but requests still cannot be executed."
            echo "Check Copilot subscription, token permissions, or run: copilot login"
            exit 1
        fi
    fi
}

# 先杀掉残留的 agent shim 进程（不杀代理）
pkill -f "engine/copilot_shim.py" 2>/dev/null || true

check_copilot_ready

# 确保虚拟环境存在
if [ ! -d "$VENV" ]; then
    echo "Creating virtualenv..."
    python3 -m venv "$VENV"
fi

if [ ! -d "$FEISHU_VENV" ]; then
    echo "Creating Feishu virtualenv..."
    python3 -m venv "$FEISHU_VENV"
fi

# 安装依赖
if [ -f "$DIR/requirements/runtime.txt" ]; then
    "$VENV/bin/pip" install -q -r "$DIR/requirements/runtime.txt"
fi
if [ -f "$FEISHU_DIR/requirements.txt" ]; then
    "$FEISHU_VENV/bin/pip" install -q -r "$FEISHU_DIR/requirements.txt"
fi

cleanup() {
    if [ -n "$FEISHU_PID" ] && kill -0 "$FEISHU_PID" 2>/dev/null; then
        echo "Stopping Feishu bot..."
        kill "$FEISHU_PID" 2>/dev/null || true
        wait "$FEISHU_PID" 2>/dev/null || true
    fi
    rm -f "$FEISHU_PID_FILE"
}

trap cleanup EXIT INT TERM

if [ -f "$FEISHU_PID_FILE" ]; then
    EXISTING_FEISHU_PID="$(cat "$FEISHU_PID_FILE")"
    if [ -n "$EXISTING_FEISHU_PID" ] && kill -0 "$EXISTING_FEISHU_PID" 2>/dev/null; then
        echo "Stopping previous Feishu bot process ($EXISTING_FEISHU_PID)..."
        kill "$EXISTING_FEISHU_PID" 2>/dev/null || true
        wait "$EXISTING_FEISHU_PID" 2>/dev/null || true
    fi
    rm -f "$FEISHU_PID_FILE"
fi

# 杀掉占用端口的进程
lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true

export HARNESS_AGENT_COMMAND="${HARNESS_AGENT_COMMAND:-python3 engine/copilot_shim.py}"
export HARNESS_AGENT_HARD_TIMEOUT="${HARNESS_AGENT_HARD_TIMEOUT:-3600}"
export HARNESS_AGENT_IDLE_TIMEOUT="${HARNESS_AGENT_IDLE_TIMEOUT:-600}"
export HARNESS_CLAUDE_COMMAND="${HARNESS_CLAUDE_COMMAND:-$HARNESS_AGENT_COMMAND}"
export HARNESS_CLAUDE_HARD_TIMEOUT="${HARNESS_CLAUDE_HARD_TIMEOUT:-$HARNESS_AGENT_HARD_TIMEOUT}"
export HARNESS_CLAUDE_IDLE_TIMEOUT="${HARNESS_CLAUDE_IDLE_TIMEOUT:-$HARNESS_AGENT_IDLE_TIMEOUT}"

# 检查是否启用 Feishu
FEISHU_ENABLED=$(python3 -c "import json; print(json.load(open('$DIR/data/integration_settings.json')).get('feishu',{}).get('enabled', False))" 2>/dev/null || echo "False")

if [ "$FEISHU_ENABLED" = "True" ]; then
    echo "Starting Feishu bot from $FEISHU_DIR"
    (
        cd "$FEISHU_DIR"
        exec "$FEISHU_VENV/bin/python3" main.py
    ) &
    FEISHU_PID=$!
    printf '%s\n' "$FEISHU_PID" > "$FEISHU_PID_FILE"
else
    echo "Feishu bot disabled, skipping..."
fi

echo "Starting Harness on http://localhost:$PORT"
"$VENV/bin/python3" "$DIR/engine/pipeline_runner.py" --harness-dir "$DIR" --web-port "$PORT"
HARNESS_EXIT_CODE=$?

exit "$HARNESS_EXIT_CODE"
