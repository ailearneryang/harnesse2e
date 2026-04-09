# API Design - 跳跳棋

## Suggested Endpoints
- POST /api/requests
- POST /api/feishu/webhook
- GET /api/stream
- POST /api/approvals/{taskId}/{approvalId}/resolve

## Notes
I'll start by reading the requirements specification to understand what needs to be designed, then create the architecture, API, and data model design documents.
Now let me create the design directory and start writing the three design documents.
Now I'll create all three design documents in parallel.
Let me verify the output files are complete:
All three design documents have been created. Let me provide a summary of the deliverables.

---

## 设计文档交付摘要

已完成三份设计文档，涵盖跳跳棋的完整系统设计：

### 📐 `harness/design/architecture.md` (571行)
- **系统上下文图 (Level 1)**: 浏览器环境、纯前端、无外部依赖
- **容器图 (Level 2)**: UI 层 / 控制层 / 模型层分层架构
- **组件图 (Level 3)**: 9 个模块（Board, Renderer, Rules, GameState, AI, InputHandler, GameController, UIOverlay, Audio），预估总 ~920 行代码
- **核心数据流**: 玩家移动流程、AI 回合流程、游戏生命周期状态机
- **坐标系统**: 立方坐标系 (q,r,s)，含像素映射公式
- **AI 策略**: 启发式评估函数（距离改善 + 跳跃奖励 + 聚集奖励）
- **动画系统**: 动画队列 + 输入锁定机制
- **悔棋机制**: 单步快照 + 恢复策略
- **可观测性**: 控制台日志 + 性能计时
- **恢复路径**: 7 种错误场景及恢复策略
- **响应式设计**: 自适应缩放 + 触屏适配

### 📡 `harness/design/api_design.md` (717行)
- **10 种数据类型**: HexCoord, Piece, Move, GamePhase, UndoSnapshot 等
- **9 个模块、40+ 公共方法**: 完整的 Request/Response 签名
- **模块间调用矩阵**: 清晰的读/写依赖关系
- 每个接口标注来源需求编号

### 💾 `harness/design/data_model.md` (526行)
- **ER 图**: GameSession → Player → Piece → HexCoord 关系图
- **9 个数据结构**: 含完整字段类型、约束、初始值
- **棋盘位置数据**: 121 位置分区（6 三角区 + 中央菱形）
- **视觉常量**: 颜色定义及 WCAG 对比度验证
- **状态转换规则**: GamePhase + TurnSubState 完整状态表
- **8 条数据完整性约束**
- **内存占用估算**: ~16KB

### ✅ 每个设计决策均标注了来源需求编号（F001~F016, NFR001~NFR005），确保完整可追溯。

VERDICT: PASS
All three design documents have been created. Let me provide a summary of the deliverables.

---

## 设计文档交付摘要

已完成三份设计文档，涵盖跳跳棋的完整系统设计：

### 📐 `harness/design/architecture.md` (571行)
- **系统上下文图 (Level 1)**: 浏览器环境、纯前端、无外部依赖
- **容器图 (Level 2)**: UI 层 / 控制层 / 模型层分层架构
- **组件图 (Level 3)**: 9 个模块（Board, Renderer, Rules, GameState, AI, InputHandler, GameController, UIOverlay, Audio），预估总 ~920 行代码
- **核心数据流**: 玩家移动流程、AI 回合流程、游戏生命周期状态机
- **坐标系统**: 立方坐标系 (q,r,s)，含像素映射公式
- **AI 策略**: 启发式评估函数（距离改善 + 跳跃奖励 + 聚集奖励）
- **动画系统**: 动画队列 + 输入锁定机制
- **悔棋机制**: 单步快照 + 恢复策略
- **可观测性**: 控制台日志 + 性能计时
- **恢复路径**: 7 种错误场景及恢复策略
- **响应式设计**: 自适应缩放 + 触屏适配

### 📡 `harness/design/api_design.md` (717行)
- **10 种数据类型**: HexCoord, Piece, Move, GamePhase, UndoSnapshot 等
- **9 个模块、40+ 公共方法**: 完整的 Request/Response 签名
- **模块间调用矩阵**: 清晰的读/写依赖关系
- 每个接口标注来源需求编号

### 💾 `harness/design/data_model.md` (526行)
- **ER 图**: GameSession → Player → Piece → HexCoord 关系图
- **9 个数据结构**: 含完整字段类型、约束、初始值
- **棋盘位置数据**: 121 位置分区（6 三角区 + 中央菱形）
- **视觉常量**: 颜色定义及 WCAG 对比度验证
- **状态转换规则**: GamePhase + TurnSubState 完整状态表
- **8 条数据完整性约束**
- **内存占用估算**: ~16KB

### ✅ 每个设计决策均标注了来源需求编号（F001~F016, NFR001~NFR005），确保完整可追溯。

VERDICT: PASS