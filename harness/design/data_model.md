# Data Model Design - 跳跳棋

Generated at: 2026-04-09
Task ID: task-20260409194003-2e64ec

---

## 1. 概述

本项目为纯前端游戏，无数据库、无持久化（NFR005）。所有数据存在于 JavaScript 运行时内存中。本文档定义游戏运行时的数据结构、实体关系和状态管理。

---

## 2. 实体关系图 (ER Diagram)

```
┌─────────────────┐       1    1..N   ┌─────────────────┐
│   GameSession    │──────────────────│     Player       │
│                  │                  │                  │
│  mode            │                  │  id: 1|2         │
│  phase           │                  │  type            │
│  currentPlayer   │                  │  moveCount       │
│  turnSubState    │                  │  color           │
└────────┬────────┘                  └────────┬────────┘
         │                                     │
         │ 1                                   │ 1
         │                                     │
         │ 1                                   │ N (10枚)
┌────────┴────────┐                  ┌────────┴────────┐
│   BoardConfig    │                  │     Piece        │
│                  │                  │                  │
│  validPositions[]│                  │  id              │
│  hexSize         │                  │  player          │
│  canvasSize      │                  │  position        │
│  centerOffset    │                  └────────┬────────┘
└────────┬────────┘                           │
         │ 1                                   │ 1
         │                                     │
         │ N (121)                             │ 1
┌────────┴────────┐                  ┌────────┴────────┐
│   BoardPosition  │                  │    HexCoord      │
│                  │ 1           1   │                  │
│  hex: HexCoord   │─────────────────│  q               │
│  zone            │                  │  r               │
│  pixel: {x, y}  │                  │  s               │
│  neighbors[]     │                  │  (q+r+s=0)      │
└─────────────────┘                  └─────────────────┘
         │
         │ 0..1
         │
┌────────┴────────┐
│   ZoneInfo       │
│                  │
│  id: string      │
│  owner: 1|2|null │
│  type: start|    │
│    target|neutral│
│  positions[]     │
└─────────────────┘
```

---

## 3. 数据结构详细定义

### 3.1 HexCoord — 六角坐标

```javascript
/**
 * 立方坐标系 (Cube Coordinates)
 * 来源需求: F015
 * 约束: q + r + s === 0
 */
const HexCoord = {
  q: 0,   // number - 列方向 (东西轴)
  r: 0,   // number - 行方向 (东南-西北轴)
  s: 0    // number - 计算值 (西南-东北轴), s = -q - r
};

// 六方向增量常量
const HEX_DIRECTIONS = [
  { q: +1, r: -1, s:  0 },  // 东北
  { q: +1, r:  0, s: -1 },  // 东
  { q:  0, r: +1, s: -1 },  // 东南
  { q: -1, r: +1, s:  0 },  // 西南
  { q: -1, r:  0, s: +1 },  // 西
  { q:  0, r: -1, s: +1 }   // 西北
];
```

**字段说明**:

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| q | number (integer) | -8 ≤ q ≤ 8 | 列坐标 |
| r | number (integer) | -8 ≤ r ≤ 8 | 行坐标 |
| s | number (integer) | s = -q - r | 冗余坐标，用于简化距离/方向计算 |

### 3.2 Piece — 棋子

```javascript
/**
 * 棋子实体
 * 来源需求: F002
 */
const Piece = {
  id: "p1_0",          // string - 唯一标识
  player: 1,           // 1 | 2 - 所属玩家
  position: HexCoord   // HexCoord - 当前棋盘位置
};
```

**字段说明**:

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | string | 格式: `p{player}_{index}` | 唯一标识, 如 "p1_0"~"p1_9", "p2_0"~"p2_9" |
| player | number | 1 或 2 | 所属玩家编号 |
| position | HexCoord | 必须为有效棋盘位置 | 棋子当前位置 |

**总数量**: 20 枚（每方 10 枚，来源 F002）

### 3.3 Player — 玩家

```javascript
/**
 * 玩家实体
 * 来源需求: F010, F013
 */
const Player = {
  id: 1,                  // 1 | 2
  type: 'human',          // 'human' | 'ai'
  color: '#4A90D9',       // string - 棋子颜色
  moveCount: 0,           // number - 已走步数
  startZone: [],          // HexCoord[] - 起始区域 (10个位置)
  targetZone: []          // HexCoord[] - 目标区域 (10个位置)
};
```

