# Architecture Design - 跳跳棋

Generated at: 2026-04-09
Task ID: task-20260409194003-2e64ec

---

## 1. 架构概述

### 1.1 架构决策

本项目为纯前端单文件游戏应用（F001~F016, NFR004），无后端服务、无网络请求（NFR005）。采用 **分层模块化架构**，在单个 HTML 文件内通过 JavaScript 模块模式（IIFE/命名空间）实现关注点分离。

**关键约束**（来源 NFR004）:
- 单个 HTML 文件交付（HTML + CSS + JavaScript 内联）
- 代码总量 ≤ 1000 行
- 无外部依赖

### 1.2 技术选型

| 技术 | 选择 | 来源需求 |
|------|------|----------|
| 渲染引擎 | HTML5 Canvas 2D | F001, NFR001 |
| 编程语言 | Vanilla JavaScript (ES6+) | NFR004 |
| 样式 | 内联 CSS | NFR004 |
| 构建工具 | 无 | 约束 5.1 |
| 音频 | Web Audio API | F016 |

---

## 2. 系统上下文图 (Level 1 - System Context)

```
┌─────────────────────────────────────────────────────┐
│                   浏览器环境                          │
│                                                     │
│  ┌───────────┐     事件      ┌─────────────────┐    │
│  │   用户     │ ──────────▶  │  跳跳棋游戏系统   │    │
│  │ (鼠标/触屏) │ ◀──────────  │  (单HTML文件)    │    │
│  └───────────┘     渲染      └─────────────────┘    │
│                                                     │
│  无外部依赖 / 无网络请求 / 无持久化                     │
└─────────────────────────────────────────────────────┘
```

**说明**: 系统完全自包含在浏览器中，用户通过鼠标点击/触屏操作与游戏交互，游戏通过 Canvas 渲染视觉反馈。无任何外部系统依赖（NFR005）。

---

## 3. 容器图 (Level 2 - Container)

由于是单文件应用，"容器"指逻辑上的功能模块：

```
┌──────────────────── index.html ─────────────────────┐
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │                  UI 层 (View)                   │  │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────────┐  │  │
│  │  │  Canvas   │ │ HUD 面板 │ │  对话框/弹窗   │  │  │
│  │  │  渲染器   │ │ (回合/步数)│ │(模式选择/教程) │  │  │
│  │  └────┬─────┘ └────┬─────┘ └──────┬────────┘  │  │
│  └───────┼────────────┼──────────────┼────────────┘  │
│          │            │              │                │
│  ┌───────┼────────────┼──────────────┼────────────┐  │
│  │       ▼            ▼              ▼             │  │
│  │              控制层 (Controller)                 │  │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────────┐  │  │
│  │  │ 输入处理器│ │ 游戏流程  │ │ 动画控制器    │  │  │
│  │  │(点击/触屏)│ │  控制器   │ │              │  │  │
│  │  └────┬─────┘ └────┬──────┘ └──────┬───────┘  │  │
│  └───────┼────────────┼──────────────┼────────────┘  │
│          │            │              │                │
│  ┌───────┼────────────┼──────────────┼────────────┐  │
│  │       ▼            ▼              ▼             │  │
│  │               模型层 (Model)                    │  │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────────┐  │  │
│  │  │ 棋盘模型 │ │ 规则引擎  │ │  AI 引擎     │  │  │
│  │  │(坐标系统) │ │(移动验证)  │ │ (启发式搜索)  │  │  │
│  │  └──────────┘ └───────────┘ └──────────────┘  │  │
│  │  ┌──────────┐ ┌───────────┐                    │  │
│  │  │ 游戏状态 │ │ 音效管理器│                    │  │
│  │  │ (State)  │ │  (Audio)  │                    │  │
│  │  └──────────┘ └───────────┘                    │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 4. 组件图 (Level 3 - Component)

### 4.1 模块清单与职责

| 模块名 | 命名空间 | 职责 | 来源需求 | 预估行数 |
|--------|---------|------|----------|---------|
| Board | `Board` | 坐标系统、位置管理、相邻计算 | F015, F001 | ~120 |
| Renderer | `Renderer` | Canvas 绘制棋盘/棋子/高亮/动画 | F001, F002, F003, F011 | ~200 |
| Rules | `Rules` | 合法移动计算、跳跃路径搜索、规则验证 | F004, F005, F006 | ~120 |
| GameState | `GameState` | 棋子位置、回合、步数、游戏阶段 | F002, F007, F009, F013 | ~80 |
| AI | `AI` | 启发式评估、移动选择 | F008 | ~100 |
| InputHandler | `InputHandler` | 鼠标/触屏事件 → 棋盘坐标映射 | F003, F015, NFR003 | ~60 |
| GameController | `GameController` | 游戏主循环、流程编排 | F007, F010, F012 | ~120 |
| UIOverlay | `UIOverlay` | HUD、弹窗、按钮 | F010, F012, F013, F014 | ~80 |
| Audio | `Audio` | 音效生成与播放 | F016 | ~40 |
| **合计** | | | | **~920** |

### 4.2 组件依赖关系

```
GameController (主入口)
├── InputHandler
│   └── Board (坐标映射)
├── GameState
│   └── Board (位置查询)
├── Rules
│   └── Board (相邻位置)
│   └── GameState (棋子位置)
├── AI
│   └── Rules (合法移动)
│   └── Board (距离计算)
│   └── GameState (当前局面)
├── Renderer
│   └── Board (坐标→像素)
│   └── GameState (棋子状态)
├── UIOverlay
│   └── GameState (回合/步数)
└── Audio
```

**依赖规则**: 
- Model 层模块互不依赖（Board, Rules, AI, GameState 之间单向依赖）
- View 层仅读取 Model 状态
- Controller 层编排所有模块

---

## 5. 核心数据流

### 5.1 玩家移动流程

```
[用户点击 Canvas]
       │
       ▼
