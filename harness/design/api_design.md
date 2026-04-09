# API Design - 跳跳棋

Generated at: 2026-04-09
Task ID: task-20260409194003-2e64ec

---

## 1. 概述

本项目为纯前端单文件游戏，无 HTTP API。本文档定义 **模块间内部接口（Internal API）**，即各 JavaScript 模块对外暴露的公共方法签名、参数类型与返回值。这些接口是模块间通信的契约。

---

## 2. 数据类型定义

### 2.1 基础类型

```typescript
/** 立方坐标 (来源: F015) */
interface HexCoord {
  q: number;  // 列轴
  r: number;  // 行轴
  s: number;  // 约束: q + r + s === 0
}

/** 像素坐标 */
interface PixelCoord {
  x: number;
  y: number;
}

/** 棋子 */
interface Piece {
  id: string;         // 唯一标识: "p1_0" ~ "p1_9", "p2_0" ~ "p2_9"
  player: 1 | 2;      // 所属玩家
  position: HexCoord;  // 当前位置
}

/** 移动指令 */
interface Move {
  pieceId: string;
  from: HexCoord;
  to: HexCoord;
  path: HexCoord[];   // 完整路径 (连跳时含中间点)
  type: 'step' | 'jump';
}

/** 游戏模式 (来源: F010) */
type GameMode = 'pvai' | 'pvp';

/** 游戏阶段 (来源: F007, F009, F010) */
type GamePhase = 'MENU' | 'INIT' | 'PLAYER_TURN' | 'OPPONENT_TURN' | 'ANIMATING' | 'GAME_OVER';

/** 玩家回合子状态 */
type TurnSubState = 'IDLE' | 'SELECTED' | 'JUMPING';

/** 悔棋快照 (来源: F012) */
interface UndoSnapshot {
  pieces: Piece[];
  currentPlayer: 1 | 2;
  moveCount: { 1: number; 2: number };
}
```

---

## 3. Board 模块 API

**职责**: 坐标系统管理、棋盘拓扑查询（来源: F015, F001）

### 3.1 init

```
Board.init(canvasSize: number) → void
```

| 参数 | 类型 | 说明 |
|------|------|------|
| canvasSize | number | Canvas 画布尺寸 (正方形) |

**行为**: 初始化 121 个有效位置集合，计算六角星坐标，建立像素映射参数。

**来源需求**: F015, F001

### 3.2 getValidPositions

```
Board.getValidPositions() → HexCoord[]
```

**返回**: 全部 121 个有效棋盘位置。

**来源需求**: F015 AC1

### 3.3 getNeighbors