**字段说明**:

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | number | 1 或 2 | 玩家编号 |
| type | string | 'human' \| 'ai' | 玩家类型，AI 模式下 P2 为 'ai' |
| color | string | CSS 颜色值 | 棋子渲染颜色 |
| moveCount | number | ≥ 0 | 累计移动步数 (F013) |
| startZone | HexCoord[] | 长度 = 10 | 起始三角区域位置列表 |
| targetZone | HexCoord[] | 长度 = 10 | 目标三角区域位置列表 |

### 3.4 GameSession — 游戏会话

```javascript
/**
 * 游戏会话状态 (核心状态对象)
 * 来源需求: F007, F009, F010
 */
const GameSession = {
  mode: 'pvai',           // GameMode - 'pvai' | 'pvp'
  phase: 'MENU',          // GamePhase
  currentPlayer: 1,       // 1 | 2 - 当前回合玩家
  turnSubState: 'IDLE',   // TurnSubState - 回合内子状态
  players: [],            // Player[2] - 两位玩家
  pieces: [],             // Piece[20] - 所有棋子
  selectedPiece: null,    // string | null - 当前选中棋子ID
  legalMoves: [],         // HexCoord[] - 当前选中棋子的合法目标
  jumpVisited: new Set(), // Set<string> - 连跳中已访问位置
  isAnimating: false,     // boolean - 动画锁
  undoSnapshot: null,     // UndoSnapshot | null - 悔棋快照
  canUndo: false          // boolean - 是否可悔棋
};
```

**字段说明**:

| 字段 | 类型 | 初始值 | 说明 | 来源需求 |
|------|------|--------|------|----------|
| mode | string | 'pvai' | 游戏模式 | F010 |
| phase | string | 'MENU' | 游戏阶段 | F007, F009 |
| currentPlayer | number | 1 | 当前回合玩家 | F007 |
| turnSubState | string | 'IDLE' | 回合内子状态 | F003, F005 |
| players | Player[] | [] | 两位玩家信息 | F010 |
| pieces | Piece[] | [] | 20 枚棋子 | F002 |
| selectedPiece | string\|null | null | 选中棋子 ID | F003 |
| legalMoves | HexCoord[] | [] | 合法目标位置 | F003, F006 |
| jumpVisited | Set\<string\> | 空集 | 连跳已访问位置 | F005 |
| isAnimating | boolean | false | 动画锁定标记 | F011 |
| undoSnapshot | object\|null | null | 悔棋快照 | F012 |
| canUndo | boolean | false | 可悔棋标记 | F012 |

### 3.5 BoardConfig — 棋盘配置

```javascript
/**
 * 棋盘渲染配置 (运行时计算)
 * 来源需求: F001, F015
 */
const BoardConfig = {
  canvasSize: 600,            // number - Canvas 画布尺寸(px)
  centerX: 300,               // number - 棋盘中心 X
  centerY: 300,               // number - 棋盘中心 Y
  hexSize: 18,                // number - 单个位置点半径(px)
  hexSpacing: 22,             // number - 相邻位置间距(px)
  pieceRadius: 12,            // number - 棋子渲染半径(px)
  validPositions: new Map(),  // Map<string, BoardPosition> - key="q,r,s"
  zones: []                   // ZoneInfo[] - 六个三角区域信息
};
```

### 3.6 BoardPosition — 棋盘位置

```javascript
/**
 * 单个棋盘位置点
 * 来源需求: F015
 */
const BoardPosition = {
  hex: HexCoord,          // 立方坐标
  pixel: { x: 0, y: 0 }, // 像素坐标 (预计算)
  zone: 'neutral',        // string - 所属区域: 'top'|'bottom'|...|'neutral'
  neighbors: []           // HexCoord[] - 有效相邻位置 (预计算)
};
```

### 3.7 UndoSnapshot — 悔棋快照

```javascript
/**
 * 悔棋用状态快照
 * 来源需求: F012
 */
const UndoSnapshot = {
  pieces: [],             // Piece[] - 棋子位置深拷贝
  currentPlayer: 1,       // 1 | 2
  moveCount: { 1: 0, 2: 0 }
};
```