InputHandler.onClick(pixelX, pixelY)
       │
       ├── Board.pixelToHex(px, py) → HexCoord
       │
       ▼
GameController.handleBoardClick(hexCoord)
       │
       ├── 状态: IDLE (未选子)
       │   ├── GameState.getPieceAt(hexCoord) → 是否本方棋子?
       │   ├── 是 → Rules.getLegalMoves(hexCoord, gameState) → Set<HexCoord>
       │   │       GameState.selectPiece(hexCoord)
       │   │       Renderer.drawHighlights(legalMoves)
       │   │       Audio.play('select')                    ← F003, F016
       │   └── 否 → 忽略
       │
       ├── 状态: SELECTED (已选子)
       │   ├── 点击合法目标?
       │   │   ├── 是(单步) → GameState.movePiece(from, to)
       │   │   │              Renderer.animateMove(from, to, 200ms)  ← F004, F011
       │   │   │              Audio.play('place')
       │   │   │              GameController.endTurn()               ← F007
       │   │   │
       │   │   ├── 是(跳跃) → GameState.movePiece(from, to)
       │   │   │              Renderer.animateMove(from, to, 150ms)  ← F005, F011
       │   │   │              Rules.getContinueJumps(to) → 有更多跳跃?
       │   │   │              ├── 有 → 状态 = JUMPING, 显示继续跳跃目标 + 结束按钮
       │   │   │              └── 无 → GameController.endTurn()
       │   │   │
       │   │   └── 否 → 取消选中 / 选中新棋子                ← F003
       │
       └── 状态: JUMPING (连跳中)
           ├── 点击可跳目标 → 执行跳跃，检查是否可继续     ← F005
           ├── 点击"结束回合" → GameController.endTurn()
           └── 无更多跳跃目标 → 自动 endTurn()
```

**来源需求**: F003, F004, F005, F006, F007, F011, F016

### 5.2 AI 回合流程

```
GameController.endTurn()
       │
       ├── GameState.switchTurn() → 切换到 AI 方
       ├── UIOverlay.showTurnIndicator('AI')              ← F007
       ├── InputHandler.disable()                          ← F007
       │
       ▼