```
Board.getNeighbors(hex: HexCoord) → HexCoord[]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| hex | HexCoord | 查询位置 |

**返回**: 该位置的所有有效相邻位置（最多 6 个，过滤越界）。

**来源需求**: F015 AC2

### 3.4 hexToPixel

```
Board.hexToPixel(hex: HexCoord) → PixelCoord
```

**返回**: 立方坐标 → Canvas 像素坐标。

**来源需求**: F015, F001

### 3.5 pixelToHex

```
Board.pixelToHex(x: number, y: number) → HexCoord | null
```

**返回**: 像素坐标 → 最近的有效立方坐标，若超出棋盘范围返回 `null`。

**来源需求**: F015 AC3

### 3.6 isValidPosition

```
Board.isValidPosition(hex: HexCoord) → boolean
```

**返回**: 该坐标是否为 121 个有效位置之一。

### 3.7 getStartPositions

```
Board.getStartPositions(player: 1 | 2) → HexCoord[]
```

**返回**: 指定玩家的 10 个起始位置。

**来源需求**: F002

### 3.8 getTargetPositions

```
Board.getTargetPositions(player: 1 | 2) → HexCoord[]
```

**返回**: 指定玩家的 10 个目标位置（对角区域）。

**来源需求**: F002, F009

### 3.9 isInTargetZone

```
Board.isInTargetZone(hex: HexCoord, player: 1 | 2) → boolean
```

**返回**: 该位置是否在指定玩家的目标区域内。

**来源需求**: F006 AC3, F009

### 3.10 distance

```
Board.distance(a: HexCoord, b: HexCoord) → number
```

**返回**: 两个位置间的六角距离 `max(|Δq|, |Δr|, |Δs|)`。

**来源需求**: F008 (AI 距离评估)

### 3.11 recalculate

```
Board.recalculate(newCanvasSize: number) → void
```

**行为**: 窗口 resize 时重新计算像素映射参数。

**来源需求**: F001 AC3

---

## 4. GameState 模块 API

**职责**: 游戏状态管理（来源: F002, F007, F009, F013）

### 4.1 init

```
GameState.init(mode: GameMode) → void
```

**行为**: 初始化棋子位置、回合设置、步数清零。

**来源需求**: F002, F010

### 4.2 getPieces

```
GameState.getPieces() → Piece[]
```

**返回**: 当前所有 20 枚棋子状态。

### 4.3 getPieceAt

```
GameState.getPieceAt(hex: HexCoord) → Piece | null
```

**返回**: 指定位置的棋子，无则返回 `null`。

**来源需求**: F003

### 4.4 movePiece

```
GameState.movePiece(pieceId: string, to: HexCoord) → void
```

**行为**: 更新棋子位置。调用前应已通过 Rules 验证合法性。

**来源需求**: F004, F005

### 4.5 getCurrentPlayer

```
GameState.getCurrentPlayer() → 1 | 2
```

**返回**: 当前回合玩家编号。

**来源需求**: F007

### 4.6 switchTurn

```
GameState.switchTurn() → void
```

**行为**: 切换当前回合到对方，对应玩家步数 +1。

**来源需求**: F007, F013

### 4.7 getMode

```
GameState.getMode() → GameMode
```

**返回**: 当前游戏模式。

### 4.8 getMoveCount

```
GameState.getMoveCount(player: 1 | 2) → number
```

**返回**: 指定玩家已走步数。

**来源需求**: F013

### 4.9 saveSnapshot / restoreSnapshot

```
GameState.saveSnapshot() → UndoSnapshot
GameState.restoreSnapshot(snapshot: UndoSnapshot) → void
```

**行为**: 保存/恢复棋局快照，用于悔棋。

**来源需求**: F012

### 4.10 getPhase / setPhase

```
GameState.getPhase() → GamePhase
GameState.setPhase(phase: GamePhase) → void
```

**来源需求**: F007, F009, F010

---

## 5. Rules 模块 API

**职责**: 移动规则验证、合法移动计算（来源: F004, F005, F006）

### 5.1 getLegalMoves

```
Rules.getLegalMoves(pieceHex: HexCoord, state: GameStateSnapshot) → {
  steps: HexCoord[];    // 单步可达位置
  jumps: HexCoord[];    // 跳跃可达位置 (一次跳跃)
}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| pieceHex | HexCoord | 选中棋子位置 |
| state | GameStateSnapshot | 当前棋盘局面 (棋子位置集合) |

**返回**: 所有合法目标位置，区分单步和跳跃。

**规则约束**:
- 单步: 相邻空位 (F004)
- 跳跃: 相邻有棋子且对侧为空 (F005)
- 目标区域约束: 已在目标区域的棋子不可移出 (F006 AC3)
- 边界约束: 不越界 (F006 AC2)

**性能要求**: 计算时间 ≤ 100ms (NFR001)

**来源需求**: F003, F004, F005, F006

### 5.2 getAllJumpPaths

```
Rules.getAllJumpPaths(
  startHex: HexCoord, 
  state: GameStateSnapshot
) → HexCoord[][]
```

**返回**: 从起始位置出发的所有跳跃路径（含连跳），每条路径为一组有序坐标。使用 BFS/DFS 搜索，排除回跳到已访问位置（F005 AC5）。

**来源需求**: F005

### 5.3 getContinueJumps

