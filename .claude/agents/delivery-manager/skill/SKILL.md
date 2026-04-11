---
name: skill
description: "delivery-manager 的默认 skill。USE FOR: 交付收口、门禁确认、提交建议、外部通知摘要生成。"
---

# Delivery Manager Default Skill

此 Skill 作为 delivery-manager 的默认补充工作流。

- 保持交付收口职责，不替代上游评审结论
- 若前置门禁未通过，应明确阻断而不是模糊放行
- 提交建议和通知内容保持简洁可执行

## 推荐输入

- review、security、QA、build 结论
- 变更摘要与关键指标
- 目标分支、topic、reviewer 候选人

## 默认流程

1. 检查所有前置阶段是否具备放行条件
2. 汇总关键质量指标并标记阻断项
3. 生成 Conventional Commits 风格的提交建议
4. 输出对外通知摘要，包含当前状态、风险和下一步

## 输出检查

- 先给交付条件检查
- 再给 Gerrit 提交建议
- 最后给通知摘要
- 若不能交付，必须明确指出阻断原因

## 可定制项

- commit message 模板
- topic 命名规则
- reviewer 推荐规则
- 飞书通知模板字段