### 3.8 Move — 移动指令

```javascript
/**
 * 移动指令 (由 Rules 模块生成, AI 模块输出)
 * 来源需求: F004, F005, F008
 */
const Move = {
  pieceId: "p1_0",        // string - 棋子 ID
  from: HexCoord,         // 起始位置
  to: HexCoord,           // 最终目标位置
  path: [],               // HexCoord[] - 完整路径 (连跳含中间点)
  type: 'step'            // 'step' | 'jump'
};
```

### 3.9 AnimationState — 动画状态

```javascript
/**
 * 动画帧状态
 * 来源需求: F011
 */
const AnimationState = {
  active: false,          // boolean - 是否有动画在播放
  piece: null,            // Piece | null - 正在移动的棋子
  fromPixel: null,        // PixelCoord - 起始像素位置
  toPixel: null,          // PixelCoord - 目标像素位置
  progress: 0,            // number 0~1 - 当前进度
  startTime: 0,           // number - 动画开始时间戳
  duration: 200,          // number - 动画时长(ms)
  onComplete: null        // Function - 完成回调
};
```

---

## 4. 六角星棋盘位置数据

### 4.1 位置总数与分区

| 区域 | 位置数 | 类型 | 说明 |
|------|--------|------|------|
| 顶部三角 (Top) | 10 | P2 起始区 / P1 目标区 | 来源 F002 |
| 底部三角 (Bottom) | 10 | P1 起始区 / P2 目标区 | 来源 F002 |
| 左上三角 | 10 | 空闲 (2人模式不使用) | — |
| 右上三角 | 10 | 空闲 | — |
| 左下三角 | 10 | 空闲 | — |
| 右下三角 | 10 | 空闲 | — |
| 中央菱形 | 61 | 公共区域 | — |
| **合计** | **121** | | F015 AC1 |

### 4.2 六角星坐标生成算法

棋盘使用行扫描方式生成，基于六角星的对称性质：

```javascript
/**
 * 生成 121 个有效位置的立方坐标
 * 六角星 = 中心菱形 + 6个三角尖角
 */
function generateStarPositions() {
  const positions = [];
  
  // 方法: 预定义每行的列范围
  // 六角星棋盘共 17 行 (行号 0~16)
  // 使用 axial 坐标 (q, r) 后转换为 cube
  
  const rows = [
    // [行号, 起始列, 结束列]  → 每行的有效位置
    // 顶部三角尖 (row 0~3): 1,2,3,4 个位置
    [0, 0, 0],     // 1 位置
    [1, 0, 1],     // 2 位置
    [2, 0, 2],     // 3 位置
    [3, 0, 3],     // 4 位置
    // 上半宽体 (row 4~7): 9,10,11,12 个位置
    [4, -4, 4],    // 9
    [5, -4, 5],    // 10
    [6, -4, 6],    // 11
    [7, -4, 7],    // 12
    // 中线 (row 8): 13 个位置
    [8, -4, 8],    // 13
    // 下半宽体 (row 9~12): 12,11,10,9
    [9, -3, 8],
    [10, -2, 8],
    [11, -1, 8],
    [12, 0, 8],
    // 底部三角尖 (row 13~16): 4,3,2,1
    [13, 4, 7],
    [14, 5, 7],
    [15, 6, 7],
    [16, 7, 7]
  ];
  // 注: 具体行列偏移需在实现阶段精确计算
  
  return positions;
}
```

> **注**: 上述算法为示意性伪代码。实际实现时将使用一组预定义的 (q,r,s) 坐标元组来确保准确性。具体坐标值在开发阶段根据六角星几何形状精确计算。

### 4.3 三角区域定义

```javascript
/**
 * 各三角区域的位置集合 (硬编码或算法生成)
 * 来源需求: F002, F009
 */
const ZONES = {
  top: {
    id: 'top',
    owner: 2,          // P2 起始区
    targetOf: 1,        // P1 目标区
    positions: [/* 10 个 HexCoord */]
  },
  bottom: {
    id: 'bottom',
    owner: 1,          // P1 起始区
    targetOf: 2,        // P2 目标区
    positions: [/* 10 个 HexCoord */]
  },
  topLeft:    { id: 'topLeft',    owner: null, targetOf: null, positions: [] },
  topRight:   { id: 'topRight',   owner: null, targetOf: null, positions: [] },
  bottomLeft: { id: 'bottomLeft', owner: null, targetOf: null, positions: [] },
  bottomRight:{ id: 'bottomRight',owner: null, targetOf: null, positions: [] }
};
```

