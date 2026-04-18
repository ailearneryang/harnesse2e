# Harness Control Plane

## 概述

Harness Control Plane 是一个面向长运行任务的本地编排服务，围绕下面这条主链工作：

`Web / Feishu -> GitHub Copilot CLI shim -> 多阶段评审流水线 -> Gerrit / Build Verification`

当前实现重点解决三件事：

1. 让需求可以从 Web UI 或飞书进入队列。
2. 让任务按 pipeline stages 自动推进，并在需要时暂停等待人工处理。
3. 让每个任务的运行过程、产物、事件、审批和历史都能在本地持久化。

当前默认 agent 接线已经从旧版 Claude 兼容模式迁移到 GitHub Copilot CLI shim：`engine/copilot_shim.py` 会接收 Claude 风格参数，再转发给本机 `copilot` 命令执行。

---

## 当前实现状态

仓库里的当前可运行实现包括：

- Flask Web 服务与实时 Dashboard。
- 请求入口：`POST /api/requests`。
- 飞书 webhook 入口：`POST /api/feishu/webhook`。
- SSE 实时事件流：`GET /api/stream`。
- 任务控制：暂停、恢复、重试、删除、让出执行权。
- 流水线模板系统，支持内置模板和自定义模板。
- 任务级运行目录：每个 task 都有独立的 `runs/<task_id>/`。
- 任务历史 / lesson learned / project memory 接口。
- Gerrit 投递适配层。
- Build verification 与 HIL 适配接口占位。

默认 pipeline 顺序来自 `pipeline.yaml`：

1. `intake`
2. `planning`
3. `software-requirement-orchestrator`
4. `cockpit-middleware-architect`
5. `development`
6. `code_review`
7. `security_review`
8. `safety_review`
9. `testing`
10. `delivery`
11. `build_verification`

---

## 快速启动

### 方式一：推荐，直接用启动脚本

```bash
./start.sh
```

默认监听端口 `8080`，也可以显式传入：

```bash
./start.sh 8080
```

`start.sh` 会做这些事：

- 创建根目录 `.venv`。
- 创建 `feishu-claude-code/.venv`。
- 清理残留的 `engine/copilot_shim.py` 进程。
- 如果飞书开关开启，则同时拉起飞书 bot。
- 启动主服务：`engine/pipeline_runner.py --harness-dir <repo> --web-port <port>`。

注意：脚本只会在 `requirements/runtime.txt` 存在时安装根服务依赖；当前仓库没有这个文件，因此请确保当前 Python 环境已经具备运行所需依赖，至少要能导入 `flask` 和 `yaml`。

### 方式二：手动启动

```bash
python3 engine/pipeline_runner.py --harness-dir . --web-port 8080
```

启动后访问：

```text
http://localhost:8080
```

---

## 运行前准备

### 1. GitHub Copilot CLI

当前默认命令是：

```text
python3 engine/copilot_shim.py
```

shim 的行为是：

- 优先使用环境变量 `COPILOT_CLI_PATH`。
- 否则从 `PATH` 查找 `copilot`。
- 再否则尝试常见路径 `/opt/homebrew/bin/copilot` 和 `/usr/local/bin/copilot`。

如果找不到 `copilot`，任务执行会失败。

### 2. 配置文件

运行时配置文件是：

`data/integration_settings.json`

仓库里还提供了一个示例：

`settings.example.json`

当前实现会在启动时把默认值和现有配置合并后写回 `data/integration_settings.json`。

关键配置项：

```json
{
    "target_repo": ".",
    "budget_limit": 5000000,
    "copilot": {
        "command": "python3 engine/copilot_shim.py",
        "output_format": "stream-json",
        "simulate": false,
        "max_turns": 30,
        "hard_timeout_seconds": 3600,
        "idle_timeout_seconds": 3600
    },
    "feishu": {
        "enabled": true
    },
    "gerrit": {
        "enabled": false,
        "remote": "origin",
        "branch": "master",
        "topic_prefix": "harness"
    },
    "build_verification": {
        "enabled": false
    }
}
```

说明：

- `target_repo` 支持相对路径或绝对路径；相对路径会相对 `harness_dir` 解析。
- `copilot` 与 `claude` 配置会被归一化处理；当前运行实际上走 `copilot` 配置。
- `simulate=true` 时会走适配器里的模拟模式，不调用真实 CLI。

---

## 任务提交方式

### 1. Web UI

浏览器打开首页后，可直接通过 Dashboard 提交任务、查看事件、审批和下载产物。

### 2. JSON 请求

```bash
curl -X POST http://localhost:8080/api/requests \
    -H 'Content-Type: application/json' \
    -d '{
        "title": "更新 README",
        "text": "请根据当前代码实现更新 docs/README.md",
        "source": "web",
        "prioritize_running": false,
        "pipeline_template_id": "default"
    }'
```