AI.computeMove(gameState)  [异步, 使用 setTimeout 避免阻塞]
       │
       ├── 遍历所有 AI 棋子
       │   ├── Rules.getLegalMoves(piece, gameState)
       │   └── 对每个合法移动评估启发式分数
       │       ├── 距离增量（接近目标区域的程度）            ← F008
       │       ├── 跳跃深度奖励                             ← F008
       │       └── 已在目标区域棋子 → 降低优先级             ← F008
       │
       ├── 选择最优移动 (或连跳路径)
       │
       ▼
GameController.executeAIMove(move)
       │
       ├── Renderer.animateMove(path, 150ms/step)          ← F011
       ├── GameState.movePiece(from, to)
       ├── Audio.play('place')
       ├── GameController.checkWin() → 是否胜利?            ← F009
       │   ├── 是 → UIOverlay.showResult()
       │   └── 否 → GameController.endTurn() → 切回玩家
       └── InputHandler.enable()
```

**来源需求**: F007, F008, F009, F011

### 5.3 游戏生命周期状态机

```
     ┌──────────┐
     │  MENU    │  ← 模式选择界面 (F010)
     │          │
     └────┬─────┘
          │ 选择模式
          ▼
     ┌──────────┐
     │  INIT    │  ← 初始化棋盘与棋子 (F001, F002)
     │          │     显示教程 (F014, 首次)
     └────┬─────┘
          │
          ▼
     ┌──────────┐  endTurn()   ┌──────────┐
     │ PLAYER   │ ──────────▶  │ AI/P2    │  ← 对方回合
     │  TURN    │ ◀──────────  │  TURN    │
     └────┬─────┘  endTurn()   └────┬─────┘
          │                         │
          │    checkWin() = true    │
          ▼                         ▼
     ┌──────────┐
     │ GAME_OVER│  ← 显示结果 (F009)
     │          │     "再来一局" → MENU
     └──────────┘

     子状态 (PLAYER_TURN 内部):
     ┌────┐ select ┌──────────┐ move ┌──────────┐
     │IDLE│ ─────▶ │ SELECTED │ ───▶ │ANIMATING │──▶ endTurn / JUMPING
     └────┘        └──────────┘      └──────────┘
                       │ cancel            
                       ▼                   
                     IDLE                  
```

**来源需求**: F007, F009, F010

---

## 6. 坐标系统设计

### 6.1 坐标方案选择

**选择**: 立方坐标系 (Cube Coordinates) `(q, r, s)` 其中 `q + r + s = 0`

**理由** (来源 F015):
- 六方向邻居计算简单，无需区分奇偶行
- 距离计算直观: `distance = max(|Δq|, |Δr|, |Δs|)`
- 跳跃目标计算: `target = piece + 2 * direction`（对称性好）

### 6.2 棋盘位置编码

六角星棋盘 121 个有效位置定义为预计算集合 `VALID_POSITIONS: Set<string>`，key 为 `"q,r,s"` 字符串。

```
六个三角区域（每区 10 个位置）:
  Top (北):     player 2 起始区 / player 1 目标区
  Bottom (南):  player 1 起始区 / player 2 目标区
  
  其余4个角区在 2人模式下为空（不作为起始/目标）

中央区域: 61 个位置（菱形区域）
```

### 6.3 像素映射

```javascript
// Cube → Pixel (flat-top hexagon)
pixelX = centerX + size * (3/2 * q)
pixelY = centerY + size * (sqrt(3)/2 * q + sqrt(3) * r)

// Pixel → Cube (反向映射 + 最近邻舍入)
// 使用 cube_round 算法处理浮点误差
```

**来源需求**: F015, F001

---

## 7. AI 策略设计

### 7.1 评估函数

```
score(move) = w1 * distanceImprovement    // 向目标区域前进的距离增量
            + w2 * jumpBonus              // 跳跃（尤其连跳）额外奖励
            + w3 * centerPenalty          // 远离中心的惩罚（鼓励向对角移动）
            + w4 * groupBonus             // 棋子聚集奖励（利于互相跳跃）

