# Sprint Contract - 冒泡算法

system
assistant
assistant
system
user
system
assistant
assistant
assistant
user
user
user
system
assistant
system
assistant
system
assistant
system
assistant
system
assistant
system
assistant
system
assistant
system
assistant
user
user
user
user
user
user
user
user
system
assistant
system
assistant
system
assistant
system
assistant
user
user
user
user
system
assistant
system
assistant
system
assistant
system
assistant
user
user
user
user
system
user
现在我了解了项目上下文。这是一个研发流水线 harness 项目，`src/` 目录为空，需要实现冒泡排序算法。让我输出结构化的 Sprint Contract。

---

# Sprint Contract — 冒泡算法 (Bubble Sort)

**Task ID:** task-20260408165533-e0b716  
**目标摘要:** 在 `src/` 目录下实现 Python 冒泡排序算法，包含完整的功能代码、单元测试和安全审查，遵循项目既有的 Python 3.13 规范。

---

## 子任务列表

| # | 子任务 | 负责角色 | Definition of Done |
|---|--------|----------|-------------------|
| T1 | **需求规格编写** — 将"冒泡算法"转化为精确的需求规格说明书，明确输入/输出、边界条件、时间/空间复杂度要求 | requirements-analyst | `specs/` 下生成需求规格文档，涵盖：函数签名、支持数据类型、升序/降序、边界用例（空列表、单元素、已排序、逆序、重复元素） |
| T2 | **系统设计** — 基于需求规格进行模块设计，确定文件结构、接口定义、命名规范 | system-architect | `design/` 下更新架构文档；明确 `src/bubble_sort.py` 的模块结构和公开 API |
| T3 | **代码实现** — 根据设计文档编写冒泡排序核心代码 | developer | `src/bubble_sort.py` 存在且包含：① 标准冒泡排序函数 ② 优化版冒泡排序（提前终止） ③ 完整的类型注解和文档字符串 ④ 代码可直接 `import` 无报错 |
| T4 | **单元测试编写** — 设计并实现测试用例覆盖全部边界场景 | qa-engineer | `tests/cases/test_bubble_sort.py` 存在且包含 ≥8 个测试用例；`pytest` 全部通过；覆盖率 ≥ 95% |
| T5 | **代码审查** — 独立评审代码质量、规范性、可维护性 | code-reviewer | 审查报告产出，无 Critical/High 级别问题；或问题已修复后复审通过 |
| T6 | **安全审查** — 检查注入风险、边界溢出、资源消耗等安全问题 | security-reviewer | 安全审查报告产出，无安全漏洞；确认无不安全的 `eval`/`exec` 使用 |
| T7 | **缺陷修复（条件触发）** — 若 T5/T6 发现问题，进行最小范围修复 | debugger | 所有审查反馈的问题已关闭；修复后重新通过 T4 的全部测试 |

---

## 依赖关系

```
T1 (需求规格)
  └──▶ T2 (系统设计)
         └──▶ T3 (代码实现)
                └──▶ T4 (单元测试)
                       ├──▶ T5 (代码审查)
                       └──▶ T6 (安全审查)   ← T5、T6 可并行
                              └──▶ T7 (缺陷修复，条件触发)
```

**执行顺序:** T1 → T2 → T3 → T4 → T5 ∥ T6 → T7（如需）

---

## 质量门禁

| 阶段 | 门禁标准 | 检查方式 |
|------|----------|----------|
| 需求完成 (T1→T2) | 需求文档涵盖 ≥5 种边界场景，函数签名已确定 | 人工审批 |
| 设计完成 (T2→T3) | 设计文档明确模块接口、文件路径，与需求一致 | 自动检查 + 人工审批 |
| 编码完成 (T3→T4) | 代码无语法错误，`python -c "import src.bubble_sort"` 通过 | 自动检查 |
| 测试通过 (T4→T5/T6) | `pytest tests/cases/test_bubble_sort.py` 全绿，覆盖率 ≥ 95% | 自动检查 |
| 审查通过 (T5+T6→交付) | 无 Critical/High 问题；安全审查无漏洞 | 人工审批 |

---

## 风险点

| # | 风险 | 影响 | 缓解措施 |
|---|------|------|----------|
| R1 | `src/` 目录为空，无既有代码规范可参考 | 编码风格不一致 | T2 中显式定义编码规范（PEP 8、类型注解、docstring 格式） |
| R2 | `tests/cases/` 无既有测试，缺少 pytest 配置 | 测试无法运行 | T4 中需同时确认 pytest 可发现并运行测试（可能需添加 `__init__.py` 或 `conftest.py`） |
| R3 | 需求过于简单导致过度设计 | 浪费时间 | 保持实现精简，仅包含标准版 + 优化版两个函数 |

---

