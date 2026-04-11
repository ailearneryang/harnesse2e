---
name: cockpit-middleware-architecture
description: 'Generate, revise, 补全 or重写 car middleware, cockpit middleware, IVI middleware architecture from PRD,需求文档,requirements/requirements_spec.md or feature specs. Use for Linux/QNX/Android cross-OS 架构设计, 中间件分层, 服务拓扑, 通信矩阵, 资源预算, 诊断, 安全 and design/architecture.md.'
---

# Cockpit Middleware Architecture

## 目标

该技能用于车载中间件和座舱域项目的架构生成与修订，重点处理多 OS、多进程、多通信机制和多语言协同下的系统边界设计。

## 何时使用

- 输入需求涉及 Linux、QNX、Android 中任意一种或多种操作系统。
- 需求涉及车机中间件、系统服务、座舱域平台、跨进程通信、系统集成、诊断、升级或高可靠运行。
- 需要从 PRD、需求规格说明书、`requirements/requirements_spec.md` 生成 `design/architecture.md`。

## 输入重点

执行前应尽量识别以下信息，若缺失则显式写入"假设与限制"：

- 业务目标、核心功能、FR、NFR。
- 目标硬件平台、SoC、内存、存储、CPU 预算。
- OS 组合：Linux、QNX、Android 或异构组合。
- 进程/服务边界、部署方式、启动方式、升级方式。
- 通信方式：Binder、PPS、FDBUS、SOME/IP、Socket、共享内存、HTTP 等。
- 语言组合：Java、C++，以及它们的桥接方式。
- 诊断、日志、安全、权限、DFMEA、再发防止约束。

## 执行步骤

1. 读取需求、现有架构文档和领域规范。
2. 基于 [车载中间件架构模板](./assets/cockpit-architecture-template.md) 组织主文档结构。
3. 先确定三层结构：应用层、中间件层、驱动/系统服务层。
4. 再确定 OS 边界、进程边界、服务边界、语言边界和通信矩阵。
5. 最后补齐安全、可观测性、部署升级、诊断、资源预算和故障隔离设计。

## 强制产出内容

- 架构驱动因素与质量属性排序。
- 系统上下文图、模块图、部署图、关键动态行为图。
- OS / 进程 / 服务 / 语言边界表。
- 通信方式选型矩阵与分工理由。
- 启动、内存、CPU、稳定性、升级恢复等资源预算或目标。
- 安全、权限、日志、指标、告警、诊断和回滚设计。

## 平台组合策略

- Linux + QNX：重点描述跨 OS 通信、资源隔离、时延预算、故障域与重启策略。
- Android + Linux：重点描述 Framework 层与 native daemon 的边界、Binder 与 native IPC 分工。
- Android + QNX：重点描述 Android 应用域与 QNX 服务域的责任划分、跨域代理与错误传播。
- Java + C++：重点描述 JNI/AIDL/Socket/FFI 桥接、线程模型和异常语义转换。

## 需求追溯标注规则

- 行内追溯使用纯文本括号格式，例如 `（FR-001）` 或 `[FR-001]`，**不能**使用 Markdown 引用链接语法（即不能写成 `[FR-001][FR-001]` 或在文末定义 `[FR-001]: ../requirements/...`）。
- 文档末尾**禁止**出现任何形如 `[FR-xxx]: path`、`[NFR-xxx]: path` 或技能路径链接定义块。
- 需求编号仅作为行内文本标注，不需要可点击链接。

## 注意事项

- 不要用"服务很多"冒充架构设计，必须写清服务职责、归属和交互。
- 不要忽略启动时序、电源状态、升级回滚、诊断闭环和资源预算。
- 不要把通信方式写成清单，必须说明每种方式的适用边界。

## 分块写入（强制）

为避免 API 超时，禁止一次性生成完整架构文档。必须分块：

1. Write 创建文件：只写标题、目录、架构驱动因素、系统上下文（500-800 字）
2. Edit 追加：模块划分、服务边界、通信矩阵
3. Edit 追加：安全设计、可观测性、部署升级
4. Edit 追加：资源预算、诊断、风险与待确认项

每次写入后确认成功再继续。
