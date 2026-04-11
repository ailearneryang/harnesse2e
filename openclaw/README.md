# OpenClaw 编程助手

这个文件夹是 OpenClaw **coding-assistant（编程助手）** 的 workspace。

编程助手通过飞书 `coding` 账号接收消息，作为传话筒和监督者，把需求提交给 harness pipeline 执行，把进度推回飞书。

---

## 文件结构

```
openclaw/
├── README.md        ← 本文件
├── SOUL.md          ← 助手人格与行为边界（每次会话自动注入）
├── AGENTS.md        ← 操作规则与角色定义（每次会话自动注入）
├── IDENTITY.md      ← 名字、emoji
├── USER.md          ← 用户画像（每人必填）
├── TOOLS.md         ← 本地工具备注与切换说明
├── HEARTBEAT.md     ← 心跳任务清单
├── memory/          ← 助手运行时记忆（自动生成，勿手动删）
└── skills/          ← workspace 级 skills
    └── copilot-cli/ ← Copilot CLI skill
```

> SOUL.md、AGENTS.md 等 bootstrap 文件由 OpenClaw 在每次新会话开始时自动注入到助手上下文，是助手的记忆和人格来源。空文件跳过，过大文件截断。

---

## 整体架构

```
飞书用户
  ↕ 消息（coding 账号）
OpenClaw coding-assistant（传话筒 + 监督者）
  ↕ HTTP API
Harness Pipeline（编排 11 个 stage）
  ↕
Copilot CLI（实际干活）
```

### 和 feishu-claude-code 的区别

项目里还有 `feishu-claude-code/`，是另一套独立系统：

| | feishu-claude-code | OpenClaw coding-assistant |
|---|---|---|
| 作用 | 飞书直连 Claude Code，对话式编程 | 飞书 → harness pipeline → Copilot CLI |
| 适合 | 临时问问题、改小代码 | 完整需求走规划→开发→评审→测试全流程 |
| 执行器 | Claude Code | Copilot CLI |

两套可以同时存在，互不影响。

---

## 新机器上手

### 1. 安装 OpenClaw

```bash
npm install -g openclaw
```

### 2. 配置 `~/.openclaw/openclaw.json`

关键字段：

```json
{
  "agents": {
    "list": [
      {
        "id": "coding-assistant",
        "name": "coding-assistant",
        "workspace": "/你的绝对路径/harnesse2e-main/openclaw",
        "identity": { "name": "编程助手", "emoji": "🧑‍💻" }
      }
    ]
  },
  "bindings": [
    {
      "type": "route",
      "agentId": "coding-assistant",
      "match": { "channel": "feishu", "accountId": "coding" }
    }
  ],
  "channels": {
    "feishu": {
      "accounts": {
        "coding": {
          "appId": "向管理员获取",
          "appSecret": "向管理员获取"
        }
      }
    }
  }
}
```

### 3. 验证连通性

```bash
openclaw status --deep
# Health 表中 Feishu 显示 OK (coding:coding:ok) 即正常
```

### 4. 填写 USER.md

填入你的名字、时区等，助手每次会话都会读取。

---

## Harness 启动

| 路线 | 命令 |
|------|------|
| Claude Code（默认，同事不受影响）| `./start.sh` |
| Copilot（本路线）| `HARNESS_CLAUDE_COMMAND="python3 engine/copilot_shim.py" ./start.sh` |

切换方式详见 `TOOLS.md`。

---

## OpenClaw 系统文件位置（供排查问题）

| 路径 | 说明 |
|------|------|
| `~/.openclaw/openclaw.json` | 主配置文件 |
| `~/.openclaw/agents/coding-assistant/` | agent 运行时状态、sessions |
| `~/.npm-global/lib/node_modules/openclaw` | 主程序 |
| `~/Library/LaunchAgents/ai.openclaw.gateway.plist` | 后台服务 |

---

## 进度跟进

| 日期 | 事项 |
|------|------|
| 2026-04-11 | 初始化，梳理系统配置和 agent 结构 |
| 2026-04-11 | workspace 迁移到 openclaw/ 子目录 |
| 2026-04-11 | copilot-cli skill 从 managed 迁移到 workspace |
| 2026-04-11 | 写 copilot_shim.py，实现双路线非侵入式切换 |
| 2026-04-11 | AGENTS.md 更新为 harness API 调度流程 |
