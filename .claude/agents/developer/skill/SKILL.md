---
name: skill
description: "developer 的默认 skill。USE FOR: 按设计实现代码、补齐测试、控制技术债、保证可运行性。"
---

# Developer Default Skill

此 Skill 作为 developer 的默认补充工作流。

- 以设计文档为实现基准，不擅自偏离接口和数据结构
- 先完成正确性，再补齐必要异常处理和测试交接信息
- 变更应聚焦任务本身，避免顺手重构无关部分

## 推荐输入

- `cockpit-middleware-architect/architecture.md`
- `cockpit-middleware-architect/api_design.md`
- `cockpit-middleware-architect/data_model.md`
- 当前任务说明、目标文件和现有测试情况

## 默认流程

1. 先核对需求与设计约束，再确定修改范围
2. 实现最小闭环代码路径，补齐错误处理和边界情况
3. 标注测试入口、依赖和边界，便于 testing stage 补齐与执行单元测试
4. 在交付前确认代码可运行、风格一致、无明显技术债扩散

## 输出检查

- 实现与设计文档保持一致
- 为 testing stage 提供清晰测试交接信息
- 说明关键改动和验证方式
- 不引入无关重构

## 可定制项

- 测试覆盖率目标
- 注释策略
- 异常处理规范
- 不同技术栈下的实现检查清单