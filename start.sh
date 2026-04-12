#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"
FEISHU_DIR="$DIR/feishu-claude-code"
FEISHU_VENV="$FEISHU_DIR/.venv"
FEISHU_PID_FILE="$DIR/.feishu-bot.pid"
PORT="${1:-8080}"

FEISHU_PID=""

# 先杀掉残留的 claude CLI 进程（不杀代理）
pkill -f "claude --print" 2>/dev/null || true

# 加载 Claude Code CLI 环境（代理 + 认证）
CLAUDE_ENV="$DIR/../cc-haha/claude-global-env.sh"
if [ -f "$CLAUDE_ENV" ]; then
    echo "Loading Claude Code environment..."
    source "$CLAUDE_ENV"
fi

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
"$VENV/bin/pip" install -q -r "$DIR/requirements/runtime.txt"
"$FEISHU_VENV/bin/pip" install -q -r "$FEISHU_DIR/requirements.txt"

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
