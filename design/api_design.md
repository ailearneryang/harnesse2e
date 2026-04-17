# 越野信息集成 API 设计

Generated at: 2026-04-17

| 属性 | 内容 |
| --- | --- |
| 关联需求 | `runs/task-20260417104007-cd19df/software-requirement-orchestrator/requirements_spec.md` |
| 关联架构 | `design/architecture.md` |
| 平台 | ICC Android 单进程系统服务 |

## 1. 设计原则

1. 输入接入、算法调用、结果发布和诊断查询分层解耦，未冻结协议项只出现在适配层或映射层（CON-005、CON-006）。
2. UI、CAN 和诊断只能消费 `UnifiedResultView`，不得各自触发独立算法计算（FUN-022）。
3. 清零相关接口必须显式返回接受/拒绝与原因码，并形成审计日志（FUN-023~FUN-025、SEC-001）。
4. 所有错误都使用明确状态码传播，不做成功形态兜底或静默重试（REL-001、REL-002）。

## 2. 接口总览

| 接口域 | 调用方向 | 主要能力 | 通信方式 |
| --- | --- | --- | --- |
| Input Adapter API | Android/车身系统 -> Offroad Service | IMU、GPS、车速、气压、清零事件上送 | Callback / Binder |
| Orchestration API | UI/工厂工具 -> Offroad Service | 状态查询、清零请求、配置刷新 | Binder / 系统服务 |
| Publish API | Offroad Service -> UI/CAN/诊断 | 统一结果快照发布 | 进程内回调 / 车机发布接口 |
| JNI Engine API | Offroad Service -> Native Engine | 计算、重置、快照恢复 | JNI |
| Diagnostic API | 诊断工具 -> Offroad Service | 运行状态、故障、审计查询 | Binder / 调试接口 |

## 3. 输入适配接口

### 3.1 输入事件模型

| 事件 | 来源 | 关键字段 | 说明 |
| --- | --- | --- | --- |
| `onImuSample` | `SensorManager` | `timestampNs`、`accel[3]`、`gyro[3]`、`quality` | 驱动姿态与指南针计算 |
| `onLocationSample` | `LocationManager` | `timestampMs`、`altitudeM`、`bearingDeg`、`isValid` | 驱动海拔融合和指南针可用性判定 |
| `onVehicleSpeed` | CarService/VHAL | `timestampMs`、`speedKph`、`isValid` | 触发移动/静止切换与记忆值保存 |
| `onBarometerSample` | CarService/VHAL | `timestampMs`、`pressureHpa`、`isValid` | 驱动气压显示和海拔主输入 |
| `onZeroRequest` | CarService/VHAL / 工厂工具 | `requestId`、`source`、`commandValue` | 进入清零守卫流程 |

### 3.2 输入归一化约束

- 所有输入进入核心服务前统一转换为 `InputSnapshot` 子结构，并补齐 `source_state`、`last_update_ts`、`quality_flag`。
- 非法数值、时间戳倒退或来源未授权时立即标记为 `INVALID_INPUT`，不得直接送入算法引擎。
- 输入时效阈值和异常值编码使用配置项表达，在 `CFG-005` 冻结前保持占位。

## 4. 编排与控制接口

### 4.1 Offroad Service 对外接口

| 方法 | 入参 | 返回 | 说明 |
| --- | --- | --- | --- |
| `getCurrentResult()` | 无 | `UnifiedResultView` | 查询当前统一结果快照 |
| `requestCalibration(request)` | `CalibrationRequest` | `CalibrationResponse` | 发起清零请求 |
| `reloadConfig(versionHint)` | `string?` | `ConfigReloadResult` | 重新加载车型/协议配置 |
| `getHealthSnapshot()` | 无 | `HealthSnapshot` | 查询输入健康度与运行状态 |
| `getAuditRecords(filter)` | `AuditQuery` | `AuditRecord[]` | 查询清零和恢复审计记录 |

### 4.2 清零请求/响应

```json
{
  "requestId": "cal-20260417-0001",
  "source": "after_sales_tool",
  "commandValue": 1,
  "vehicleState": {
    "speedKph": 0.0,
    "isLevelGround": true
  }
}
```

```json
{
  "accepted": true,
  "resultCode": "ACCEPTED",
  "message": "calibration queued",
  "auditId": "audit-cal-20260417-0001"
}
```

### 4.3 结果与健康度对象

| 对象 | 关键字段 | 说明 |
| --- | --- | --- |
| `UnifiedResultView` | `publishSeq`、12 个输出信号、`stateFlags`、`updatedAt` | UI/CAN/诊断共享快照 |
| `HealthSnapshot` | `serviceState`、`inputAges`、`restartCount`、`configVersion` | 运行状态与输入健康度 |
| `ConfigReloadResult` | `success`、`configVersion`、`reason` | 配置重载结果 |

## 5. 发布接口

### 5.1 UI/CAN/诊断统一发布约定

| 发布目标 | 接口语义 | 必要约束 |
| --- | --- | --- |
| UI | 发布最新 `UnifiedResultView` | 只展示有效或允许的降级结果；无效项隐藏或置灰 |
| CAN `0x4F0` | 将 `UnifiedResultView` 映射为协议输出 | 位定义、周期、异常值编码配置化 |
| 诊断 | 发布故障事件和状态快照 | 保留故障原因、输入健康度、配置版本 |

- `publishSeq` 单调递增，用于判定 UI 与 CAN 是否消费同一批结果。
- 任一输出失败不得回写修改结果内容，只能记录独立发布错误并保留原始快照。

## 6. JNI Engine 接口

### 6.1 Native 方法建议

| 方法 | 入参 | 返回 | 说明 |
| --- | --- | --- | --- |
| `nativeInit(configSnapshot)` | `ConfigSnapshot` | `EngineHandle` | 初始化算法引擎 |
| `nativeProcess(snapshot, state)` | `InputSnapshot`、`PersistedState` | `EngineResult` | 执行一次计算 |
| `nativeRequestCalibration(request, state)` | `CalibrationRequest`、`PersistedState` | `CalibrationDecision` | 判断并执行清零 |
| `nativeRestoreState(persistedState)` | `PersistedState` | `RestoreResult` | 恢复上次成功状态 |
| `nativeRelease(handle)` | `EngineHandle` | `void` | 释放引擎资源 |

### 6.2 JNI 错误码

| 错误码 | 说明 |
| --- | --- |
| `OK` | 处理成功 |
| `INVALID_INPUT` | 输入值非法、缺字段或时序错误 |
| `DEGRADED` | 输出已降级但服务仍可用 |
| `STATE_ERROR` | 内部状态损坏或快照恢复失败 |
| `CAL_REJECTED` | 清零条件/授权不满足 |

## 7. 版本与兼容性

- 对外接口保持语义稳定，未冻结字段统一通过 `configVersion` 和映射表管理。
- `UnifiedResultView`、`PersistedState`、`ConfigSnapshot` 都需要显式 `schemaVersion` 字段。
- 新版本若增加字段，默认只能向后兼容追加，禁止复用旧字段语义。

*文档结束*