### 3. 带附件的 multipart 请求

```bash
curl -X POST http://localhost:8080/api/requests \
    -F 'title=分析上传文档' \
    -F 'text=请结合附件生成设计建议' \
    -F 'files=@./requirements/ivi_app_store_requirements_spec.md' \
    -F 'pipeline_template_id=design-only'
```

当前上传限制由服务端硬编码：

- 最多 10 个文件。
- 单文件最大 10 MB。
- 总大小最大 25 MB。
- 支持文本、代码、Office、PDF 和常见图片类型。

如果只上传文件、不填 `text`，系统会自动补一段默认请求文本，让 agent 从标题和附件内容推断诉求。

### 4. 飞书 Webhook

启用飞书后，Webhook 入口为：

```text
POST /api/feishu/webhook
```

服务端会：

- 校验签名与去重。
- 从飞书 payload 提取 `title`、`text`、`chat_id`、`sender`。
- 自动创建任务并入队。

如果你需要飞书 bot 的长连接方案和本地部署方式，单独参考子项目 `feishu-claude-code/README.md`。

---

## Pipeline 与模板系统

### 默认 stages

默认 stage 定义在 `pipeline.yaml` 中，每个 stage 都绑定了默认 agent：

| Stage ID | 默认 Agent | 用途 |
|---|---|---|
| `intake` | `planner` | 请求接收与初步整理 |
| `planning` | `planner` | Sprint contract / 执行计划 |
| `software-requirement-orchestrator` | `software-requirement-orchestrator` | 需求规格编排 |
| `cockpit-middleware-architect` | `cockpit-middleware-architect` | 架构与设计产物 |
| `development` | `developer` | 实现修改 |
| `code_review` | `code-reviewer` | 代码评审 |
| `security_review` | `security-reviewer` | 安全评审 |
| `safety_review` | `safety-reviewer` | 安全合规评审 |
| `testing` | `unite-test` | 测试与验证 |
| `delivery` | `delivery-manager` | Gerrit 投递 |
| `build_verification` | `build-verifier` | 构建验证 |

### 内置模板

模板系统由 `engine/pipeline_template_manager.py` 管理，当前内置模板包括：

- `default`：完整流程。
- `quick-dev`：快速开发，适合小改动或 bug 修复。
- `design-only`：只做需求与设计。
- `cockpit-middleware`：车载中间件完整流程。

任务创建时可以通过 `pipeline_template_id` 选择模板。模板快照会保存到任务本身，因此后续修改默认模板不会影响已创建任务。

### 自定义 pipeline

可通过 API 直接更新当前运行中的自定义 pipeline：

- `GET /api/pipeline`
- `POST /api/pipeline`
- `POST /api/pipeline/reset`

也可以通过模板 API 做模板级 CRUD：

- `GET /api/pipeline-templates`
- `GET /api/pipeline-templates/<template_id>`
- `POST /api/pipeline-templates`
- `PUT /api/pipeline-templates/<template_id>`
- `DELETE /api/pipeline-templates/<template_id>`
- `POST /api/pipeline-templates/<template_id>/set-default`
- `GET /api/pipeline-templates/<template_id>/preview`
- `GET /api/pipeline-templates/available-stages`

---

## 人工介入与任务控制

当前实现支持两类人工介入：

### 1. 显式审批

当任务文本包含高风险关键词时，`design` 或 `delivery` 阶段可能触发人工审批。关键词包括：

- `security`
- `auth`
- `payment`
- `prod`
- `生产`
- `隐私`
- `删除数据`
- `权限`

相关接口：

- `GET /api/approvals`
- `POST /api/approvals/<task_id>/<approval_id>/resolve`

`resolution` 只能是：

- `approved`
- `rejected`

### 2. 任务调度控制

支持这些操作：

- `POST /api/tasks/<task_id>/retry`
- `POST /api/tasks/<task_id>/resume`
- `POST /api/tasks/<task_id>/pause`
- `POST /api/tasks/<task_id>/defer`
- `DELETE /api/tasks/<task_id>`
- `POST /api/control/pause`
- `POST /api/control/resume`

其中：

- `retry` 会从第一个未通过 stage 继续，已通过 stage 保留。
- `resume` 可带人工反馈重新排队。
- `defer` 用于请求当前任务在安全边界主动让出执行权。
- 运行中的任务不能直接删除。

---

## 运行时目录与持久化

### 全局运行时数据

主要位于 `data/`：

