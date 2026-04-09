#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"
PORT="${1:-8080}"

# 加载 Claude Code CLI 环境（代理 + 认证）
CLAUDE_ENV="/Users/xing/cc-haha/claude-global-env.sh"
if [ -f "$CLAUDE_ENV" ]; then
    echo "Loading Claude Code environment..."
    source "$CLAUDE_ENV"
fi

# 确保虚拟环境存在
if [ ! -d "$VENV" ]; then
    echo "Creating virtualenv..."
    python3 -m venv "$VENV"
fi

# 安装依赖
"$VENV/bin/pip" install -q -r "$DIR/requirements/runtime.txt"

# 杀掉残留进程
lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || true

echo "Starting Harness on http://localhost:$PORT"
exec "$VENV/bin/python3" "$DIR/engine/pipeline_runner.py" --harness-dir "$DIR" --web-port "$PORT"
