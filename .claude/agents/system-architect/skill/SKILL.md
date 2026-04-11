---
name: skill
description: "system-architect 的默认 skill。USE FOR: 架构设计、接口设计、数据建模、需求到设计的映射追踪。"
---

# System Architect Default Skill

此 Skill 作为 system-architect 的默认补充工作流。

- 目标是把需求转换为可实施、可追踪、可评审的技术设计
- 设计产物之间必须互相一致，避免架构、API、数据模型脱节
- 关键设计决策需要说明理由和风险

## 推荐输入

- 需求规格说明书
- 现有系统边界、技术约束和非功能需求
- 目标部署环境和集成方式

## 默认流程

1. 从需求中提取关键能力、边界和约束
2. 设计系统分层、组件职责和交互关系
3. 产出 API 定义和数据模型，并与需求编号建立追踪关系
4. 补充技术选型理由、已知风险和待确认事项

## 输出检查

- 产出 `architecture.md`、`api_design.md`、`data_model.md` 所需内容
- 设计决策尽量关联需求编号
- API 包含完整 request/response
- 数据模型包含字段类型和关系说明

## 可定制项

- C4 图层级深度
- API 设计规范
- 数据建模粒度
- 技术选型评估模板