- `integration_settings.json`：运行配置。
- `runtime_state.json`：任务运行态快照。
- `runtime_events.jsonl`：事件流持久化。
- `pipeline_templates/`：模板 YAML 备份。
- `reports/`：全局报告。
- `transcripts/`：全局 transcript 数据。
- `tasks/`：任务级持久化记录。
- `harness_state.db`、`pipeline_state.db`：状态与模板存储。

### 单任务运行目录

每个任务都会创建：

```text
runs/<task_id>/
```

目录结构由运行器保证至少包含：

- `src/`
- `tests/`
- `tests/reports/`
- `reports/`
- `transcripts/`
- `uploads/`
- `context/`
- `deliverables/`
- 每个已配置 stage 的同名目录

同时会写入：

- `meta.json`：任务元数据。
- 对应 stage 产物，例如 `delivery/delivery.md`、`reports/build_verification.json`。

系统还会维护：

- `runs/latest` 符号链接。
- 如果符号链接失败，则回退为 `runs/latest.txt`。

运行器启动时会自动迁移旧的 `run_dir` 路径，把历史任务重映射到当前仓库下的 `runs/<task_id>`。

---

## 主要 API 一览

### 基础状态

- `GET /`：Dashboard 首页。
- `GET /assets/<path>`：前端静态资源。
- `GET /api/health`：健康检查。
- `GET /api/runtime`：完整运行态快照。
- `GET /api/events?since=<seq>`：增量事件查询。
- `GET /api/stream`：SSE 实时订阅。

### 任务查询与产物

- `GET /api/tasks`
- `GET /api/tasks/<task_id>`
- `GET /api/tasks/<task_id>/artifacts`
- `GET /api/tasks/<task_id>/artifacts/download?path=<abs_path>`
- `GET /api/tasks/<task_id>/artifacts/archive`

### 设置与 pipeline

- `GET /api/settings`
- `POST /api/settings`
- `GET /api/pipeline`
- `POST /api/pipeline`
- `POST /api/pipeline/reset`

### Memory API

当前已经实现：

- `GET /api/memory/history`
- `GET /api/memory/statistics`
- `GET /api/memory/lessons`
- `GET /api/memory/project`
- `POST /api/memory/import`

这些接口读取 `engine/memory_store.py` 维护的任务历史、失败经验和项目级记忆。

---

## Gerrit / Build Verification / HIL

### Gerrit

`delivery` 阶段会调用 Gerrit 适配层提交变更。默认策略仍然是：

```text
refs/for/<branch>%topic=<task_id>
```

若 `gerrit.enabled=false`，交付阶段会生成报告，但不会实际推送。

### Build Verification

`build_verification` 阶段已经有适配器和报告落盘逻辑：

- 结果写入 `runs/<task_id>/reports/build_verification.json`
- 开关由 `build_verification.enabled` 控制

当前这部分属于可接线状态，是否真的执行下游校验取决于配置和适配器实现。

### HIL

HIL 适配器已在运行器中注册，但目前更偏向预留能力，用于在 build verification 或上下文里暴露能力描述。

---

## 相关目录说明

当前仓库里和主服务强相关的目录如下：

- `engine/`：Flask API、调度器、适配器、状态与记忆系统。
- `dashboard/`：前端页面模板和静态资源。
- `data/`：运行时配置、数据库、事件和模板备份。
- `runs/`：每个任务的独立执行目录。
- `design/`：设计类产物样例。
- `requirements/`：需求类产物样例。
- `specs/pending/`：待处理规格输入。
- `specs/processed/`：已处理规格。
- `feishu-claude-code/`：飞书 bot 子项目。

---

## 已知注意事项

1. 根服务依赖文件 `requirements/runtime.txt` 目前不存在，`start.sh` 不会自动安装主服务依赖。
2. 主服务强依赖 Flask；如果环境里没有 `flask`，`engine/pipeline_runner.py` 会在启动时报错。
3. `yaml` 模块不可用时，pipeline YAML 加载和模板 YAML 备份能力会降级。
4. `copilot` CLI 不可执行时，若 `simulate=false`，真实任务运行会失败。
5. `build_verification` 和 `hil` 已接入调度框架，但是否真正执行外部流程依赖后续适配实现和配置。

---

## 最小自检

服务启动后，可以先做这三个检查：

```bash
curl http://localhost:8080/api/health
curl http://localhost:8080/api/runtime
curl http://localhost:8080/api/pipeline-templates
```

如果三者都返回 JSON，再提交一个最小任务：

```bash
curl -X POST http://localhost:8080/api/requests \
    -H 'Content-Type: application/json' \
    -d '{"title":"smoke test","text":"echo current pipeline status"}'
```

然后观察：

- Dashboard 首页。
- `GET /api/tasks`。
- `GET /api/stream`。
- 对应 `runs/<task_id>/` 目录是否产生 `meta.json` 和 stage 产物。
