---
name: skill
description: "build-verifier 的默认 skill。USE FOR: 构建验证、CI/CD 结果汇总、质量门禁收口、发布前放行判定。"
---

# Build Verifier Default Skill

此 Skill 作为 build-verifier 的默认补充工作流。

- 保持 agent 主文件中的角色边界、门禁规则和 verdict 结尾不变
- 若任务要求与本 Skill 冲突，以任务要求为准
- 若本 Skill 与 agent 主文件冲突，以 agent 主文件为准

## 推荐输入

- 构建任务 ID 或流水线链接
- 编译结果、测试结果、覆盖率结果
- lint、type check、SAST、SBOM、签名链结果
- 发布阈值或门禁例外说明

## 默认流程

1. 收集所有上游验证结果，标记缺失项
2. 先判断阻断项，再判断告警项，避免结论模糊
3. 对照发布门禁逐项汇总通过/失败/待人工确认状态
4. 输出统一摘要，明确给出最终 verdict

## 输出检查

- 包含关键指标汇总
- 明确指出失败项和缺失项
- 结尾必须是 `VERDICT: PASS`、`VERDICT: FAIL` 或 `VERDICT: NEED_HUMAN`

## 可定制项

- 测试覆盖率阈值
- SAST 严重等级阈值
- SBOM 与签名链检查字段
- 不同 CI 平台的结果映射方式