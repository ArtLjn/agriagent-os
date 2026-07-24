# 01 — HTTP API 协议

> 状态：草稿 | 维护：BlockShip | 关联：[02_Agent内部接口](./02_Agent内部接口.md)、[03_外部服务接口](./03_外部服务接口.md)、[04_Skill接口契约](./04_Skill接口契约.md)

---

## 1. 基础约定

| 项 | 约定 |
| --- | --- |
| 后端注册路径 | 代码内直接注册 `/auth`、`/agent`、`/smart-fill`、`/planting`、`/admin` 等根路径 |
| 对外挂载前缀 | 部署层可通过 Nginx/API Gateway 挂到 `/api/v1`；本文 API 清单优先写代码真实路径 |
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
POST /auth/login
Body: { "phone": "...", "password": "..." }
Response: {
  "access_token": "...",
  "token_type": "bearer",
  "user": { "id": "...", "phone": "...", "nickname": "...", "role": "user" }
}
```

### 4.2 注册

```
POST /auth/register
Body: { "phone": "...", "password": "...", "nickname": "..." }
Response: 同登录
```

### 4.3 当前用户

```
GET /auth/me
Response: { "id": "...", "phone": "...", "farm": {...} }
```

## 5. 业务 API 清单

### 5.1 Agent（聊天）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/agent/skills` | App 端技能能力列表 |
| POST | `/agent/chat` | 同步对话 |
| POST | `/agent/chat/stream` | 流式对话（SSE） |
| GET | `/agent/conversations` | 历史会话列表 |
| GET | `/agent/conversations/{session_id}/messages` | 单会话消息 |
| GET | `/agent/conversations/{session_id}/debug-export` | 会话调试导出 |
| GET | `/agent/daily` | 获取每日建议 |
| POST | `/agent/daily/refresh` | 强制刷新每日建议 |
| POST | `/agent/report` | 生成周期报告 |
| GET | `/agent/advice-history` | 建议历史 |
| GET | `/agent/report-history` | 报告历史 |
| GET | `/agent/reports` | 报告分页列表 |
| DELETE | `/agent/reports/{report_id}` | 删除报告 |

### 5.2 Smart Fill

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/smart-fill/scenarios` | 场景列表 |
| POST | `/smart-fill/parse` | 提交场景表单并返回草稿，不直接落库 |

### 5.3 记账

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/costs` | 成本记录列表（分页 + 过滤） |
| POST | `/costs` | 新增（直接，绕过 Agent） |
| DELETE | `/costs/{record_id}` | 删除 |
| GET | `/costs/cycles/{cycle_id}/profit` | 茬口利润 |
| GET | `/costs/summary/{year}` | 年度汇总 |
| POST | `/costs/parse` | 成本自然语言解析 |
| GET | `/cost-categories` | 分类列表 |
| POST | `/cost-categories` | 新增分类 |
| DELETE | `/cost-categories/{category_id}` | 删除分类 |
| GET | `/debts` | 赊账列表 |
| POST | `/debts` | 新增赊账 |
| POST | `/debts/settle` | 结清赊账 |

### 5.4 作物与茬口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/crops/templates` | 当前农场作物模板 |
| POST | `/crops/templates` | 创建模板 |
| GET | `/crops/templates/system?category=` | 系统模板库（`farm_id IS NULL`，当前支持按 category 过滤） |
| POST | `/crops/templates/system/{id}/import` | 导入系统模板到当前农场（副本模式） |
| PUT | `/crops/templates/system/{template_id}` | 管理员更新系统模板 |
| DELETE | `/crops/templates/system/{template_id}` | 管理员删除系统模板 |
| GET | `/crops/templates/{template_id}` | 模板详情 |
| PUT | `/crops/templates/{template_id}` | 更新模板 |
| DELETE | `/crops/templates/{template_id}` | 删除模板 |
| POST | `/crops/templates/parse` | 作物模板自然语言解析 |
| GET | `/cycles` | 茬口列表 |
| POST | `/cycles` | 创建茬口 |
| GET | `/cycles/{cycle_id}` | 茬口详情 |
| PUT | `/cycles/{cycle_id}` | 更新茬口 |
| DELETE | `/cycles/{cycle_id}` | 删除茬口 |
| POST | `/cycles/{cycle_id}/advance-stage` | 推进阶段 |
| GET | `/planting/units` | 地块列表 |
| POST | `/planting/units` | 新增地块 |
| PUT | `/planting/units/{unit_id}` | 更新地块 |
| DELETE | `/planting/units/{unit_id}` | 删除地块 |

**地域化说明**：`region_tag` 仍是 openspec 提案维度，当前代码未把 `region` 暴露为系统模板查询参数。详见 [openspec/changes/extend-crop-template-with-region-tag](../../../openspec/changes/extend-crop-template-with-region-tag/proposal.md)。

