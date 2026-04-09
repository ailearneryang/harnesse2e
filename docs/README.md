# Harness Control Plane - 完整介绍文档

## 一、概述

**Harness Control Plane** 是一套可运行的长时任务编排框架，围绕 `Feishu -> Claude Code CLI -> Review -> QA -> Gerrit` 主链构建，目标是让用户能在 `localhost` 实时看到 harness 的整个执行过程，并且在关键节点人工接管。

它的核心理念是：**让多个 Agent 像工厂流水线一样自动协作，但保持全链路可观测、可暂停、可恢复、可人工介入。**

---

## 零、当前实现状态

当前仓库已经落地了一个可运行 MVP：

1. Web 请求入口：`POST /api/requests`
2. 飞书 webhook 入口：`POST /api/feishu/webhook`
3. Claude Code CLI 适配层：优先真实调用，未配置时自动降级到 simulation mode
4. 多阶段 pipeline：`intake -> planning -> requirements -> design -> development -> code_review -> security_review -> testing -> delivery`
5. 实时 UI：`GET /`，通过 SSE 订阅 `/api/stream`
6. 人工介入：审批列表与批准/拒绝接口
7. Gerrit 交付：将当前 repo 的 `HEAD` 推送到 `refs/for/<branch>%topic=<task_id>`
8. 状态持久化：任务、审批、事件、transcript、产物摘要均落盘

---

## 零点一、启动方式

安装依赖：

```bash
pip install -r requirements/runtime.txt
```

启动服务：

```bash
python engine/pipeline_runner.py --harness-dir . --web-port 8080
```

浏览器访问：

```text
http://localhost:8080
```

如果你还没有配置 Claude Code CLI，可先使用默认的 simulation mode；如果要切到真实 CLI，把 `data/integration_settings.json` 或 `settings.example.json` 中的 `claude.simulate` 改成 `false`，并配置 `target_repo`。

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    AutoDev Harness 架构                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  输入层: specs/pending/ (文件监听触发)               │    │
│  └────────────────────┬────────────────────────────────┘    │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  执行层: 四阶段流水线                                │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│    │
│  │  │ 需求分析 │→│ 系统设计 │→│ 代码开发 │→│质量测试 ││    │
│  │  │ Agent    │ │ Agent    │ │ Agent    │ │ Agent  ││    │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘│    │
│  │       ↑              ↑            ↑          │       │    │
│  │       └──────────────┴────────────┴──────────┘       │    │
│  │                  反馈回流循环                         │    │
│  └────────────────────┬────────────────────────────────┘    │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  质控层: 独立评审 + 一致性检测                       │    │
│  │  ┌────────────┐ ┌──────────────┐ ┌───────────────┐ │    │
│  │  │ 产物评审   │ │ 一致性检测   │ │ 变更影响分析  │ │    │
│  │  │ Agent      │ │ Checker      │ │ Analyzer      │ │    │
│  │  └────────────┘ └──────────────┘ └───────────────┘ │    │
│  └────────────────────┬────────────────────────────────┘    │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  保障层                                             │    │
│  │  上下文蒸馏 │ 产物版本控制 │ 预算控制 │ 人工介入协议 │    │
│  └────────────────────┬────────────────────────────────┘    │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  可观测层: Web Dashboard + 状态持久化               │    │
│  │  ┌──────────────────────────────────────────────┐   │    │
│  │  │  实时进度 │ 质量评分 │ 成本统计 │ 告警推送  │   │    │
│  │  └──────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  存储层: pipeline_state.json + artifacts + versions │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、目录结构详解

```
harness/
├── pipeline.yaml                 # 流水线配置（阶段定义、状态转移、人工介入规则）
├── budget.yaml                   # 预算与资源控制
├── review_protocol.yaml          # 产物评审协议（各阶段评审标准）
│
├── specs/                        # 功能规范输入
│   ├── pending/                  # 待处理（放入新规范到这里）
│   │   └── demo_user_login.md    # 示例：用户登录功能规范
│   └── processed/                # 已处理
│
├── requirements/                 # 需求阶段产物
│   └── requirements_spec.md      # 需求规格说明书
│
├── design/                       # 设计阶段产物
│   ├── architecture.md           # 系统架构设计
│   ├── api_design.md             # API 接口设计
│   ├── data_model.md             # 数据模型设计
│   ├── mockups/                  # UI 原型图
│   └── diagrams/                 # 架构图
│
├── src/                          # 开发阶段产物（源码）
│
├── tests/                        # 测试阶段产物
│   ├── cases/                    # 测试用例
│   └── reports/                  # 测试报告
│       └── test_report.md
│
├── agents/                       # Agent 角色定义
│   ├── agents.yaml               # 角色 Prompt 模板与能力定义
│   └── identities.yaml           # WorkBuddy IDENTITY.md 模板
│
├── engine/                       # 核心引擎
│   ├── state_machine.py          # 状态机（状态转移、重试、告警、持久化）
│   ├── pipeline_runner.py        # 流水线运行器（三层循环、Web API）
│   ├── reviewers/                # 质控组件
│   │   ├── consistency_checker.py    # 跨阶段一致性检测
│   │   └── change_impact_analyzer.py # 变更影响分析
│   └── distillers/               # 上下文管理
│       └── context_distiller.py      # 上下文蒸馏器
│
├── dashboard/                    # Web Dashboard
│   └── templates/
│       └── index.html            # 可视化监控页面
│
├── data/                         # 运行时数据
│   ├── pipeline_state.json       # 状态快照（断点续跑）
│   ├── review_results/           # 评审结果
│   ├── consistency/              # 一致性检查报告
│   ├── changes/                  # 变更记录
│   ├── distilled/                # 蒸馏后的上下文
│   └── versions/                 # 产物版本历史
│
└── docs/                         # 文档
    └── README.md                 # 本文件
```