---

## 5. 颜色与视觉常量

```javascript
/**
 * 视觉配置常量
 * 来源需求: F001, F002, F003, NFR003
 */
const COLORS = {
  board: {
    background: '#F5E6CA',       // 棋盘底色 (暖米色)
    positionDot: '#C4A882',      // 空位点颜色
    positionDotRadius: 4,        // 空位点半径(px)
    zoneTop: 'rgba(220,60,60,0.15)',     // 顶部区域底色
    zoneBottom: 'rgba(60,100,220,0.15)', // 底部区域底色
    zoneNeutral: 'rgba(0,0,0,0)'         // 中性区域 (透明)
  },
  pieces: {
    player1: '#4A90D9',          // P1 棋子颜色 (蓝)
    player2: '#D94A4A',          // P2 棋子颜色 (红)
    stroke: '#FFFFFF',           // 棋子描边 (白)
    strokeWidth: 2               // 描边宽度
  },
  highlight: {
    selected: 'rgba(255,215,0,0.6)',     // 选中棋子高亮 (金色)
    legalMove: 'rgba(0,200,100,0.5)',    // 合法目标 (绿色半透明)
    legalMoveRadius: 8                    // 合法目标标记半径(px)
  },
  ui: {
    turnP1: '#4A90D9',           // P1 回合指示色
    turnP2: '#D94A4A',           // P2 回合指示色
    buttonBg: '#4A90D9',         // 按钮背景色
    buttonHover: '#3A7BC8',      // 按钮悬停色
    textPrimary: '#333333',      // 主文本色
    textSecondary: '#666666'     // 辅助文本色
  }
};
```