权重参考: w1=10, w2=5, w3=-2, w4=3
```

### 7.2 AI 执行约束

- 决策时间 ≤ 2s（NFR001）—— 单层贪心搜索，无需深度搜索
- 使用 `setTimeout(computeMove, 500ms)` 模拟思考延迟，避免瞬间响应
- 连跳选择: 贪心选择累计得分最高的跳跃序列

**来源需求**: F008, NFR001

---

## 8. 动画系统设计

### 8.1 动画队列

```
AnimationController:
  queue: Animation[]
  isPlaying: boolean
  
  enqueue(animation) → 加入队列
  play() → 依次执行队列中动画
  onComplete() → 回调通知 GameController
  
Animation:
  type: 'move' | 'jump'
  from: HexCoord
  to: HexCoord
  duration: number (ms)
  easing: 'easeInOut'
```

### 8.2 动画参数

| 动画类型 | 持续时间 | 来源需求 |
|---------|---------|----------|
| 单步移动 | 200ms | F011 |
| 跳跃单步 | 150ms | F011 |
| 连跳总时间 | N × 150ms | F011 |

### 8.3 动画期间输入锁定

动画播放期间，`InputHandler.enabled = false`，所有点击事件被忽略（F011 AC3）。

---

## 9. 悔棋机制

### 9.1 快照策略

每次玩家移动前，保存当前状态快照:

```
undoSnapshot = {
  pieces: deepCopy(gameState.pieces),  // 棋子位置
  currentPlayer: gameState.currentPlayer,
  moveCount: { ...gameState.moveCount }
}
```

悔棋时恢复快照，重新渲染。仅保留最近一次快照（单步悔棋）。

**来源需求**: F012

### 9.2 悔棋可用条件

- 当前回合玩家刚完成移动
- 对手尚未开始行动
- 在人机模式下, AI 行动前的短暂窗口期
- 在双人模式下, 对方点击棋子之前

---

## 10. 可观测性 (Observability)

由于是纯前端游戏（NFR005 无网络），可观测性主要通过控制台日志实现：

### 10.1 日志级别

```javascript
const DEBUG = false; // 发布时设为 false

function log(level, module, message, data) {
  if (!DEBUG && level === 'debug') return;
  console[level](`[${module}] ${message}`, data || '');
}
```

### 10.2 关键日志点

| 模块 | 日志事件 | 级别 |
|------|---------|------|
| GameController | 回合切换 | info |
| Rules | 合法移动计算结果 | debug |
| AI | 评估分数、选择移动 | debug |
| Renderer | 帧率统计 | debug |
| InputHandler | 点击坐标映射 | debug |

### 10.3 性能度量

```javascript
// AI 决策计时
const t0 = performance.now();
const move = AI.computeMove(state);
const elapsed = performance.now() - t0;
log('info', 'AI', `决策耗时: ${elapsed.toFixed(1)}ms`);

// 渲染帧率
let frameCount = 0, lastFpsTime = 0;
function gameLoop(timestamp) {
  frameCount++;
  if (timestamp - lastFpsTime > 1000) {
    log('debug', 'Renderer', `FPS: ${frameCount}`);
    frameCount = 0; lastFpsTime = timestamp;
  }
  requestAnimationFrame(gameLoop);
}
```

**来源需求**: NFR001

---

## 11. 恢复路径 (Recovery Paths)

### 11.1 错误场景与恢复策略

| 场景 | 检测方式 | 恢复策略 | 来源需求 |
|------|---------|---------|----------|
| Canvas 不支持 | `!canvas.getContext` | 显示降级提示 "请使用现代浏览器" | NFR002 |
| AI 计算超时 (>2s) | `setTimeout` 计时器 | 使用随机合法移动替代 | F008, NFR001 |
| 合法移动为空 | `legalMoves.size === 0` | 跳过当前回合（自动 pass） | F006 |
| 棋盘点击越界 | `pixelToHex` 返回 null | 忽略点击，无响应 | F015 |
| 音频播放失败 | `try-catch` 包裹 | 静默跳过，不影响游戏 | F016 AC4 |
| 动画帧丢失 | `requestAnimationFrame` 回调检查 | 直接跳到动画结束状态 | F011 |
| 游戏状态不一致 | 棋子数量校验 | 重置到上一个有效快照或重新开始 | F006 |

### 11.2 防御性编程策略

```javascript
// 所有外部输入（鼠标事件）经过验证
function handleClick(e) {
  const hex = Board.pixelToHex(e.offsetX, e.offsetY);
  if (!hex) return;                         // 越界保护
  if (!Board.isValidPosition(hex)) return;  // 非法位置保护
  if (state.phase !== 'PLAYER_TURN') return; // 非法阶段保护
  if (state.isAnimating) return;            // 动画锁保护
  // ... 正常处理
}
```

---

## 12. 响应式设计

### 12.1 缩放策略

```javascript
function resize() {
  const maxW = window.innerWidth * 0.95;
  const maxH = window.innerHeight * 0.85; // 预留 HUD 空间
  const boardSize = Math.min(maxW, maxH);
  canvas.width = boardSize;
  canvas.height = boardSize;
  Board.recalculate(boardSize); // 重算像素映射参数
  Renderer.redraw();
}

