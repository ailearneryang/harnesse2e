# 车机 App Store API 设计文档

## 1. 概览

### 1.1 API 边界

本文档定义车机 App Store 的核心接口边界，覆盖目录查询、应用详情、安装任务、更新查询、状态回传和运营发布接口。接口设计遵循以下原则：

1. 轻量元数据与大文件下载分离，目录和策略走业务 API，安装包走 CDN 直传。
2. 端侧安装状态以 `InstallTask` 为单一事实源，任务接口幂等可恢复。
3. 同一术语在需求与架构文档中保持一致，如 `AppListing`、`AppRelease`、`InstallTask`、`EntitlementSnapshot`。

### 1.2 版本策略

- 外部业务 API 使用 `/v1/` 前缀。
- 重大字段语义变化通过 `/v2/` 演进，不做同名字段破坏式重定义。
- CDN 下载地址不承诺长期稳定，必须通过发布接口动态获取。

### 1.3 鉴权与访问控制

| 访问主体 | 鉴权方式 | 可访问范围 |
| --- | --- | --- |
| 车机设备 | 设备令牌 | 公共目录、设备级策略、任务状态回传 |
| 登录用户 | 设备令牌 + 用户令牌 | 授权应用安装、我的应用、个性化推荐 |
| 运营后台 | 后台 RBAC | 上下架、推荐位、灰度、冻结、查询审计 |

## 2. 接口清单

### 2.1 GET /v1/store/home

- 需求追溯：FUN-001、CFG-001、DAT-001
- 路径：`/v1/store/home`
- 方法：`GET`
- 描述：获取首页推荐、分类、榜单、活动和最近更新摘要。

#### Query

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `region` | 是 | 设备区域 |
| `vehicle_model` | 是 | 车型标识 |
| `client_version` | 是 | 商店客户端版本 |
| `catalog_version` | 否 | 本地目录版本，用于增量刷新 |

#### Response

```json
{
  "request_id": "req-1001",
  "catalog_version": "2026.04.15.01",
  "generated_at": "2026-04-15T13:30:00Z",
  "sections": [
    {
      "type": "featured",
      "title": "精选推荐",
      "items": [
        {
          "app_id": "nav.pro",
          "release_id": "rel-120",
          "name": "高德导航车机版",
          "icon_url": "https://cdn.example/icon.png",
          "availability": "installable"
        }
      ]
    }
  ]
}
```

#### 错误码

| 错误码 | 说明 |
| --- | --- |
| `CATALOG_UNAVAILABLE` | 目录服务不可用 |
| `INVALID_DEVICE_CONTEXT` | 设备画像不完整或不合法 |

#### 幂等性与重试策略

- 只读接口，可安全重试。
- 超时后端侧可回退到本地缓存，不要求服务端保持会话状态。

### 2.2 GET /v1/apps

- 需求追溯：FUN-002、FUN-003
- 路径：`/v1/apps`
- 方法：`GET`
- 描述：按关键词、分类和过滤条件查询应用列表。

#### Query

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `q` | 否 | 搜索关键词 |
| `category` | 否 | 分类编码 |
| `page` | 否 | 页码 |
| `page_size` | 否 | 每页数量 |
| `installed_state` | 否 | `all/installed/not_installed/updatable` |

#### Response

```json
{
  "request_id": "req-1002",
  "page": 1,
  "page_size": 20,
  "total": 1,
  "items": [
    {
      "app_id": "music.plus",
      "name": "音乐 Plus",
      "summary": "海量音乐内容",
      "category": "media",
      "availability": "restricted",
      "availability_reason": "driving_restricted"
    }
  ]
}
```

#### 错误码

- `INVALID_QUERY`
- `SEARCH_BACKEND_TIMEOUT`

#### 幂等性与重试策略

- 只读接口，可重试。
- 搜索超时可回退到本地索引或提示用户重试。

### 2.3 GET /v1/apps/{appId}

- 需求追溯：FUN-004、FUN-015、FUN-023
- 路径：`/v1/apps/{appId}`
- 方法：`GET`
- 描述：获取应用详情、版本摘要、权限摘要和兼容性说明。

#### Response

```json
{
  "request_id": "req-1003",
  "app": {
    "app_id": "video.family",
    "name": "家庭视频",
    "developer": "OEM Media",
    "version": "3.2.1",
    "package_size_bytes": 104857600,
    "permissions_summary": [
      "存储访问",
      "麦克风"
    ],
    "compatibility": {
      "availability": "installable",
      "reason": null
    }
  }
}
```

#### 错误码

- `APP_NOT_FOUND`
- `APP_NOT_VISIBLE`

#### 幂等性与重试策略

- 只读接口，可重试。

### 2.4 POST /v1/install-tasks

- 需求追溯：FUN-005、FUN-006、FUN-007、FUN-020、SEC-001、SEC-002
- 路径：`/v1/install-tasks`
- 方法：`POST`
- 描述：创建安装、更新或卸载任务。

#### Request

```json
{
  "app_id": "nav.pro",
  "release_id": "rel-120",
  "action_type": "install",
  "actor_context": {
    "user_id": "user-1",
    "session_id": "sess-1"
  },
  "device_context": {
    "driving_state": "parked",
    "network_type": "wifi"
  }
}
```

#### Response

```json
{
  "request_id": "req-1004",
  "task_id": "task-9001",
  "status": "waiting_precheck",
  "idempotent_reused": false
}
```

#### 错误码

| 错误码 | 说明 |
| --- | --- |
| `NOT_LOGGED_IN` | 未登录 |
| `ENTITLEMENT_DENIED` | 无授权 |
| `LOW_STORAGE` | 存储不足 |
| `NO_NETWORK` | 网络不可用 |
| `DRIVING_RESTRICTED` | 驾驶中限制 |
| `TASK_CONFLICT` | 已存在活动任务 |
| `RELEASE_UNAVAILABLE` | 版本已下架或冻结 |