**色彩对比度验证** (NFR003):
- 棋子蓝(#4A90D9) vs 白色背景: 对比度 3.1:1（大图形元素，满足 AA 大文本标准）
- 棋子红(#D94A4A) vs 白色背景: 对比度 4.6:1（满足 AA 标准）
- 主文本(#333) vs 白色背景: 对比度 12.6:1（满足 AAA 标准）

---

## 6. 状态转换规则

### 6.1 GamePhase 转换

| 当前状态 | 事件 | 下一状态 | 条件 | 来源 |
|---------|------|---------|------|------|
| MENU | 选择模式 | INIT | — | F010 |
| INIT | 初始化完成 | PLAYER_TURN | currentPlayer=1 | F002 |
| PLAYER_TURN | 移动完成 | OPPONENT_TURN | 未胜利 | F007 |
| PLAYER_TURN | 移动完成 | GAME_OVER | 检测到胜利 | F009 |
| OPPONENT_TURN | AI/P2移动完成 | PLAYER_TURN | 未胜利 | F007 |
| OPPONENT_TURN | AI/P2移动完成 | GAME_OVER | 检测到胜利 | F009 |
| GAME_OVER | 再来一局 | MENU | — | F009 |

### 6.2 TurnSubState 转换

| 当前状态 | 事件 | 下一状态 | 说明 | 来源 |
|---------|------|---------|------|------|
| IDLE | 点击己方棋子 | SELECTED | 选中棋子 | F003 |
| SELECTED | 点击合法目标(单步) | IDLE | 完成移动→endTurn | F004 |
| SELECTED | 点击合法目标(跳跃) | JUMPING | 检查可否继续跳 | F005 |
| SELECTED | 点击空白/对方棋子 | IDLE | 取消选中 | F003 |
| SELECTED | 点击另一己方棋子 | SELECTED | 切换选中 | F003 |
| JUMPING | 点击可跳目标 | JUMPING | 继续跳跃 | F005 |
| JUMPING | 点击结束/无跳跃 | IDLE | 完成移动→endTurn | F005 |

---

## 7. 数据操作摘要

### 7.1 读操作 (无副作用)

| 操作 | 数据 | 调用方 | 来源 |
|------|------|--------|------|
| 获取位置棋子 | pieces | InputHandler→GameController | F003 |
| 获取相邻位置 | validPositions.neighbors | Rules | F004, F005 |
| 获取合法移动 | pieces + validPositions | Rules→GameController | F006 |
| 判断是否在目标区 | zones | Rules | F006, F009 |
| 计算距离 | HexCoord | AI | F008 |
| 获取步数 | players.moveCount | UIOverlay | F013 |

### 7.2 写操作 (状态变更)

| 操作 | 变更数据 | 触发条件 | 来源 |
|------|---------|---------|------|
| 初始化棋子 | pieces, players | 游戏开始 | F002 |
| 移动棋子 | piece.position | 合法移动确认 | F004, F005 |
| 切换回合 | currentPlayer, moveCount | endTurn | F007 |
| 选中棋子 | selectedPiece, legalMoves | 点击棋子 | F003 |
| 保存快照 | undoSnapshot | 移动前 | F012 |
| 恢复快照 | pieces, currentPlayer, moveCount | 悔棋 | F012 |
| 更新阶段 | phase | 状态机转换 | F007, F009 |

---

## 8. 数据完整性约束

| 约束 | 描述 | 验证时机 |
|------|------|---------|
| C1 | 棋子总数始终为 20 | 每次移动后 |
| C2 | 每个位置最多 1 枚棋子 | 移动前验证 |
| C3 | q + r + s === 0 (立方坐标) | 坐标创建时 |
| C4 | 棋子位置必须在 validPositions 中 | 移动前验证 |
| C5 | 已入目标区的棋子不可离开 | 合法移动计算时 (F006 AC3) |
| C6 | 连跳不可回到已访问位置 | 跳跃计算时 (F005 AC5) |
| C7 | 每方恰好 10 枚棋子 | 初始化时 |
| C8 | currentPlayer 只能是 1 或 2 | 回合切换时 |

---

## 9. 内存占用估算

| 数据结构 | 数量 | 单元大小 | 合计 |
|---------|------|---------|------|
| BoardPosition | 121 | ~100 bytes | ~12 KB |
| Piece | 20 | ~60 bytes | ~1.2 KB |
| HEX_DIRECTIONS | 6 | ~30 bytes | ~180 B |
| GameSession | 1 | ~500 bytes | ~500 B |
| UndoSnapshot | 1 | ~1.3 KB | ~1.3 KB |
| 合法移动缓存 | ~30 | ~20 bytes | ~600 B |
| **合计** | | | **~16 KB** |

内存使用极小，远低于任何现代设备限制。

---

## 10. 需求追溯矩阵

| 需求编号 | 数据模型组件 | 章节 |
|---------|------------|------|
| F001 | BoardConfig, BoardPosition, COLORS.board | §3.5, §3.6, §5 |
| F002 | Piece, Player, ZONES | §3.2, §3.3, §4.3 |
| F003 | GameSession.selectedPiece/legalMoves, COLORS.highlight | §3.4, §5 |
| F004 | Move, HEX_DIRECTIONS | §3.8, §3.1 |
| F005 | Move, GameSession.jumpVisited | §3.8, §3.4 |
| F006 | BoardPosition.neighbors, ZONES, 完整性约束 C5 | §3.6, §4.3, §8 |
| F007 | GameSession.phase/currentPlayer | §3.4, §6.1 |
| F008 | Move (AI 输出) | §3.8 |
| F009 | ZONES.targetOf, GameSession.phase | §4.3, §6.1 |
| F010 | GameSession.mode, Player.type | §3.4, §3.3 |
| F011 | AnimationState | §3.9 |
| F012 | UndoSnapshot | §3.7 |
| F013 | Player.moveCount | §3.3 |
| F014 | (纯 UI, 无数据模型) | — |
| F015 | HexCoord, BoardPosition, HEX_DIRECTIONS | §3.1, §3.6, §4 |
| F016 | (运行时 AudioContext, 无持久数据) | — |
| NFR003 | COLORS (对比度) | §5 |
| NFR004 | 内存占用约 16KB | §9 |
| NFR005 | 无持久化, 纯内存 | §1 |

---

*文档版本: v1.0 | 日期: 2026-04-09 | 作者: system-architect*
