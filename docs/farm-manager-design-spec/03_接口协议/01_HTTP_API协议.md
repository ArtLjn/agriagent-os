# 01 — HTTP API 协议

> 状态：草稿 | 维护：BlockShip | 关联：[02_Agent内部接口](./02_Agent内部接口.md)、[03_外部服务接口](./03_外部服务接口.md)、[04_Skill接口契约](./04_Skill接口契约.md)

---

## 1. 基础约定

| 项 | 约定 |
| --- | --- |
| 路径前缀 | `/api/v1/` |
| 协议 | HTTPS（生产）/ HTTP（开发） |
| 认证 | JWT in `Authorization: Bearer <token>` |
| 请求格式 | JSON（`Content-Type: application/json`） |
| 响应格式 | JSON |
| 时间格式 | ISO 8601 UTC（如 `2026-06-19T10:30:00Z`） |
| 货币单位 | 分（int），RMB |
| 字符集 | UTF-8 |
| 路径 trace | Header `X-Trace-Id`（客户端可传，服务端兜底生成） |
| 分页参数 | `?page=1&page_size=20` |
| 分页响应 | `{items, total, page, page_size}` |

## 2. 标准响应

### 2.1 成功响应

```json
{
  "code": 0,
  "message": "ok",
  "data": { ... }
}
```

或直接返回业务数据（无包裹），由各端点决定。**当前阶段两种风格并存，待统一**。

### 2.2 错误响应

```json
{
  "code": "COST_001",
  "message": "金额必须大于 0",
  "detail": { "field": "amount", "value": -100 }
}
```

错误码格式：`<DOMAIN>_<NUMBER>`，如：
- `AUTH_001` — 用户名或密码错误
- `COST_001` — 金额必须大于 0
- `CYCLE_001` — 当前茬口不存在
- `AGENT_001` — LLM 调用超时
- `SYS_500` — 系统内部错误

## 3. HTTP 状态码

| 码 | 用途 |
| --- | --- |
| 200 | 成功 |
| 201 | 创建成功（POST） |
| 204 | 删除成功（无返回体） |
| 400 | 参数错误（Pydantic 校验失败） |
| 401 | 未认证 / Token 失效 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 冲突（如重复创建） |
| 422 | 业务校验失败（如金额超范围） |
| 429 | 限流 |
| 500 | 服务端错误 |
| 502 | 上游 LLM / 天气服务错误 |
| 503 | 服务不可用（维护中） |

## 4. 认证与会话

### 4.1 登录

```
POST /api/v1/auth/login
Body: { "username": "...", "password": "..." }
Response: {
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { "id": 1, "username": "...", "farm_id": 1 }
}
```

### 4.2 刷新 Token

```
POST /api/v1/auth/refresh
Body: { "refresh_token": "..." }
Response: 同登录
```

### 4.3 当前用户

```
GET /api/v1/auth/me
Response: { "id": 1, "username": "...", "farm_id": 1, "permissions": [...] }
```

## 5. 业务 API 清单

### 5.1 Agent（聊天）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/agent/chat` | 同步对话 |
| POST | `/api/v1/agent/chat/stream` | 流式对话（SSE） |
| POST | `/api/v1/agent/advice` | 触发每日建议 |
| GET | `/api/v1/agent/history` | 历史会话列表 |
| GET | `/api/v1/agent/sessions/{id}` | 单会话详情 |
| POST | `/api/v1/pending/{id}/confirm` | 确认 Pending Action |
| POST | `/api/v1/pending/{id}/cancel` | 取消 Pending Action |

### 5.2 Smart Fill

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/scenarios` | 场景列表 |
| POST | `/api/v1/parse` | 提交场景表单 |

### 5.3 记账

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/costs` | 成本记录列表（分页 + 过滤） |
| POST | `/api/v1/costs` | 新增（直接，绕过 Agent） |
| PUT | `/api/v1/costs/{id}` | 修改 |
| DELETE | `/api/v1/costs/{id}` | 删除 |
| GET | `/api/v1/costs/summary` | 汇总 |
| GET | `/api/v1/costs/analytics` | 趋势分析 |
| GET | `/api/v1/costs/categories` | 分类列表 |
| POST | `/api/v1/costs/categories` | 新增分类 |
| GET | `/api/v1/debts` | 赊账列表 |

### 5.4 作物与茬口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/crops/templates` | 当前农场作物模板 |
| POST | `/api/v1/crops/templates` | 创建模板 |
| GET | `/api/v1/crops/templates/system?crop_name=&region=` | 系统模板库（`farm_id IS NULL`，按 region 优先匹配，不足 fallback 到 default） |
| POST | `/api/v1/crops/templates/system/{id}/import` | 导入系统模板到当前农场（副本模式，携带 `region_tag`） |
| GET | `/api/v1/cycles` | 茬口列表 |
| POST | `/api/v1/cycles` | 创建茬口 |
| DELETE | `/api/v1/cycles/{id}` | 删除茬口 |
| GET | `/api/v1/planting-units` | 地块列表 |