#### 幂等性与重试策略

- 使用 `Idempotency-Key` 头或 `app_id + release_id + action_type + actor` 组合做幂等。
- 若同类活动任务存在，返回已有 `task_id`。
- 安装器已执行后不得对同一任务自动重试安装。

### 2.5 GET /v1/install-tasks/{taskId}

- 需求追溯：FUN-006、FUN-008、FUN-021
- 路径：`/v1/install-tasks/{taskId}`
- 方法：`GET`
- 描述：查询任务进度、错误码和恢复状态。

#### Response

```json
{
  "request_id": "req-1005",
  "task_id": "task-9001",
  "app_id": "nav.pro",
  "release_id": "rel-120",
  "action_type": "install",
  "status": "downloading",
  "progress": 62,
  "retryable": true,
  "error_code": null
}
```

#### 错误码

- `TASK_NOT_FOUND`

#### 幂等性与重试策略

- 只读接口，可重试。

### 2.6 POST /v1/install-tasks/{taskId}/cancel

- 需求追溯：FUN-010、FUN-021
- 路径：`/v1/install-tasks/{taskId}/cancel`
- 方法：`POST`
- 描述：取消下载中或排队中的任务。

#### Response

```json
{
  "request_id": "req-1006",
  "task_id": "task-9001",
  "status": "cancelled"
}
```

#### 错误码

- `TASK_NOT_CANCELLABLE`
- `TASK_NOT_FOUND`

#### 幂等性与重试策略

- 重复取消返回同一终态。

### 2.7 GET /v1/updates

- 需求追溯：FUN-009、FUN-010
- 路径：`/v1/updates`
- 方法：`GET`
- 描述：获取当前设备可更新应用列表。

#### Response

```json
{
  "request_id": "req-1007",
  "items": [
    {
      "app_id": "music.plus",
      "installed_version": "1.0.0",
      "target_release_id": "rel-220",
      "target_version": "1.1.0"
    }
  ]
}
```

#### 错误码

- `UPDATES_UNAVAILABLE`

#### 幂等性与重试策略

- 只读接口，可重试。

### 2.8 POST /v1/telemetry/events

- 需求追溯：FUN-019、MNT-002、DIA-001
- 路径：`/v1/telemetry/events`
- 方法：`POST`
- 描述：批量上报曝光、点击、任务状态、失败和诊断事件。

#### Request

```json
{
  "events": [
    {
      "event_type": "install_failed",
      "occurred_at": "2026-04-15T13:35:00Z",
      "app_id": "nav.pro",
      "release_id": "rel-120",
      "task_id": "task-9001",
      "error_code": "SIGNATURE_INVALID"
    }
  ]
}
```

#### Response

```json
{
  "request_id": "req-1008",
  "accepted": 1
}
```

#### 错误码

- `INVALID_EVENT_PAYLOAD`
- `EVENT_BATCH_TOO_LARGE`

#### 幂等性与重试策略

- 事件上报可使用 `event_id` 去重。
- 网络失败时端侧可本地缓存后稍后重传。

### 2.9 POST /admin/v1/releases/{releaseId}/publish

- 需求追溯：FUN-014、FUN-018、CMP-001
- 路径：`/admin/v1/releases/{releaseId}/publish`
- 方法：`POST`
- 描述：运营后台执行发布、灰度或冻结状态变更。

#### Request

```json
{
  "operation": "freeze",
  "reason": "发现严重兼容性问题",
  "scope": {
    "region": ["CN"],
    "vehicle_model": ["X1"]
  }
}
```

#### Response

```json
{
  "request_id": "req-1009",
  "release_id": "rel-120",
  "status": "frozen"
}
```

#### 错误码

- `FORBIDDEN`
- `INVALID_RELEASE_STATE`
- `REVIEW_NOT_APPROVED`

#### 幂等性与重试策略

- 后台变更必须携带操作审计信息。
- 重复提交同一变更返回当前状态。

## 3. 事件与回调

| 事件 | 生产方 | 消费方 | 说明 |
| --- | --- | --- | --- |
| `catalog_updated` | Catalog Service | 车机端 | 目录或策略版本更新 |
| `release_revoked` | Release Service | 车机端 | 版本冻结、下架或撤回 |
| `task_status_changed` | Task Manager | UI / Telemetry | 任务状态变化 |
| `install_result_reported` | Install Bridge | Task Manager / Telemetry | 安装器返回结果 |

## 4. 失败场景与降级策略

1. **目录接口失败**：端侧回退到本地缓存，并提示“内容可能不是最新”。
2. **下载失败**：任务进入 `paused` 或 `failed`，展示错误码与重试入口。
3. **签名校验失败**：直接终止任务并上报 `SIGNATURE_INVALID`。
4. **下架事件与安装并发**：新建任务立即拒绝；已完成下载但未安装的任务在安装前再次校验版本状态。

## 5. 可观测性与审计字段

所有核心接口建议统一携带以下字段：

| 字段 | 说明 |
| --- | --- |
| `request_id` | 链路追踪 ID |
| `device_id` | 脱敏设备标识 |
| `user_id` | 脱敏用户标识 |
| `catalog_version` | 目录版本 |
| `policy_version` | 策略版本 |
| `task_id` | 任务 ID |

## 6. 待确认项

1. 是否需要对游客模式开放安装能力。
2. 自动更新是否需要独立 API 与后台调度接口。
3. 付费能力引入后是否新增订单与支付 API 域。