**⚠️ 需人工确认的节点：**
1. **T1 完成后** — 确认需求规格范围是否合理（是否需要支持自定义比较函数、泛型类型等）
2. **T2 完成后** — 确认设计方案（文件结构、API 命名）
3. **T5+T6 完成后** — 确认审查结果，决定是否进入交付
现在我了解了项目上下文。这是一个研发流水线 harness 项目，`src/` 目录为空，需要实现冒泡排序算法。让我输出结构化的 Sprint Contract。

---

# Sprint Contract — 冒泡算法 (Bubble Sort)

**Task ID:** task-20260408165533-e0b716  
**目标摘要:** 在 `src/` 目录下实现 Python 冒泡排序算法，包含完整的功能代码、单元测试和安全审查，遵循项目既有的 Python 3.13 规范。

---

## 子任务列表

| # | 子任务 | 负责角色 | Definition of Done |
|---|--------|----------|-------------------|
| T1 | **需求规格编写** — 将"冒泡算法"转化为精确的需求规格说明书，明确输入/输出、边界条件、时间/空间复杂度要求 | requirements-analyst | `specs/` 下生成需求规格文档，涵盖：函数签名、支持数据类型、升序/降序、边界用例（空列表、单元素、已排序、逆序、重复元素） |
| T2 | **系统设计** — 基于需求规格进行模块设计，确定文件结构、接口定义、命名规范 | system-architect | `design/` 下更新架构文档；明确 `src/bubble_sort.py` 的模块结构和公开 API |
| T3 | **代码实现** — 根据设计文档编写冒泡排序核心代码 | developer | `src/bubble_sort.py` 存在且包含：① 标准冒泡排序函数 ② 优化版冒泡排序（提前终止） ③ 完整的类型注解和文档字符串 ④ 代码可直接 `import` 无报错 |
| T4 | **单元测试编写** — 设计并实现测试用例覆盖全部边界场景 | qa-engineer | `tests/cases/test_bubble_sort.py` 存在且包含 ≥8 个测试用例；`pytest` 全部通过；覆盖率 ≥ 95% |
| T5 | **代码审查** — 独立评审代码质量、规范性、可维护性 | code-reviewer | 审查报告产出，无 Critical/High 级别问题；或问题已修复后复审通过 |
| T6 | **安全审查** — 检查注入风险、边界溢出、资源消耗等安全问题 | security-reviewer | 安全审查报告产出，无安全漏洞；确认无不安全的 `eval`/`exec` 使用 |
| T7 | **缺陷修复（条件触发）** — 若 T5/T6 发现问题，进行最小范围修复 | debugger | 所有审查反馈的问题已关闭；修复后重新通过 T4 的全部测试 |

---

## 依赖关系

```
T1 (需求规格)
  └──▶ T2 (系统设计)
         └──▶ T3 (代码实现)
                └──▶ T4 (单元测试)
                       ├──▶ T5 (代码审查)
                       └──▶ T6 (安全审查)   ← T5、T6 可并行
                              └──▶ T7 (缺陷修复，条件触发)
```

**执行顺序:** T1 → T2 → T3 → T4 → T5 ∥ T6 → T7（如需）

---

## 质量门禁

| 阶段 | 门禁标准 | 检查方式 |
|------|----------|----------|
| 需求完成 (T1→T2) | 需求文档涵盖 ≥5 种边界场景，函数签名已确定 | 人工审批 |
| 设计完成 (T2→T3) | 设计文档明确模块接口、文件路径，与需求一致 | 自动检查 + 人工审批 |
| 编码完成 (T3→T4) | 代码无语法错误，`python -c "import src.bubble_sort"` 通过 | 自动检查 |
| 测试通过 (T4→T5/T6) | `pytest tests/cases/test_bubble_sort.py` 全绿，覆盖率 ≥ 95% | 自动检查 |
| 审查通过 (T5+T6→交付) | 无 Critical/High 问题；安全审查无漏洞 | 人工审批 |

---

## 风险点

| # | 风险 | 影响 | 缓解措施 |
|---|------|------|----------|
| R1 | `src/` 目录为空，无既有代码规范可参考 | 编码风格不一致 | T2 中显式定义编码规范（PEP 8、类型注解、docstring 格式） |
| R2 | `tests/cases/` 无既有测试，缺少 pytest 配置 | 测试无法运行 | T4 中需同时确认 pytest 可发现并运行测试（可能需添加 `__init__.py` 或 `conftest.py`） |
| R3 | 需求过于简单导致过度设计 | 浪费时间 | 保持实现精简，仅包含标准版 + 优化版两个函数 |

---

**⚠️ 需人工确认的节点：**
1. **T1 完成后** — 确认需求规格范围是否合理（是否需要支持自定义比较函数、泛型类型等）
2. **T2 完成后** — 确认设计方案（文件结构、API 命名）
3. **T5+T6 完成后** — 确认审查结果，决定是否进入交付
