# TOOLS.md - 本项目工具备注

## Harness

- **地址**：`http://localhost:8080`
- **提交任务**：`POST /api/requests` → `{"text": "需求内容"}`
- **查进度**：`GET /api/tasks/<task_id>`
- **健康检查**：`GET /api/health`
- **启动（Copilot 路线）**：
  ```bash
  HARNESS_CLAUDE_COMMAND="python3 engine/copilot_shim.py" ./start.sh
  ```
- **启动（Claude Code 路线）**：
  ```bash
  ./start.sh
  ```

## 切换到 Copilot 路线

harness 默认用 Claude Code，切换到 Copilot 有两种方式（不需要改任何代码）：

**方式一：环境变量（推荐，临时生效）**
```bash
HARNESS_CLAUDE_COMMAND="python3 engine/copilot_shim.py" ./start.sh
```

**方式二：改 `data/integration_settings.json`（持久生效，但不要提交到 git）**

找到这一行：
```json
"command": "claude"
```
改成：
```json
"command": "python3 engine/copilot_shim.py"
```

> `data/integration_settings.json` 是运行时配置，不在版本控制追踪范围内（或应加入 .gitignore），改完重启 harness 生效。

## Copilot CLI

- **路径**：`/opt/homebrew/bin/copilot`
- **版本验证**：`copilot --version`
- **shim 位置**：`engine/copilot_shim.py`

## 工作目录

- **项目根**：`/Users/clawbot/Documents/harnesse2e-main`（新机器上需替换用户名）
- **workspace**：`/Users/clawbot/Documents/harnesse2e-main/openclaw`
