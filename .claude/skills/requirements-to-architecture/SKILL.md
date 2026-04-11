---
name: requirements-to-architecture
description: 'Generate, revise, 补全, 重写 or收口 architecture documents from PRD,需求文档,需求规格说明书,requirements/requirements_spec.md or feature specs. Use for 输出 design/architecture.md, and when requested also design/api_design.md and design/data_model.md, with API 边界, 模块划分, 数据流, 状态流, 技术选型, 安全设计 and 可观测性设计 for backend, platform, Android, IVI and cockpit projects.'
---

# Requirements To Architecture

## 目标

该技能用于把需求文档稳定转换为架构文档，重点不是"写一篇大而全的说明文"，而是输出可以直接指导设计评审、接口设计和后续开发分层的架构结果。

## 何时使用

- 已有 PRD、需求规格说明书、`requirements/requirements_spec.md`、功能清单或需求评审纪要，需要产出架构文档。
- 已有旧版架构文档，需要根据新增需求补全、重写或收口。
- 需要把业务需求映射为模块、接口、数据模型、部署拓扑和运行约束。
- 需要为 Android、IVI、车机、座舱域、中后台平台或通用业务系统给出务实的架构方案。

## 输入

执行前优先收集以下输入，缺一项时允许做显式假设：

- 需求主文档：例如 `requirements/requirements_spec.md`、PRD、需求规格说明书。
- 已有架构或设计文档：例如 `design/architecture.md`、`design/api_design.md`、`design/data_model.md`。
- 领域约束与基准文档：例如企业架构规范、平台约束、合规要求。
- 交付约束：运行环境、团队规模、周期、上线方式、兼容性要求。

## 默认输出

- 主输出优先写入用户指定路径。
- 若未指定路径，优先选择仓库既有命名约定：`design/architecture.md`。
- 若用户同时要求接口与数据设计，可在此基础上继续补充 `design/api_design.md` 与 `design/data_model.md`，但主任务仍以架构文档为中心。
- 当补充 `design/api_design.md` 与 `design/data_model.md` 时，必须与主架构文档保持术语、模块边界、状态机、错误码和集成边界一致，不能各写一套。
- 主架构文档优先基于 `./assets/architecture-template.md` 组织结构；API 设计文档优先基于 `./assets/api-design-template.md`；数据模型设计文档优先基于 `./assets/data-model-template.md`。

## 执行步骤

1. 读取需求与现有上下文。
2. 提炼业务目标、FR、NFR、风险、假设与限制。
3. 选择合适的架构模式并说明备选方案取舍。
4. 完成系统上下文、模块、数据流、部署和关键动态行为设计。
5. 按模板分别补齐架构、API、数据模型三份文档的结构化章节。
6. 落实模块职责、接口约束、安全、可观测性、部署和演进策略。
7. 使用模板自检是否缺失关键章节，如有缺口继续修订。

## Android / IVI / 座舱专项规则

- 分层必须清晰，UI、Domain、Data、System Adapter 的依赖方向明确。
- 若同时存在轻量接口调用与大文件传输，必须给出双通道隔离策略。
- 安装、下载、升级、卸载等状态必须定义单一事实来源，避免前台状态臆造。
- 必须补充车辆状态、登录态、网络状态、存储空间、权限和后台运行限制的拦截设计。
- 必须给出启动耗时、内存、CPU、稳定性、恢复能力等资源预算或目标。

## 需求追溯标注规则

- 行内追溯使用纯文本括号格式，例如 `（FR-001）` 或 `[FR-001]`，**不能**使用 Markdown 引用链接语法（即不能写成 `[FR-001][FR-001]` 或在文末定义 `[FR-001]: ../requirements/...`）。
- 文档末尾**禁止**出现任何形如 `[FR-xxx]: path` 或 `[NFR-xxx]: path` 的链接定义块。
- 需求编号仅作为行内文本标注，不需要可点击链接。

## 输出质量要求

- 每个关键设计决策都应能追溯到需求、约束或风险。
- 文档应兼顾静态结构与动态行为，避免只有分层图没有运行链路。
- 架构方案必须能支撑后续 API 设计、数据模型设计、测试策略和代码结构。
- 若需求存在信息缺口，要显式写入"假设与限制"，不能静默忽略。