**地域化说明**：`region` 参数从 `UserSettings.default_city` 映射（拼音小写，如 `xuzhou`），未映射城市 fallback 到 `default`。详见 [openspec/changes/extend-crop-template-with-region-tag](../../../openspec/changes/extend-crop-template-with-region-tag/proposal.md)。
| POST | `/api/v1/planting-units` | 新增地块 |

### 5.5 农事与工人

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/logs` | 农事日志 |
| POST | `/api/v1/logs` | 记录农事 |
| GET | `/api/v1/operations` | 工单列表 |
| POST | `/api/v1/operations` | 派工 |
| GET | `/api/v1/workers` | 工人列表 |
| GET | `/api/v1/labor/payables` | 工资应付 |

### 5.6 天气

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/weather/current` | 当前天气 |
| GET | `/api/v1/weather/forecast` | 未来 N 天预报 |
| GET | `/api/v1/weather/alerts` | 天气预警 |

### 5.7 设置与反馈

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/settings` | 用户设置 |
| PUT | `/api/v1/settings` | 更新设置 |
| POST | `/api/v1/feedback` | 提交反馈 |

### 5.8 Admin（仅管理员）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/admin/users` | 用户列表 |
| GET | `/api/v1/admin/skills` | Skill 注册表 |
| GET | `/api/v1/admin/traces` | trace 列表 |
| GET | `/api/v1/admin/traces/{id}` | trace 详情 |
| GET | `/api/v1/admin/data-flywheel/samples` | DataFlywheel 样本 |
| POST | `/api/v1/admin/data-flywheel/samples/{id}/label` | 标注 |
| GET | `/api/v1/admin/simulation/run` | 跑回归 |
| GET | `/api/v1/admin/evaluation/report` | 评测报告 |
| GET | `/api/v1/admin/tokens/stats` | Token 统计 |

## 6. SSE 流式协议

`POST /api/v1/agent/chat/stream` 返回 `text/event-stream`：

```
event: token
data: {"text": "已"}

event: token
data: {"text": "记账"}

event: pending
data: {"pending_id": "...", "summary": "化肥 200 元 赊账", "expires_at": "..."}

event: tool_call
data: {"skill": "create_cost_record", "params": {...}, "status": "pending"}

event: done
data: {"message_id": 123, "trace_id": "..."}
```

事件类型：

| 事件 | 含义 | data 字段 |
| --- | --- | --- |
| `token` | LLM 输出的 token 流 | `text` |
| `tool_call` | 工具调用 | `skill`, `params`, `status` |
| `pending` | 待确认动作 | `pending_id`, `summary`, `expires_at` |
| `reflection` | 反思触发 | `check`, `result` |
| `error` | 错误 | `code`, `message` |
| `done` | 流结束 | `message_id`, `trace_id` |

客户端必须处理 `error` 和 `done`；其他事件可选。

## 7. 限流

| 端点类型 | 限流策略 |
| --- | --- |
| 认证（login/refresh） | 5 req/min/IP |
| 业务 API | 100 req/min/user |
| Agent chat | 20 req/min/user |
| Agent stream | 5 并发/user |
| Admin API | 60 req/min/admin |

超限返回 `429 Too Many Requests` + Header `Retry-After: 60`。

## 8. Pending Action 详细协议

### 8.1 创建

Agent 在写操作 Skill 触发时，返回 SSE `pending` 事件，前端展示确认 UI。

### 8.2 确认

```
POST /api/v1/pending/{pending_id}/confirm
Response: { "code": 0, "data": { "executed": true, "result": {...} } }
```

### 8.3 取消

```
POST /api/v1/pending/{pending_id}/cancel
Response: { "code": 0, "data": { "cancelled": true } }
```

### 8.4 过期

Pending Action 默认 5 分钟过期，过期后无法 confirm；前端展示「已过期，请重新发起」。

## 9. API 文档生成

- FastAPI 自动生成 OpenAPI 3 schema：`/docs`（Swagger）、`/redoc`（ReDoc）
- 生产环境关闭 `/docs` 防止泄露
- 同步导出 `docs/reference/api-spec.yaml`，由 CI 验证

## 10. 版本治理

- 路径前缀 `/api/v1/` 锁定 v1
- 破坏性变更必须 `/api/v2/`，旧 v1 保留 6 个月
- 字段新增不需版本升级（前向兼容）
- 字段删除/重命名必须 v2

## 11. 相关文档

- [02_Agent内部接口](./02_Agent内部接口.md)
- [03_外部服务接口](./03_外部服务接口.md)
- [04_Skill接口契约](./04_Skill接口契约.md)
- [01_正式设计/01_Agent平台架构](../01_正式设计/01_Agent平台架构.md)
- 现有 API spec：[../../../docs/reference/api-spec.yaml](../../../docs/reference/api-spec.yaml)