---

## 四、五大核心设计详解

### 4.1 三层循环嵌套机制

```
主循环 (Feature Loop)
├── while True:
│   ├── 检测 specs/pending/ 是否有新规范
│   ├── 有 → 处理完整流水线
│   ├── 无 → sleep(poll_interval) 继续轮询
│   │
│   ├── 阶段重试循环 (Stage Retry Loop)
│   │   ├── for attempt in range(max_retries):
│   │   │   ├── 执行阶段
│   │   │   ├── 评审产物
│   │   │   ├── 通过 → break
│   │   │   └── 不通过 → 重试
│   │   └── 超过次数 → 退回或暂停
│   │
│   └── 反馈回流循环 (Feedback Loop)
│       ├── 测试通过 → DONE → IDLE
│       ├── 有 Bug → 退回 DEVELOPMENT
│       ├── 需求问题 → 退回 REQUIREMENTS
│       └── 设计不一致 → 退回 DESIGN
```

### 4.2 独立产物评审协议

每个阶段完成后，由**独立的 review-agent**（不是产出者本身）评审：

```
评审维度（需求阶段为例）：
├── 功能完整性 (25%) - 所有功能点是否识别
├── 验收标准   (25%) - 是否有 Given/When/Then
├── 无歧义性   (20%) - 是否有模糊描述词
├── 非功能需求 (15%) - 是否量化
└── 优先级分类 (15%) - 是否 P0~P3 分级
```

每条标准独立打分 → 加权总分 → ≥80 分通过，否则退回重做。

### 4.3 上下文蒸馏机制

长流水线上下文爆炸问题的解决方案：

```
需求文档 (5000字) → [蒸馏器] → 结构化摘要 (1500字)
    ├── 关键决策列表
    ├── 接口契约摘要
    ├── 数据实体列表
    └── 未解决问题

设计文档 (8000字) → [蒸馏器] → 结构化摘要 (2000字)
    ├── API 路径列表
    ├── 数据模型 ER 摘要
    └── 技术选型决策
```

跨阶段交接时，传递的是**蒸馏后的摘要包**，而非原始文档。

### 4.4 跨阶段一致性检测

自动检查三条一致性链路：

```
1. 需求↔设计：
   - 设计中的每个功能模块是否追溯到需求编号
   - 设计中是否有超出需求范围的功能

2. 设计↔代码：
   - API 路径是否与设计文档一致
   - 数据模型字段是否对齐

3. 需求↔测试：
   - 每个需求功能点是否有对应测试用例
   - 测试用例的 AC 与需求 AC 是否一致
```

产出追溯矩阵（Traceability Matrix）：

| 需求编号 | 设计文档 | 代码模块 | 测试用例 | 覆盖度 |
|---------|---------|---------|---------|--------|
| F001    | ✅      | ✅      | ✅      | full   |
| F002    | ✅      | ✅      | ❌      | partial|
| F003    | ❌      | ❌      | ❌      | none   |

### 4.5 预算与成本控制

```yaml
预算维度：
├── Token 限制: 每个 Feature 500K tokens
├── 时间限制: 每个 Feature 120 分钟
├── 重试限制: 单阶段 3 次，总计 10 次
├── 告警阈值: 80% 使用量发出警告
└── 硬限制: 95% 使用量强制暂停
```

---

## 五、Agent 角色定义

### 5.1 五个 Agent 角色

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| **requirements-analyst** | 需求分析 | 功能规范 | requirements_spec.md |
| **system-architect** | 系统设计 | 需求规格 | architecture.md + api_design.md + data_model.md |
| **developer** | 代码开发 | 设计文档 | src/ 源码 |
| **qa-engineer** | 质量测试 | 源码+需求 | 测试用例 + 测试报告 |
| **review-agent** | 独立评审 | 阶段产物 | 评分 + 改进建议 |