```
Rules.getContinueJumps(
  currentHex: HexCoord, 
  visited: Set<string>, 
  state: GameStateSnapshot
) → HexCoord[]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| currentHex | HexCoord | 当前跳跃落点 |
| visited | Set\<string\> | 本次连跳中已访问位置集合 |
| state | GameStateSnapshot | 当前棋盘局面 |

**返回**: 可继续跳跃的目标位置列表。

**来源需求**: F005 AC2, AC5

### 5.4 isLegalMove

```
Rules.isLegalMove(
  from: HexCoord, 
  to: HexCoord, 
  state: GameStateSnapshot
) → boolean
```

**返回**: 指定移动是否合法。

**来源需求**: F006

### 5.5 checkWin

```
Rules.checkWin(player: 1 | 2, state: GameStateSnapshot) → boolean
```

**返回**: 指定玩家的 10 枚棋子是否全部位于目标区域。

**来源需求**: F009

---

## 6. AI 模块 API

**职责**: AI 对手决策（来源: F008）

### 6.1 computeMove

```
AI.computeMove(
  state: GameStateSnapshot, 
  callback: (move: Move) => void
) → void
```

| 参数 | 类型 | 说明 |
|------|------|------|
| state | GameStateSnapshot | 当前棋盘局面 |
| callback | Function | 决策完成后的回调，传入选择的移动 |

**行为**: 
- 异步执行（`setTimeout`），避免阻塞 UI
- 遍历所有己方棋子的合法移动
- 用启发式评估函数打分，选择最优移动
- 决策时间 ≤ 2s (NFR001)
- 含 500ms 最小思考延迟（UX 考虑）

**来源需求**: F008, NFR001

### 6.2 evaluate (内部方法)

```
AI._evaluate(
  move: Move, 
  player: 1 | 2, 
  state: GameStateSnapshot
) → number
```

**评估维度**:
- 距离改善 (向目标区域前进程度) — F008 AC2
- 跳跃奖励 (连跳比单步更高分) — F008 AC3
- 优先级调整 (已到目标的棋子降权) — F008 AC4

---

## 7. Renderer 模块 API

**职责**: Canvas 绘制与动画（来源: F001, F002, F003, F011）

### 7.1 init

```
Renderer.init(canvas: HTMLCanvasElement) → void
```

**行为**: 获取 2D context，初始化绘制参数。

### 7.2 drawBoard

```
Renderer.drawBoard() → void
```

**行为**: 绘制棋盘背景、121 个位置点、六角区域底色。

**来源需求**: F001

### 7.3 drawPieces

```
Renderer.drawPieces(pieces: Piece[]) → void
```

**行为**: 绘制所有棋子，双方颜色不同。

**来源需求**: F002

### 7.4 drawHighlights

```
Renderer.drawHighlights(
  selected: HexCoord | null, 
  legalMoves: HexCoord[]
) → void
```

**行为**: 绘制选中棋子高亮和合法目标位置标记。

**来源需求**: F003

### 7.5 animateMove

```
Renderer.animateMove(
  piece: Piece, 
  path: HexCoord[], 
  duration: number, 
  callback: () => void
) → void
```

| 参数 | 类型 | 说明 |
|------|------|------|
| piece | Piece | 移动的棋子 |
| path | HexCoord[] | 移动路径 |
| duration | number | 每段动画时长 (ms) |
| callback | Function | 动画完成回调 |

**行为**: 使用 `requestAnimationFrame` 逐帧绘制棋子移动动画。

**来源需求**: F011

### 7.6 redraw

```
Renderer.redraw() → void
```

**行为**: 完整重绘（清空 Canvas → 绘棋盘 → 绘棋子 → 绘高亮）。

**来源需求**: F001 AC3

---

## 8. InputHandler 模块 API

**职责**: 用户输入处理（来源: F003, NFR002, NFR003）

### 8.1 init

```
InputHandler.init(
  canvas: HTMLCanvasElement, 
  onClick: (hex: HexCoord) => void
) → void
```

**行为**: 绑定 `click` 和 `touchstart` 事件，转换为 HexCoord 回调。

**来源需求**: F003, NFR002

### 8.2 enable / disable

```
InputHandler.enable() → void
InputHandler.disable() → void
```

**行为**: 控制输入接收。动画期间和 AI 回合期间禁用。

**来源需求**: F007 AC3, F011 AC3

---

## 9. GameController 模块 API

**职责**: 游戏流程编排（来源: F007, F010, F012）

### 9.1 init

```
GameController.init() → void
```

**行为**: 初始化所有子模块，显示模式选择界面。

### 9.2 startGame

```
GameController.startGame(mode: GameMode) → void
```

**行为**: 初始化棋盘和棋子，开始第一回合。

**来源需求**: F010

### 9.3 handleBoardClick

```
GameController.handleBoardClick(hex: HexCoord) → void
```

**行为**: 根据当前子状态处理点击（选子 / 移动 / 取消）。

**来源需求**: F003, F004, F005

### 9.4 endTurn

```
GameController.endTurn() → void
```

**行为**: 结束当前回合，检查胜负，切换回合。

**来源需求**: F007, F009

### 9.5 undo

```
GameController.undo() → void
```

**行为**: 执行悔棋操作。

**来源需求**: F012

### 9.6 restartGame

```
GameController.restartGame() → void
```

**行为**: 返回模式选择界面。

**来源需求**: F009 AC3

---

## 10. UIOverlay 模块 API

**职责**: HUD 和弹窗管理（来源: F010, F012, F013, F014）

### 10.1 showModeSelect

```
UIOverlay.showModeSelect(onSelect: (mode: GameMode) => void) → void
```

**来源需求**: F010

### 10.2 showTurnIndicator

```
UIOverlay.showTurnIndicator(player: 1 | 2, mode: GameMode) → void
```

**来源需求**: F007 AC2

### 10.3 updateMoveCount

```
UIOverlay.updateMoveCount(p1Count: number, p2Count: number) → void
```

**来源需求**: F013

### 10.4 showEndTurnButton / hideEndTurnButton

```
UIOverlay.showEndTurnButton(onClick: () => void) → void
UIOverlay.hideEndTurnButton() → void
```

**来源需求**: F005 AC2

### 10.5 showUndoButton / hideUndoButton

```
UIOverlay.showUndoButton(onClick: () => void) → void
UIOverlay.hideUndoButton() → void
```

**来源需求**: F012

### 10.6 showGameResult

```
UIOverlay.showGameResult(
  winner: 1 | 2, 
  totalMoves: { 1: number; 2: number },
  onRestart: () => void
) → void
```

**来源需求**: F009

### 10.7 showTutorial

```
UIOverlay.showTutorial(onClose: () => void) → void
```

**来源需求**: F014

---

## 11. Audio 模块 API

**职责**: 音效播放（来源: F016）

### 11.1 play

```
Audio.play(sound: 'select' | 'place' | 'victory') → void
```

**行为**: 
- 使用 Web Audio API 生成简短合成音效
- 播放失败时静默处理，不抛出异常

**音效参数**:

| 音效名 | 频率 | 时长 | 波形 | 来源 |
|--------|------|------|------|------|
| select | 440Hz | 80ms | sine | F016 AC1 |
| place | 330Hz | 120ms | triangle | F016 AC2 |
| victory | 523-659-784Hz 琶音 | 800ms | sine | F016 AC3 |

**来源需求**: F016

---

## 12. 模块间调用矩阵

```
             Board  State  Rules  AI   Renderer  Input  Controller  UI   Audio
Board          -      -      -    -      -        -       -         -     -
GameState      R      -      -    -      -        -       -         -     -
Rules          R      R      -    -      -        -       -         -     -
AI             R      R      R    -      -        -       -         -     -
Renderer       R      R      -    -      -        -       -         -     -
InputHandler   R      -      -    -      -        -       -         -     -
GameController R      RW     R    R      R        RW      -         R     R
UIOverlay      -      R      -    -      -        -       -         -     -
Audio          -      -      -    -      -        -       -         -     -

R = Read (调用只读方法)
RW = Read + Write (调用含状态修改的方法)
```

---

## 13. 接口版本与兼容性

由于是单文件应用，所有模块在同一文件中，不存在版本兼容问题。接口变更通过代码修改直接同步。

---

*文档版本: v1.0 | 日期: 2026-04-09 | 作者: system-architect*
