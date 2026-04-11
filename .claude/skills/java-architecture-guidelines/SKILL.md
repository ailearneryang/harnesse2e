---
name: java-architecture-guidelines
description: 'Use for Java architecture in middleware and platform projects: module layering, domain model, service orchestration, concurrency model, exception boundary, interface contract and maintainable package design from requirements and architecture tasks.'
---

# Java Architecture Guidelines

## 适用场景

- 需求涉及 Java 服务编排、领域模型、模块分层、Android Java 服务或平台 Java 组件。
- 需要设计包结构、接口契约、线程模型、状态仓库和异常边界。

## 必须补充的设计点

- package/module 边界、接口可见性、依赖方向和禁止循环依赖策略。
- 领域模型、DTO、Repository、UseCase、Facade 等职责分工。
- 线程池、串行队列、回调、Future、消息分发、状态一致性约束。
- checked / unchecked 异常边界、错误码转换、审计与日志脱敏。
- 面向测试的接口抽象、可替换实现和稳定扩展点。

## 输出约束

- 文档中必须说明 Java 模块如何支撑可维护性与可测试性。
- 必须说明状态流、异常流和并发模型，而不是只给类名清单。
- 如果 Java 只是桥接层，必须说明它与 C++/native 层的桥接契约。
