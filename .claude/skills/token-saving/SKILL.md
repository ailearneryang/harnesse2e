---
name: token-saving
description: "节省 token 消耗的最佳实践。USE FOR: 优化 prompt 长度、减少重复输出、控制上下文大小、提高成本效益。"
globs:
  - "**/*.py"
  - "**/*.md"
  - "**/*.yaml"
---

# Token 节省最佳实践

本 Skill 帮助在保证输出质量的前提下最小化 token 消耗。

---

## 1. 输出格式精简

### 1.1 使用结构化简洁输出
- **避免**：冗长的解释性文本、重复说明、客套话
- **使用**：直接给出关键信息，用 bullet points 而非段落

### 1.2 代码注释精简
```python
# ✅ 好：关键逻辑一行注释
def process(data):
    # 跳过空值避免下游 NPE
    return [x for x in data if x]

# ❌ 差：冗长解释
def process(data):
    # This function takes a list of data items and processes them
    # by filtering out any items that are None or empty. This is
    # important because downstream functions expect non-null values
    # and will throw NullPointerException if they receive null.
    return [x for x in data if x]
```

### 1.3 文档格式
- 优先使用表格而非长段落
- 使用缩写：如 `req` → requirements, `impl` → implementation
- 避免重复已知上下文

---

## 2. Prompt 工程

### 2.1 精准指令
```
# ✅ 好
实现 bubble_sort(arr)，返回升序数组。

# ❌ 差
请帮我实现一个冒泡排序算法。这个算法应该接收一个数组作为输入，
然后通过比较相邻元素并交换位置的方式，最终返回一个从小到大排序好的数组。
```

### 2.2 避免过度上下文
- 只包含当前任务必需的背景信息
- 使用 `## Context (if needed)` 明确标记可选上下文
- 历史决策用 1-2 行摘要，不复制全文

### 2.3 输出约束
```
# 明确限制输出范围
输出要求：
- 仅返回修改的函数，不输出未变更代码
- 每个文件 diff 不超过 50 行
- 跳过样板代码说明
```

---

## 3. 代码生成策略

### 3.1 增量修改
- 修改时只输出 diff，不输出完整文件
- 使用 `// ... existing code ...` 标记省略部分

### 3.2 避免重复
- 通用逻辑抽取为可调用函数
- 测试用例使用 parametrize 而非重复代码

### 3.3 工具调用优化
```python
# ✅ 批量操作
files = ["a.py", "b.py", "c.py"]
for f in files:
    edit(f, changes)

# ❌ 单独操作（每次调用都消耗 token）
edit("a.py", change1)
edit("b.py", change2)
edit("c.py", change3)
```

---

## 4. 上下文管理

### 4.1 蒸馏优先
- 大文档传递时，先用 distiller 生成摘要
- 摘要目标：原文 30% 以内

### 4.2 分段处理
- 超过 200 行的文件分段处理
- 每段独立完成，减少重复加载

### 4.3 缓存利用
- 重复查询的内容记录到 context.md
- 避免多次 Read 同一文件

---

## 5. VERDICT 快速判定

### 5.1 早期退出
```
# 发现明显问题立即报告，不继续深入
if critical_issue:
    return "VERDICT: FAIL - 缺少必要的错误处理"
```

### 5.2 检查点模式
- 每完成一个子任务输出状态
- 可中断恢复，避免重做

---

## 6. 当前任务 Token 预算

参考 `budget.yaml` 配置：
- 单任务限制：500K tokens
- 单 stage 软限制：50K tokens
- 告警阈值：80%
- 硬限制：95%

**当前用量**：检查 `/api/runtime` 返回的 `budget` 字段

---

## 检查清单

在完成任务前确认：
- [ ] 输出是否可以更简洁？
- [ ] 是否重复了已知信息？
- [ ] 代码注释是否必要？
- [ ] 是否可以用 diff 代替完整文件？
- [ ] 上下文是否可以蒸馏？