### 5.2 在 WorkBuddy 多 Agent 模式中的使用

1. 为每个 Agent 创建独立的 `.workbuddy/IDENTITY.md`（`agents/identities.yaml` 提供模板）
2. Team Lead 通过 `send_message` 串行调度
3. 每个 Agent 完成后通过 `send_message` 向 Team Lead 汇报
4. Team Lead 根据评审结果决定下一步

---

## 六、Web Dashboard

### 访问方式
启动流水线后，浏览器打开 `http://localhost:8080`

### 监控面板
```
┌─────────────────────────────────────────────┐
│  Pipeline Overview                          │
│  📋需求 → 🏗️设计 → 💻开发 → 🧪测试 → ✅完成  │
│  [状态动画显示当前阶段]                       │
├──────────────────┬──────────────────────────┤
│  Token Budget    │  Activity Feed           │
│  [环形图+百分比]  │  [实时滚动日志]           │
│                  │                          │
├──────────────────┤  🤖 design-agent...      │
│  Review Scores   │  ✅ 需求评审通过...       │
│  需求 ██████ 92  │  📝 需求分析完成...       │
│  设计 █████░░ -- │                          │
│  开发 ░░░░░░ -- │                          │
│  测试 ░░░░░░ -- │                          │
├──────────────────┼──────────────────────────┤
│  Alerts          │  追溯矩阵 / 一致性        │
│  ⚠️ 3处模糊描述  │  F001 ✅✅✅ full         │
│                  │  F002 ✅✅❌ partial       │
└──────────────────┴──────────────────────────┘
```

### API 端点
```
GET  /api/status     - 流水线状态摘要
GET  /api/state      - 完整状态机数据
GET  /api/budget     - 预算状态
GET  /api/alerts     - 告警列表
GET  /api/activities - 活动日志
GET  /api/reviews    - 评审历史
POST /api/control/pause   - 暂停流水线
POST /api/control/resume  - 恢复流水线
POST /api/control/stop    - 停止流水线
```

---

## 七、快速启动指南

### 方式一：配合 WorkBuddy 多 Agent（推荐）

```
1. 复制 harness/ 模板到项目目录
2. 在 WorkBuddy 中创建团队，添加 5 个 Agent 成员
3. 为每个 Agent 配置 IDENTITY.md（参考 agents/identities.yaml）
4. 将功能规范放入 specs/pending/
5. Team Lead 启动流水线调度
```

### 方式二：命令行运行

```bash
# 安装依赖
pip install flask

# 启动流水线（持续模式）
cd harness
python engine/pipeline_runner.py --harness-dir . --web-port 8080

# 单次运行（处理一个规范后退出）
python engine/pipeline_runner.py --once

# 不启动 Web Dashboard
python engine/pipeline_runner.py --no-web
```

### 方式三：独立使用各组件

```python
# 只使用一致性检查器
from engine.reviewers.consistency_checker import ConsistencyChecker
checker = ConsistencyChecker("/path/to/harness")
results = checker.run_all_checks()

# 只使用变更影响分析
from engine.reviewers.change_impact_analyzer import ChangeImpactAnalyzer
analyzer = ChangeImpactAnalyzer("/path/to/harness")
impact = analyzer.analyze_change("修改登录密码规则为至少12位")

# 只使用上下文蒸馏器
from engine.distillers.context_distiller import ContextDistiller
distiller = ContextDistiller("/path/to/harness")
ctx = distiller.distill("requirements", long_content, "requirements_spec.md")
```

---

## 八、配置定制

### 修改评审标准
编辑 `review_protocol.yaml`，调整各阶段的评审维度和权重。

### 修改预算限制
编辑 `budget.yaml`，调整 Token 限制、时间限制、告警阈值。

### 修改流水线行为
编辑 `pipeline.yaml`，调整：
- 阶段超时时间
- 最大重试次数
- 人工介入触发条件
- 轮询间隔

### 添加新阶段
在 `pipeline.yaml` 的 `stages` 中添加新阶段定义，在 `agents/agents.yaml` 中定义对应 Agent。

---

## 九、设计哲学

1. **产物驱动**：每个阶段有明确的输入/输出文件，而非模糊的"信息传递"
2. **独立评审**：产出者不评审自己的产物，由独立的 review-agent 负责质量把关
3. **可追溯**：需求→设计→代码→测试全链路可追溯，任意变更可分析影响范围
4. **渐进式自动化**：从 STATUS.md → Web Dashboard → 告警推送，按需叠加
5. **安全降级**：预算耗尽、重试超限、检测到歧义时自动暂停，等人工介入
6. **断点续跑**：所有状态持久化，进程中断后可从断点恢复
