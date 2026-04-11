---
name: android-middleware-architecture
description: 'Use for Android middleware, AOSP, Android Automotive, Binder, AIDL, HIDL, HAL, SystemServer, CarService, Service, APK and framework-native boundary architecture from requirements and design documents.'
---

# Android Middleware Architecture

## 适用场景

- 需求涉及 Android Framework、SystemServer、CarService、APK、前后台 Service 或 HAL。
- 需要设计 Binder/AIDL/HIDL 接口、Framework 与 native service 的边界。
- 需要考虑 Android Automotive 端侧性能、权限、生命周期和后台限制。

## 必须补充的设计点

- App、Framework、System Service、HAL、Native Daemon 的职责划分。
- Binder/AIDL 作为控制面时的接口粒度、线程池、回调、死亡通知与权限校验。
- 前台服务、后台限制、启动链路、Boot 完成时序和系统广播使用约束。
- Java 层与 native 层桥接、JNI 风险、ANR、防阻塞与主线程约束。
- PackageManager、Car API、Vehicle HAL、权限模型、日志与埋点脱敏。

## 输出约束

- 文档中必须明确 App 与 System Service 的边界，禁止泛化跨层直连。
- 必须区分 Binder 控制面与高吞吐数据面的传输策略。
- 必须说明 Android 生命周期、权限和后台限制如何影响架构选型。
