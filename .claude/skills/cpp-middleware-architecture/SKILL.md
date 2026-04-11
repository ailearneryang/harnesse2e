---
name: cpp-middleware-architecture
description: 'Use for C++ middleware, native service, performance critical module, real-time path, memory ownership, threading, IPC bridge, ABI boundary and reliability architecture from automotive or embedded requirements and design docs.'
---

# C++ Middleware Architecture

## 适用场景

- 需求涉及 C++ native service、性能敏感路径、低时延链路、驱动代理或跨 OS 中间件。
- 需要设计对象生命周期、线程同步、零拷贝、高可靠与 ABI 边界。

## 必须补充的设计点

- 模块边界、头文件暴露面、ABI 稳定性和接口版本策略。
- 所有权模型、对象生命周期、资源释放、异常禁用或错误码语义。
- 线程模型、锁粒度、无锁队列适用边界、优先级反转和死锁规避。
- IPC 桥接、序列化、零拷贝、缓冲区管理和背压策略。
- 崩溃恢复、内存泄漏、句柄泄漏、watchdog、性能观测点和诊断接口。

## 输出约束

- 文档中必须说明 C++ 模块的生命周期、线程策略和内存策略。
- 必须说明哪些路径走高性能 native 数据面，哪些路径可通过上层控制面抽象。
- 如果存在 Java / Android 交互，必须说明 JNI、Binder 或代理层的边界与风险。
