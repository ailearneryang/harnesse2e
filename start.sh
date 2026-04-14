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
# 先杀掉残留的 agent shim 进程（不杀代理）
pkill -f "engine/copilot_shim.py" 2>/dev/null || true

# 可选加载旧的 Claude 环境（仅兼容历史代理配置）
CLAUDE_ENV="$DIR/../cc-haha/claude-global-env.sh"
if [ -f "$CLAUDE_ENV" ]; then
    echo "Loading optional legacy Claude environment..."
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