window.addEventListener('resize', debounce(resize, 100));
```

**来源需求**: F001 AC3, NFR002

### 12.2 触屏适配

- 使用 `touchstart` 事件映射为 `click`（NFR002）
- 触屏点击的容差范围 ≥ 棋子半径 × 1.5
- 禁用 Canvas 区域的默认触屏行为（防止缩放/滚动）

---

## 13. 文件结构 (单文件内部组织)

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>跳跳棋</title>
  <style>
    /* ===== CSS 样式 (~50行) ===== */
    /* 布局、HUD、弹窗、按钮样式 */
  </style>
</head>
<body>
  <!-- ===== HTML 结构 (~20行) ===== -->
  <div id="game-container">
    <div id="hud"><!-- 回合信息、步数、按钮 --></div>
    <canvas id="board"></canvas>
  </div>
  <div id="modal"><!-- 模式选择/教程/结果弹窗 --></div>

  <script>
  'use strict';
  // ===== JavaScript (~850行) =====
  
  // --- 1. 常量与配置 ---
  // --- 2. Board 模块 (坐标系统) ---
  // --- 3. GameState 模块 (状态管理) ---
  // --- 4. Rules 模块 (规则引擎) ---
  // --- 5. AI 模块 ---
  // --- 6. Audio 模块 ---
  // --- 7. Renderer 模块 (Canvas 渲染) ---
  // --- 8. InputHandler 模块 ---
  // --- 9. UIOverlay 模块 ---
  // --- 10. GameController 模块 (主控) ---
  // --- 11. 入口 ---
  
  window.addEventListener('DOMContentLoaded', () => {
    GameController.init();
  });
  </script>
</body>
</html>
```

**来源需求**: NFR004

---

## 14. 需求追溯矩阵

| 需求编号 | 架构组件 | 设计章节 |
|---------|---------|---------|
| F001 | Board, Renderer | §4.1, §6, §12 |
| F002 | GameState, Renderer | §4.1, §5.3 |
| F003 | InputHandler, Renderer, Rules | §4.1, §5.1 |
| F004 | Rules, GameController | §4.1, §5.1 |
| F005 | Rules, GameController | §4.1, §5.1 |
| F006 | Rules | §4.1, §5.1, §11.1 |
| F007 | GameController, UIOverlay | §4.1, §5.2, §5.3 |
| F008 | AI | §4.1, §5.2, §7 |
| F009 | GameController, UIOverlay | §4.1, §5.3 |
| F010 | UIOverlay, GameController | §4.1, §5.3 |
| F011 | Renderer (AnimationController) | §4.1, §8 |
| F012 | GameController, GameState | §4.1, §9 |
| F013 | GameState, UIOverlay | §4.1 |
| F014 | UIOverlay | §4.1, §5.3 |
| F015 | Board | §4.1, §6 |
| F016 | Audio | §4.1, §11.1 |
| NFR001 | AI, Renderer, Rules | §7.2, §10.3 |
| NFR002 | Renderer, InputHandler | §12 |
| NFR003 | Renderer, UIOverlay | §4.1 |
| NFR004 | 全部 | §1.1, §4.1, §13 |
| NFR005 | 全部 | §1.1 |

---

*文档版本: v1.0 | 日期: 2026-04-09 | 作者: system-architect*
