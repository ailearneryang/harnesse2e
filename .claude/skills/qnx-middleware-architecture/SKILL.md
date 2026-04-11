---
name: qnx-middleware-architecture
description: 'Use for QNX Neutrino middleware, PPS, resource manager, channel/message passing, Screen, io-pkt, adaptive partitioning, high reliability and real-time service architecture in cockpit, cluster or embedded requirements and architecture docs.'
---

# QNX Middleware Architecture

## 适用场景

- 需求涉及 QNX Neutrino 服务、resource manager、PPS、消息通道或实时调度。
- 需要设计高可靠、可恢复、低时延的座舱或仪表域中间件。
- 需要说明与 Android、Linux 或 MCU 之间的跨域接口。

## 必须补充的设计点

- 进程优先级、调度类、分区策略和关键线程实时性目标。
- PPS、message passing、resource manager、socket 等通信方式的分工。
- service restart、故障隔离、持久化、冷启动与热启动恢复。
- Screen、io-pkt、驱动代理、设备访问权限和关键资源占用预算。
- 跨 OS 桥接代理、消息序列化格式、超时与错误传播模型。

## 输出约束

- 文档中必须说明哪些路径需要实时保证，哪些路径允许异步降级。
- 必须说明 QNX 服务与 Android/Linux 侧代理之间的边界和故障域。
- 必须说明分区、优先级和恢复机制如何支撑稳定性目标。
