# Minimal Permission Management API Design

Generated at: 2026-04-14

## 1. 设计原则

1. 复用现有审批与控制接口，优先做鉴权增强，不新增不必要的端点。
2. 所有写接口必须带身份上下文，默认拒绝匿名写入。
3. 错误语义固定为 `401/403/404/409`，方便前端与 Feishu 回调统一处理。

---

## 2. 身份上下文约定

### 2.1 请求头

| Header | 必填 | 说明 |
| --- | --- | --- |
| `X-User-Id` | 写接口是 | 调用人唯一标识 |
| `X-User-Name` | 否 | 展示名 |
| `X-User-Roles` | 写接口是 | 逗号分隔，如 `approver,operator` |
| `X-Request-Id` | 否 | 链路追踪 ID |

### 2.2 Feishu 回调补齐

Feishu 卡片回调进入后，服务端先将 Feishu 用户信息转换为上述 `ActorContext`，再进入权限判断。

---

## 3. API 总览

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/api/requests` | `task:create` | 提交任务 |
| `GET` | `/api/approvals` | `approval:list` | 查看待审批项 |
| `POST` | `/api/approvals/{taskId}/{approvalId}/resolve` | `approval:resolve` | 批准/拒绝审批 |
| `POST` | `/api/control/{action}` | `pipeline:control` | 控制流水线 |
| `GET` | `/api/state` | `task:read` | 查看完整状态，最小方案建议仅 approver/operator 可看全量 |

---

## 4. 详细接口定义

### 4.1 POST /api/requests

提交新任务。

**Authorization**

- `requester` / `approver` / `operator` 可调用。
- 匿名允许仅限内部联调关闭鉴权时；默认部署关闭匿名写入。

**Request**

```json
{
  "title": "approval smoke test",
  "text": "请设计一个最小的权限管理方案。这是人工审批链路联调，请在继续前等待人工审批。"
}
```

**Response 200**

```json
{
  "id": "task-20260414110545-158a12",
  "status": "queued"
}
```

### 4.2 GET /api/approvals

查询当前所有待审批项。

**Authorization**

- `approver` / `operator`

**Response 200**

```json
[
  {
    "id": "approval-8fa1d3c2",
    "task_id": "task-20260414110545-158a12",
    "task_title": "approval smoke test",
    "stage": "design",
    "reason": "Risky request requires human confirmation before continuing",
    "status": "pending",
    "required_role": "approver",
    "created_at": "2026-04-14T11:05:46Z"
  }
]
```

**Response 403**

```json
{
  "error": "forbidden",
  "message": "approval:list requires approver or operator"
}
```

### 4.3 POST /api/approvals/{taskId}/{approvalId}/resolve

批准或拒绝某个待审批项。

**Authorization**

- `approver` / `operator`
- 只有满足 `approval.required_role` 的角色才能执行

**Request**

```json
{
  "resolution": "approved",
  "note": "联调批准，继续执行"
}
```

**Response 200**

```json
{
  "id": "approval-8fa1d3c2",
  "task_id": "task-20260414110545-158a12",
  "stage": "design",
  "status": "approved",
  "required_role": "approver",
  "resolved_at": "2026-04-14T11:06:05Z",
  "resolved_by": {
    "actor_id": "feishu:ou_xxx",
    "display_name": "审批人A",
    "roles": ["approver"]
  },
  "resolution_channel": "feishu",
  "note": "联调批准，继续执行"
}
```

**Response 401**

```json
{
  "error": "unauthorized",
  "message": "missing actor context"
}
```

**Response 403**

```json
{
  "error": "forbidden",
  "message": "approval:resolve requires role approver"
}
```

**Response 409**

```json
{
  "error": "approval_already_resolved",
  "message": "approval approval-8fa1d3c2 has already been approved"
}
```

### 4.4 POST /api/control/{action}

控制流水线运行状态。

**Path 参数**

- `action in {pause, resume, stop}`

**Authorization**

- `operator`

**Request**

```json
{
  "note": "暂停等待外部系统恢复"
}
```

**Response 200**

```json
{
  "ok": true,
  "action": "pause"
}
```

### 4.5 GET /api/state

查看运行时状态。

**Authorization**

- `operator`：可查看全量。
- `approver`：可查看全量或脱敏全量。
- `requester`：仅返回本人任务摘要（最小方案可后置实现）。

---

## 5. 统一错误模型

```json
{
  "error": "forbidden",
  "message": "approval:resolve requires role approver",
  "request_id": "req-1d2f",
  "details": {
    "actor_id": "user:alice",
    "required_role": "approver"
  }
}
```

| 状态码 | 场景 |
| --- | --- |
| `401` | 未提供身份或身份解析失败 |
| `403` | 身份存在但权限不足 |
| `404` | 任务或审批单不存在 |
| `409` | 审批已被处理、状态冲突 |

---

## 6. 审计字段要求

以下字段必须进入日志、事件或审批结果：

| 字段 | 说明 |
| --- | --- |
| `request_id` | 链路追踪 |
| `actor_id` | 操作人 |
| `actor_roles` | 操作角色 |
| `action` | 资源动作 |
| `resource_id` | 任务/审批单 ID |
| `decision` | allow/deny |
| `reason` | 拒绝原因或审批意见 |

---

## 7. 向后兼容策略

1. 先为接口增加可选身份解析与审计，不立即中断历史读接口。
2. 对写接口采用“有身份则校验、无身份则按开关拒绝”的灰度方式。
3. 待 Feishu 与 Dashboard 均能稳定传递身份后，关闭匿名写入口。
