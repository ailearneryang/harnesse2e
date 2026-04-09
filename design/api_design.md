# API Design - 贪吃蛇

## Suggested Endpoints
- POST /api/requests
- POST /api/feishu/webhook
- GET /api/stream
- POST /api/approvals/{taskId}/{approvalId}/resolve

## Notes
I'll start by exploring the current codebase to understand the project context, then produce the three design documents.
Now let me read the requirements spec and the existing design stubs to understand what needs to be produced:
Now I have the full picture. The existing design documents are stubs from a failed previous attempt. I need to write complete design documents for this single-file HTML5 Canvas Snake game. Let me also check the review protocol to understand what the design reviewer expects:
Now I have everything I need. Let me write all three design documents. This is a pure frontend single-file game — no server, no REST API, no database. The "API" design must be adapted to describe the internal JavaScript interfaces, and the "data model" must describe the in-memory game state structures.
三份设计文档已全部完成，摘要如下：

---

## 设计产出总结

### 1. `design/architecture.md` — 系统架构设计
- **C4 模型三层图**：系统上下文图、容器图、组件图（全部 Mermaid 语法）
- **9 个核心组件**：GameLoop、StateManager、Snake、Food、ScoreManager、InputHandler、Renderer、AudioManager、SpeedController
- **游戏状态机**：IDLE → PLAYING → PAUSED → GAME_OVER，含状态转换图
- **数据流图**：从输入层 → 处理层 → 输出层的完整数据流
- **技术选型**：Canvas 2D、requestAnimationFrame + 累加器、Web Audio API、localStorage，每项标注需求来源
- **6 项已知风险**：触屏手势冲突、localStorage 不可用、AudioContext 限制、高 DPI 模糊、500 行限制、网格占满等

### 2. `design/api_design.md` — 内部接口设计
- 因无后端，文档定义为 **JavaScript 模块间公共接口**
- **8 个组件共 20+ 个接口方法**，每个接口包含：描述、参数类型、返回值类型、错误码、调用示例
- **核心循环伪代码**：完整的 GameLoop 每帧执行逻辑
- 键盘映射表、触屏手势处理流程、方向队列机制
- 接口调用关系 Mermaid 图

### 3. `design/data_model.md` — 数据模型设计
- **ER 图**（Mermaid 语法）：9 个实体及其关系
- **9 个实体的完整字段定义**：GameState、Snake、Segment、Direction、Food、Score、SpeedConfig、InputBuffer、RenderConfig
- 每个字段含类型、默认值、约束、来源需求编号
- **速度变化对照表**：11 级速度从 150ms 到 50ms
- **3 个时序图**：初始化、吃食物、游戏结束的完整数据流生命周期
- **完整运行时状态快照示例**
- localStorage 持久化方案与安全约束

所有设计决策均标注了来源需求编号（REQ-F001~F014, NFR001~NFR005），满足评审协议 DES-C03 的追溯性要求。
三份设计文档已全部完成，摘要如下：

---

## 设计产出总结

### 1. `design/architecture.md` — 系统架构设计
- **C4 模型三层图**：系统上下文图、容器图、组件图（全部 Mermaid 语法）
- **9 个核心组件**：GameLoop、StateManager、Snake、Food、ScoreManager、InputHandler、Renderer、AudioManager、SpeedController
- **游戏状态机**：IDLE → PLAYING → PAUSED → GAME_OVER，含状态转换图
- **数据流图**：从输入层 → 处理层 → 输出层的完整数据流
- **技术选型**：Canvas 2D、requestAnimationFrame + 累加器、Web Audio API、localStorage，每项标注需求来源
- **6 项已知风险**：触屏手势冲突、localStorage 不可用、AudioContext 限制、高 DPI 模糊、500 行限制、网格占满等

### 2. `design/api_design.md` — 内部接口设计
- 因无后端，文档定义为 **JavaScript 模块间公共接口**
- **8 个组件共 20+ 个接口方法**，每个接口包含：描述、参数类型、返回值类型、错误码、调用示例
- **核心循环伪代码**：完整的 GameLoop 每帧执行逻辑
- 键盘映射表、触屏手势处理流程、方向队列机制
- 接口调用关系 Mermaid 图

### 3. `design/data_model.md` — 数据模型设计
- **ER 图**（Mermaid 语法）：9 个实体及其关系
- **9 个实体的完整字段定义**：GameState、Snake、Segment、Direction、Food、Score、SpeedConfig、InputBuffer、RenderConfig
- 每个字段含类型、默认值、约束、来源需求编号
- **速度变化对照表**：11 级速度从 150ms 到 50ms
- **3 个时序图**：初始化、吃食物、游戏结束的完整数据流生命周期
- **完整运行时状态快照示例**
- localStorage 持久化方案与安全约束

所有设计决策均标注了来源需求编号（REQ-F001~F014, NFR001~NFR005），满足评审协议 DES-C03 的追溯性要求。