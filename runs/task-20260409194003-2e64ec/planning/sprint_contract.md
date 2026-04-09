# Sprint Contract - 跳跳棋

Now let me read the intake summary to understand the full context:
Now I have comprehensive context. Let me write the sprint contract as a structured planning document:
Sprint Contract 已生成完毕。以下是规划摘要：

---

# 📋 Sprint Contract — 跳跳棋 (Chinese Checkers)

## 目标摘要
构建单文件自包含 HTML5 跳跳棋网页游戏 (`src/chinese_checkers.html`)，人 vs AI 对战，中文界面，零依赖，对齐 `snake.html` 先例。

## 子任务 (8 个)

| # | 子任务 | Agent | Token 预算 | 关键 DoD |
|---|--------|-------|-----------|----------|
| **ST-1** | 需求规格编写 | requirements-analyst | ≤80K | F001~Fxxx 全编号，AC 用 Given/When/Then，评审 ≥80 分 |
| **ST-2** | 系统设计 | system-architect | ≤120K | 坐标系方案确定、移动算法、AI 伪代码、状态机定义 |
| **ST-3** | 代码实现 | developer | ≤200K | 单文件 HTML，121 位棋盘，连续跳跃，AI 贪心策略 |
| **ST-4** | 代码评审 | code-reviewer | — | 设计-代码一致性，错误处理，评审 ≥80 分 |
| **ST-5** | 安全评审 | security-reviewer | — | 无 XSS/eval，无外部请求 |
| **ST-6** | 安全合规 | safety-reviewer | — | 标注 ISO 26262/AUTOSAR 不适用 |
| **ST-7** | QA 测试 | qa-engineer | ≤100K | 全功能覆盖，测试全通过 |
| **ST-8** | 交付 | delivery-manager | — | Git commit + Gerrit push |

## 关键路径
```
ST-1 → ST-2 → ST-3 → ST-4/ST-5/ST-6 → ST-7 → ST-8
```

## 🔴 需人工确认的节点
- **R1**: 原始 spec 仅"跳跳棋"三字，已推断为标准六角星 2 人对战模式。若用户有不同预期（如西洋跳棋、多人模式等），需在需求阶段前确认。

## 产出物
完整 sprint contract 已写入：
`/runs/task-20260409194003-2e64ec/planning/sprint_contract.md`

**预算**：预估 ~225K / 500K tokens (45%)，时间 ~120 min，均有充足余量。
Sprint Contract 已生成完毕。以下是规划摘要：

---

# 📋 Sprint Contract — 跳跳棋 (Chinese Checkers)

## 目标摘要
构建单文件自包含 HTML5 跳跳棋网页游戏 (`src/chinese_checkers.html`)，人 vs AI 对战，中文界面，零依赖，对齐 `snake.html` 先例。

## 子任务 (8 个)

| # | 子任务 | Agent | Token 预算 | 关键 DoD |
|---|--------|-------|-----------|----------|
| **ST-1** | 需求规格编写 | requirements-analyst | ≤80K | F001~Fxxx 全编号，AC 用 Given/When/Then，评审 ≥80 分 |
| **ST-2** | 系统设计 | system-architect | ≤120K | 坐标系方案确定、移动算法、AI 伪代码、状态机定义 |
| **ST-3** | 代码实现 | developer | ≤200K | 单文件 HTML，121 位棋盘，连续跳跃，AI 贪心策略 |
| **ST-4** | 代码评审 | code-reviewer | — | 设计-代码一致性，错误处理，评审 ≥80 分 |
| **ST-5** | 安全评审 | security-reviewer | — | 无 XSS/eval，无外部请求 |
| **ST-6** | 安全合规 | safety-reviewer | — | 标注 ISO 26262/AUTOSAR 不适用 |
| **ST-7** | QA 测试 | qa-engineer | ≤100K | 全功能覆盖，测试全通过 |
| **ST-8** | 交付 | delivery-manager | — | Git commit + Gerrit push |

## 关键路径
```
ST-1 → ST-2 → ST-3 → ST-4/ST-5/ST-6 → ST-7 → ST-8
```

## 🔴 需人工确认的节点
- **R1**: 原始 spec 仅"跳跳棋"三字，已推断为标准六角星 2 人对战模式。若用户有不同预期（如西洋跳棋、多人模式等），需在需求阶段前确认。

## 产出物
完整 sprint contract 已写入：
`/runs/task-20260409194003-2e64ec/planning/sprint_contract.md`

**预算**：预估 ~225K / 500K tokens (45%)，时间 ~120 min，均有充足余量。
