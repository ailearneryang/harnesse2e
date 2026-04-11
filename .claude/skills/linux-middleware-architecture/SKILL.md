---
name: linux-middleware-architecture
description: 'Use for Linux middleware, Linux daemon, systemd service, POSIX IPC, D-Bus, Unix socket, shared memory, epoll, watchdog and resource isolation architecture in cockpit, IVI or embedded platform requirements and architecture docs.'
---

# Linux Middleware Architecture

## 适用场景

- 需求涉及 Linux daemon、后台服务、systemd 管理、POSIX 线程与定时器。
- 需要设计 D-Bus、Unix Domain Socket、共享内存、epoll 驱动的服务通信。
- 需要明确服务启动顺序、watchdog、资源隔离、权限与日志策略。

## 必须补充的设计点

- service / daemon 拆分原则、systemd unit 依赖和启动时序。
- 进程模型、线程模型、崩溃重启、watchdog、心跳与健康检查。
- IPC 选型边界：D-Bus 适合控制面，socket 适合数据面，共享内存适合高吞吐低拷贝。
- 文件系统、配置、日志轮转、core dump、权限模型和最小权限运行。
- CPU 绑核、优先级、内存占用、fd 泄漏、背压和队列长度约束。

## 输出约束

- 文档中必须有 Linux 服务拓扑图或 service matrix。
- 必须说明 daemon 与上层应用、下层驱动或其他 OS 的接口边界。
- 必须说明异常恢复、服务拉起、资源泄漏防控和诊断方式。