### 5.5 农事与工人

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/logs` | 农事日志 |
| POST | `/logs` | 记录农事 |
| PUT | `/logs/{log_id}` | 更新农事日志 |
| DELETE | `/logs/{log_id}` | 删除农事日志 |
| GET | `/planting/work-orders` | 工单列表 |
| POST | `/planting/work-orders` | 派工 |
| GET | `/planting/work-orders/{work_order_id}` | 工单详情 |
| GET | `/planting/recent-operations` | 近期农事操作 |
| GET | `/planting/operation-types` | 作业类型 |
| GET | `/planting/workers` | 工人列表 |
| POST | `/planting/workers` | 新增工人 |
| GET | `/planting/workers/summary` | 工人用工摘要 |
| PUT | `/planting/workers/{worker_id}` | 更新工人 |
| DELETE | `/planting/workers/{worker_id}` | 停用工人 |
| POST | `/planting/labor/wages` | 保存工资记录 |
| PATCH | `/planting/labor/wages/{labor_entry_id}` | 更新工资记录 |
| GET | `/planting/labor/unsettled-summary` | 未结工资汇总 |

### 5.6 天气

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/weather/forecast` | 当前天气、未来预报与预警聚合 |
| GET | `/locations/search` | 地点搜索 |
| GET | `/locations/meta` | 地点元信息 |
| GET | `/locations/regions` | 地域枚举 |

### 5.7 设置与反馈

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/settings` | 用户设置 |
| PUT | `/settings` | 更新设置 |
| POST | `/agent/feedback` | 提交反馈 |
| GET | `/agent/feedback/stats` | 反馈统计 |

### 5.8 Admin（仅管理员）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/admin/users` | 用户列表 |
| GET | `/admin/users/quota-overview` | 用户配额总览 |
| PUT | `/admin/users/{user_id}/status` | 更新用户状态 |
| GET | `/admin/skills` | Skill 注册表 |
| PUT | `/admin/skills/{skill_name}/enabled` | 启停 Skill |
| GET | `/admin/prompts` | Prompt 列表 |
| POST | `/admin/prompts/reload` | 重新加载 Prompt |
| GET | `/admin/traces` | trace 列表 |
| GET | `/admin/traces/requests` | trace 请求聚合列表 |
| GET | `/admin/traces/{request_id}/timeline` | trace 时间线 |
| GET | `/admin/data-flywheel/samples` | DataFlywheel 样本 |
| POST | `/admin/data-flywheel/samples/{sample_id}/labels` | 标注 |
| GET | `/admin/data-flywheel/daily-review/inbox` | 问题链 inbox |
| GET | `/admin/data-flywheel/repair-packs` | repair pack 列表 |
| POST | `/simulation/run` | 跑仿真 |
| GET | `/simulation/runs` | 仿真运行列表 |
| GET | `/admin/stats/tokens` | Token 统计 |
| GET | `/admin/dashboard/summary` | 后台看板摘要 |

## 6. SSE 流式协议

`POST /agent/chat/stream` 返回 `text/event-stream`：

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

当前代码中 Pending 通过对话确认和 `agent_pending_plans` 执行器流转，不再暴露独立 `/pending/{id}/confirm` HTTP 路由。

### 8.3 取消

用户取消同样通过对话语义或前端 pending plan 控件进入 Agent 流程，后端未注册独立 `/pending/{id}/cancel` 路由。

### 8.4 过期

Pending Action 默认 5 分钟过期，过期后无法 confirm；前端展示「已过期，请重新发起」。

## 9. API 文档生成

- FastAPI 自动生成 OpenAPI 3 schema：`/docs`（Swagger）、`/redoc`（ReDoc）
- 生产环境关闭 `/docs` 防止泄露
- 同步导出 `docs/reference/api-spec.yaml`，由 CI 验证

## 10. 版本治理

- 代码内路由当前不统一携带 `/api/v1`；若部署层需要版本前缀，应由 Nginx/API Gateway 统一挂载并清晰记录映射
- 破坏性变更优先通过部署前缀或新 router 版本隔离，旧版本至少保留 6 个月
- 字段新增不需版本升级（前向兼容）
- 字段删除/重命名必须 v2

## 11. 相关文档

- [02_Agent内部接口](./02_Agent内部接口.md)
- [03_外部服务接口](./03_外部服务接口.md)
- [04_Skill接口契约](./04_Skill接口契约.md)
- [01_正式设计/01_Agent平台架构](../01_正式设计/01_Agent平台架构.md)
- 现有 API spec：[../../../docs/reference/api-spec.yaml](../../../docs/reference/api-spec.yaml)
