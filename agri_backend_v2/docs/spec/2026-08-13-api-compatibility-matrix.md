---
spec_id: 2026-08-13-api-compatibility-matrix
last_updated: 2026-08-22
status: draft
---

# farm-manager 新旧接口兼容矩阵

## 0. 文档目的与判定口径

本文整理 `archive/backend/` 旧后端、`../../business/`、`../../agent/` 当前运行时代码之间的接口差异，作为 v2 补接口、前端迁移和接口文档修订的基准。

判定优先级：

1. 当前运行时代码：`../../business/api/*.py`、`../../agent/api/*.py`；
2. 旧后端实际路由：`archive/backend/app/**/routes.py`；
3. 设计文档：`../../docs/spec/2026-08-05-api-spec.md` 及其他专题 spec。

截至 2026-08-13 的静态盘点结果：

| 范围 | 路由声明数 | 说明 |
|---|---:|---|
| 旧后端 HTTP | 149 | 业务、Agent、管理、数据飞轮、模拟器、探活 |
| v2 Business REST | 84 | 包含同一路由同时支持 `PUT/PATCH` 的声明 |
| v2 Agent HTTP | 13 | 包含 SSE、HITL、Turn、Trace |
| v2 Business MCP | 另计 | MCP 工具不是前端 REST 接口，不混入以下 REST 矩阵 |

状态说明：

| 状态 | 含义 |
|---|---|
| 等价 | 能力和主要字段基本一致，仅前缀或包装变化 |
| 迁移 | v2 已有能力，但路径、方法、查询参数或响应包装变化 |
| 新增 | v2 新增旧版没有的能力 |
| 缺失 | 旧版有能力，v2 当前没有对应 HTTP 路由 |
| 规划漂移 | spec 宣称存在，但当前运行时代码没有；或 spec 路径/字段已过期 |
| 非核心 | 旧版管理、数据飞轮、模拟器等，不属于当前 Business 核心迁移 |

## 1. 服务与协议边界

| 调用关系 | 旧版 | v2 当前 |
|---|---|---|
| 前端 → Business | 单体服务根路径，例如 `/costs`、`/planting/*` | `http://127.0.0.1:9876/api/v2/*` |
| 前端 → Agent | `/agent/*`，JSON 或旧 SSE | `http://127.0.0.1:8000/api/v2/*`，对话为 SSE |
| Agent → Business | 旧版内部 Skill/Service 调用 | `http://127.0.0.1:9876/mcp`，Streamable HTTP MCP |
| 数据隔离 | 旧版通过当前 Farm 对象 | v2 JWT 中的 `user_id/farm_id`，Business 按 farm_id 隔离 |
| 错误 | 多种 `detail` 形态 | Business 目标为 `detail.code/message/meta`；Agent 错误通常包含 `code` |

MCP 工具只供 Agent ReAct/MCP 调用，不能直接作为移动端或 admin-web 的 REST 替代接口。

## 2. 认证、用户与农场

### 2.1 认证与用户接口

| 旧接口 | v2 实际接口 | 请求参数 | v2 响应/差异 | 状态 |
|---|---|---|---|---|
| `POST /auth/register` | `POST /api/v2/auth/register` | JSON：`phone,password,nickname?` | 当前运行时返回 `user_id,phone,nickname,role,farm_id,token`；旧版返回 `access_token,token_type,user` | 迁移；响应不兼容 |
| `POST /auth/login` | `POST /api/v2/auth/login` | JSON：`phone,password` | 同注册响应 | 迁移；响应不兼容 |
| `GET /auth/me` | `GET /api/v2/users/me` | Bearer JWT | `id,phone,nickname,avatar_url,role,status,farm:{id,uid,name,location}` | 路径迁移 |
| `PUT /auth/me` | `PATCH /api/v2/users/me` | JSON：`nickname?,avatar_url?` | 更新后的用户资料 | 方法/路径迁移 |
| `PUT /auth/me/farm-location` | `PATCH /api/v2/farms/{farm_id}/location` | JSON：`location,lat?,lon?` | 农场信息 | 路径迁移 |
| `GET /settings` | `GET /api/v2/users/me/settings` | Bearer JWT | `user_id,default_city,default_lat,default_lon,assistant_role` | 路径迁移 |
| `PUT /settings` | `PATCH /api/v2/users/me/settings` | JSON：上述设置字段，均可选 | 更新后的设置 | 方法/路径迁移 |

当前 v2 认证请求字段：

| 字段 | 旧版约束 | v2 运行时约束 |
|---|---|---|
| `phone` | 中国大陆 11 位 | 注册必须是 11 位数字且以 `1[3-9]` 开头；登录继续兼容 `+` 和 11-20 位 |
| `password` 注册 | 8-64 位 | 6-72 位 |
| `nickname` | 默认“农友”，最长 50 | 默认“农友”，最长 50 |

认证响应需要优先统一。推荐保留标准响应：

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": "<user_id>",
    "phone": "13800138000",
    "nickname": "农友",
    "avatar_url": null,
    "role": "user",
    "status": "active"
  },
  "farm_id": 1
}
```

### 2.2 农场与 Dashboard

| 旧能力/接口 | v2 实际接口 | 请求参数 | 响应主要字段 | 状态 |
|---|---|---|---|---|
| 默认农场快照 | `GET /api/v2/farms/my` | 无 | `farm_id,name,location,today,active_cycles,recent_logs_count,weather,workers_summary,cost_summary` | v2 新增 |
| `GET /farms/{id}`（旧版通过用户上下文间接使用） | `GET /api/v2/farms/{farm_id}` | Path：`farm_id` | `id,uid,name,location,user_id,created_at` | v2 新增 |
| 更新农场名称 | `PATCH /api/v2/farms/{farm_id}` | `name` | `id,uid,name,location` | v2 新增 |
| 更新农场位置 | `PUT /auth/me/farm-location` | `location,lat?,lon?` | 农场信息 | 已迁移 |
| 旧总览能力 | `GET /api/v2/farms/{farm_id}/overview` | Path：`farm_id` | 农场经营快照 | 路径已实现 |
| spec 中的 `/farms/{id}/status` | 无 | Path：`farm_id` | — | 需要修正文档或补兼容路由 |
| 农场首页 | `GET /api/v2/dashboard` | 无 | 农场经营快照 | 等价 |
| 近期农事 | `GET /api/v2/dashboard/recent-operations` | `cycle_id?,days=30,limit=10` | `{items:[...]}` | 迁移 |
| 成本汇总 | `GET /api/v2/dashboard/cost-summary` | `year?` | 年度收支汇总 | v2 新增 |
| 活跃茬口 | `GET /api/v2/dashboard/active-cycles` | 无 | `{items:[...]}` | v2 新增 |
| 未结人工 | `GET /api/v2/dashboard/unsettled-labor` | 无 | 未结人工汇总 | v2 新增 |

## 3. 种植域

### 3.1 作物模板

| 旧接口 | v2 实际接口 | 请求参数 | 响应 | 状态 |
|---|---|---|---|---|
| `GET /crops/templates` | `GET /api/v2/crop-templates` | `page=1,page_size=20` | `{items,total}`，item 含 `id,farm_id,name,variety,category,stages,created_at` | 路径/分页迁移 |
| `POST /crops/templates` | `POST /api/v2/crop-templates` | `name,variety?,category?,stages[]` | 模板详情 + `already_exists` | 等价 |
| `GET /crops/templates/{id}` | `GET /api/v2/crop-templates/{template_id}` | Path：`template_id` | 模板详情 | 迁移 |
| `PUT /crops/templates/{id}` | `PUT/PATCH /api/v2/crop-templates/{template_id}` | 模板字段 | 模板详情 | 迁移 |
| `DELETE /crops/templates/{id}` | `DELETE /api/v2/crop-templates/{template_id}` | Path | `{"deleted": id}` | 迁移 |
| `GET /crops/templates/system` | `GET /api/v2/crop-templates/system/list` | `category?` | `{items}` | 路径迁移 |
| `POST /crops/templates/system` | 无 | `name,variety?,category?,stages[]` | — | 缺失 |
| `PUT /crops/templates/system/{id}` | 无 | 同上 | — | 缺失 |
| `DELETE /crops/templates/system/{id}` | 无 | Path | — | 缺失 |
| `POST /crops/templates/system/{id}/import` | `POST /api/v2/crop-templates/system/{template_id}/import` | Path | `id,already_exists` | 等价 |
| `POST /crops/templates/parse` | 无 | `description` | 模板草稿 | 缺失 |

模板请求字段：

```text
TemplateRequest:
  name: string
  variety?: string
  category?: string
  stages: StageRequest[]

StageRequest:
  name: string
  duration_days: integer
  order_index: integer
  key_tasks?: string
```

### 3.2 茬口

| 旧接口 | v2 实际接口 | 请求参数 | 响应主要字段 | 状态 |
|---|---|---|---|---|
| `GET /cycles` | `GET /api/v2/crop-cycles` | `status?,page=1,page_size=20` | `{items,total}` | 路径迁移 |
| `POST /cycles` | `POST /api/v2/crop-cycles` | `name,crop_template_id,start_date,field_name?,total_area_mu?,season?,batch_note?` | 完整茬口 | 等价 |
| `GET /cycles/{id}` | `GET /api/v2/crop-cycles/{cycle_id}` | Path | 完整茬口 + `stages` | 路径迁移 |
| `PUT /cycles/{id}` | `PUT/PATCH /api/v2/crop-cycles/{cycle_id}` | 更新字段 | 完整茬口 | 迁移 |
| `DELETE /cycles/{id}` | `DELETE /api/v2/crop-cycles/{cycle_id}` | Path | `{"deleted": id}` | 迁移 |
| `POST /cycles/{id}/advance-stage` | 同路径 | Path | 更新后的完整茬口 | 等价 |
| `POST /cycles/parse` | 无 | `description` | 茬口草稿 | 缺失 |

v2 茬口响应字段：`id,farm_id,name,crop_template_id,start_date,field_name,total_area_mu,season,batch_note,status,created_at,stages,current_stage_name`。

spec 中的 `unit_count`、`unit_area_mu` 当前没有由 `cycle_service` 直接序列化返回，应修正文档或补字段。

### 3.3 种植单元

| 旧接口 | v2 实际接口 | 请求参数 | 响应 | 状态 |
|---|---|---|---|---|
| `GET /planting/units` | `GET /api/v2/planting-units` | `cycle_id?` | `{items,total}` | 路径/包装迁移 |
| `POST /planting/units` | `POST /api/v2/planting-units` | `cycle_id,name,area_mu?,planted_date?,status?,note?` | 单元详情 | 等价 |
| `PUT /planting/units/{id}` | `PUT/PATCH /api/v2/planting-units/{unit_id}` | `name?,area_mu?,planted_date?,status?,note?` | 单元详情 | 迁移 |
| `DELETE /planting/units/{id}` | `DELETE /api/v2/planting-units/{unit_id}` | Path | `{"deleted": id}` | 迁移 |

响应字段：`id,farm_id,cycle_id,name,area_mu,planted_date,status,note,created_at`。

### 3.4 农事日志

| 旧接口 | v2 实际接口 | 请求参数 | 响应 | 状态 |
|---|---|---|---|---|
| `GET /logs` | `GET /api/v2/farm-logs` | `cycle_id?,operation_type?,start_date?,end_date?,page?,page_size?` | `{items,total}` | 路径/过滤器迁移 |
| `POST /logs` | `POST /api/v2/farm-logs` | `cycle_id,operation_type,operation_date?,note?,worker_names[]` | 日志详情 | 参数收窄 |
| `PUT /logs/{id}` | `PUT/PATCH /api/v2/farm-logs/{log_id}` | 更新字段 | 日志详情 | 迁移 |
| `DELETE /logs/{id}` | `DELETE /api/v2/farm-logs/{log_id}` | Path | `{"deleted": id}` | 迁移 |
| 无 | `GET /api/v2/farm-logs/{log_id}` | Path | 日志详情 | v2 新增 |
| `GET /planting/operation-types` | `GET /api/v2/farm-logs/operations/types` | `crop_name?` | `{items}` | v2 新增/路径迁移 |

旧版还支持 `work_order_id,operation_time,photo_urls,worker_ids`；v2 当前创建/更新请求没有这些字段。若前端仍使用，必须补 v2 字段或明确废弃。

### 3.5 工人

| 旧接口 | v2 实际接口 | 请求参数 | 响应 | 状态 |
|---|---|---|---|---|
| `GET /planting/workers` | `GET /api/v2/workers` | `active_only=false` | `{items,total}` | 路径/包装迁移 |
| `POST /planting/workers` | `POST /api/v2/workers` | `name,phone?,default_pay_type?,default_unit_price?,note?` | 工人详情 | 等价 |
| `GET /planting/workers/summary` | `GET /api/v2/workers/summary` | `active_only=false` | `{items,total}` | 等价 |
| `PUT /planting/workers/{id}` | `PUT/PATCH /api/v2/workers/{worker_id}` | 工人更新字段 | 工人详情 | 迁移 |
| `DELETE /planting/workers/{id}` | `DELETE /api/v2/workers/{worker_id}` | Path | 停用后的工人 | 迁移 |

v2 工人字段：`id,farm_id,name,phone,default_pay_type,default_unit_price,note,status,created_at`。spec 中的 `role,pay_type,pay_rate` 已过期。

### 3.6 工单、工资与近期农事

| 旧接口 | v2 实际接口 | 请求参数 | 响应 | 状态 |
|---|---|---|---|---|
| `POST /planting/work-orders` | `POST /api/v2/work-orders` | `operation_type,operation_date,cycle_id?,scope_type?,unit_ids[],labor_entries[],note?,photo_urls?` | 工单详情 | 等价 |
| `GET /planting/work-orders` | `GET /api/v2/work-orders` | `cycle_id?,page?,page_size?` | `{items,total}` | 路径/分页迁移 |
| `GET /planting/work-orders/{id}` | `GET /api/v2/work-orders/{order_id}` | Path | 工单详情 | 等价 |
| 无 | `PUT/PATCH /api/v2/work-orders/{order_id}` | 工单更新字段 | 工单详情 | v2 新增 |
| 无 | `POST /api/v2/work-orders/{order_id}/settle` | `amount?,worker_name?,cycle_id?,start_date?,end_date?` | `paid_amount,total_unpaid_before,workers` 等 | v2 新增 |
| `POST /planting/labor/wages` | `POST /api/v2/labor/wages` | `worker_id?/worker_name?,cycle_id,operation_type,work_date,pay_type?,quantity?,unit_price?,payable_amount?,paid_amount?,note?,client_request_id?` | 工资记录 + `cost_record_id` | 迁移 |
| `PATCH /planting/labor/wages/{id}` | `PATCH /api/v2/labor/wages/{labor_entry_id}` | 工资更新字段 | 工资记录 | 等价 |
| `GET /planting/labor/unsettled-summary` | `GET /api/v2/labor/unsettled-summary` | 无 | `total_unpaid,workers[]` | 迁移 |
| 无 | `GET /api/v2/labor/wages` | `mode=unpaid\|monthly\|worker`；`worker_name?,month?,start_date?,end_date?` | 按模式返回工资汇总/明细 | v2 新增 |
| `GET /planting/recent-operations` | `GET /api/v2/recent-operations` | `cycle_id?,days=30,limit=20` | `{items}` | 路径/包装迁移 |
| `GET /planting/operation-types` | `GET /api/v2/operation-types` | `crop_name?` | `{items}` | 路径/包装迁移 |

工单响应字段：`id,farm_id,cycle_id,cycle_name,operation_type,operation_date,scope_type,unit_ids,unit_names,note,photo_urls,labor_entries,labor_cost_record_id,total_payable_amount,total_paid_amount,total_unpaid_amount,created_at`。

工资查询响应按 `mode` 区分：

```text
unpaid:  summary{total_unpaid,worker_count}, workers[]
monthly: month, summary{total_payable,total_paid,total_unpaid,worker_count}, workers[]
worker:  worker_name,date_range, summary{entry_count,total_payable,total_paid,total_unpaid}, entries[]
```

## 4. 财务域

### 4.1 成本分类与成本记录

| 旧接口 | v2 实际接口 | 请求参数 | 响应 | 状态 |
|---|---|---|---|---|
| `GET /cost-categories` | `GET /api/v2/cost-categories` | 无 | `{items:[id,farm_id,name,type,icon,sort_order,is_default]}` | 迁移 |
| `POST /cost-categories` | `POST /api/v2/cost-categories` | `name,type,icon?,sort_order?` | 分类详情 | 等价 |
| 无 | `PUT/PATCH /api/v2/cost-categories/{id}` | `name?,type?,icon?,sort_order?` | 分类详情 | v2 新增 |
| `DELETE /cost-categories/{id}` | `DELETE /api/v2/cost-categories/{category_id}` | Path | `{"deleted": id}` | 迁移 |
| `GET /costs` | `GET /api/v2/cost-records` | `cycle_id?,record_type?,category?,source_type?,source_id?,date_from?,date_to?,page?,page_size?` | `{items,total}` | 路径/过滤器迁移 |
| `POST /costs` | `POST /api/v2/cost-records` | `record_type,category,amount,record_date,cycle_id?,settled_amount?,note?,record_subtype?,counterparty?,due_date?,source_type?,source_id?` | 成本记录 | 等价 |
| 无 | `PUT/PATCH /api/v2/cost-records/{id}` | 成本更新字段 | 成本记录 | v2 已实现 |
| `DELETE /costs/{id}` | `DELETE /api/v2/cost-records/{record_id}` | Path | 删除后的记录 | 迁移 |
| `GET /costs/cycles/{id}/profit` | `GET /api/v2/cost-records/cycles/{cycle_id}/profit` | Path | `cycle_id,total_cost,total_income,net_profit,settled_*,unsettled_*,labor_*` | 迁移 |
| `GET /costs/summary/{year}` | `GET /api/v2/cost-records/summary/yearly?year=` | Query：`year` | `year,total_cost,total_income,net_profit,by_category,...` | 路径迁移 |
| `POST /costs/parse` | 无 | `description` | 成本草稿 | 缺失 |

成本记录响应主要字段：`id,farm_id,cycle_id,record_type,category,category_id,amount,settled_amount,unsettled_amount,settlement_status,record_date,recorded_at,note,record_subtype,counterparty,due_date,settled_at,parent_record_id,source_type,source_id,created_at`。

说明：旧缺口文档中“`PUT /cost-records/{id}`、`PUT /cost-categories/{id}` 尚未实现”的结论已过期；当前 v2 代码和 Service 均已存在这两组接口。

### 4.2 债务

| 旧接口 | v2 实际接口 | 请求参数 | 响应 | 状态 |
|---|---|---|---|---|
| `POST /debts` | `POST /api/v2/debts` | `counterparty,amount,record_date,due_date?,note?,cycle_id?,record_type?,category?` | 成本记录 | 等价 |
| `GET /debts` | `GET /api/v2/debts` | `counterparty?,page?,page_size?` | `{items,total,summary}` | 迁移 |
| `POST /debts/settle` | `POST /api/v2/debts/settle` | `counterparty,amount?,note?` | 结算后的成本记录 | 等价 |
| 无 | `GET /api/v2/debts/summary` | 无 | `{items:[counterparty,total_debt,total_settled,remaining,record_count]}` | v2 新增 |

## 5. 天气与位置

| 旧接口 | v2 实际接口 | 请求参数 | 响应/差异 | 状态 |
|---|---|---|---|---|
| `GET /weather/forecast` | `GET /api/v2/weather` | `location?,days=3,lat?,lon?` | v2 天气预报 + 预警；旧默认 `days=7` | 路径/默认值迁移 |
| 无 | `GET /api/v2/weather/now` | `location?,lat?,lon?` | 单日/实时天气 | v2 新增 |
| `GET /locations/search?q=&limit=20` | `GET /api/v2/locations/search?keyword=&limit=10` | `q` 改为 `keyword` | 旧：`items,total`；v2：`items` | 参数/响应迁移 |
| `GET /locations/meta` | 无 | 无 | — | 缺失 |
| `GET /locations/regions` | 无 | `province?,city?` | — | 缺失 |
| 无 | `GET /api/v2/locations/coords?city=` | `city` | `city,latitude,longitude,found` | v2 新增 |

旧版天气允许无 Authorization 兼容访问；v2 Business 天气路由当前要求 JWT。显式未知地点不能静默套用默认坐标，Agent 应收到 `unknown_location` 后调用城市搜索重试。

## 6. Agent HTTP、SSE、HITL 与 Trace

### 6.1 旧 Agent 与 v2 Agent 对照

| 旧接口 | v2 实际接口 | 请求参数 | 响应/协议 | 状态 |
|---|---|---|---|---|
| `GET /agent/skills` | 无 | 无 | 技能列表 | 缺失 |
| `POST /agent/chat` | `POST /api/v2/chat` | 旧：`cycle_id?,message,session_id?,simulate_user_id?`；v2：`message,conversation_id?,client_request_id?` | 旧 JSON `reply,pending_action,pending_plan`；v2 SSE | 协议重构 |
| `POST /agent/chat/stream` | `POST /api/v2/chat` | `after_seq?` | `text/event-stream`，事件带 `type,data,seq` | 合并 |
| `GET /agent/conversations` | `GET /api/v2/conversations` | `limit=20,cursor?` | 分页会话对象 | 响应迁移 |
| `GET /agent/conversations/{id}/messages` | `GET /api/v2/conversations/{conversation_id}/messages` | `limit=100,cursor?` | 规范历史消息分页；旧 v2 详情接口继续兼容 `before?` | 路径/分页契约迁移 |
| `GET /agent/conversations/{id}/turns` | `GET /api/v2/conversations/{conversation_id}/turns` | `limit=50,cursor?` | 会话 Turn 摘要和执行证据状态 | v2 新增 |
| `GET /agent/conversations/{id}/turns/{turn_id}` | `GET /api/v2/conversations/{conversation_id}/turns/{turn_id}` | `include_payload?` | Turn/Trace 聚合详情；普通用户默认公开投影 | v2 新增 |
| `GET /agent/conversations/{id}/debug-export` | 无 | Path | — | 缺失 |
| `GET /agent/daily` | 无 | `cycle_id?` | 每日建议 | 缺失 |
| `POST /agent/daily/refresh` | 无 | `cycle_id?` | 每日建议 | 缺失 |
| `POST /agent/report` | 无 | `cycle_id?,report_type?` | 报告 | 缺失 |
| `GET /agent/advice-history` | 无 | `cycle_id?,limit?` | 建议历史 | 缺失 |
| `GET /agent/report-history` | 无 | `cycle_id?,limit?` | 报告历史 | 缺失 |
| `GET /agent/reports` | 无 | `page?,size?` | 报告分页 | 缺失 |
| `DELETE /agent/reports/{id}` | 无 | Path | — | 缺失 |
| `POST /agent/feedback` | 无 | Feedback body | 反馈结果 | 缺失 |
| `GET /agent/feedback/stats` | 无 | 无 | 统计 | 缺失 |

### 6.2 v2 新增 Agent 接口

| 接口 | 请求参数 | 响应 |
|---|---|---|
| `POST /api/v2/approve` | `turn_id,decision,reason?` | `{ok,turn_id,decision}` |
| `POST /api/v2/reset` | `conversation_id?` | `{ok,conversation_id}` |
| `GET /api/v2/turns/{turn_id}` | Path | turn 状态、审批状态、错误状态 |
| `GET /api/v2/turns/{turn_id}/events` | `after_seq=0` | 可重放 SSE |
| `POST /api/v2/turns/{turn_id}/cancel` | Path | `{ok,turn_id,status}` |
| `GET /api/v2/traces` | `conversation_id?,limit=20,cursor?` | Trace 请求列表 |
| `GET /api/v2/traces/{request_id}` | `limit=200` | Trace 节点 |
| `GET /api/v2/traces/{request_id}/summary` | Path | Trace 聚合摘要 |
| `GET /api/v2/health` | 无 | Agent、Redis、turn 状态 |
| `GET /api/v2/dev-users` | 无 | 仅返回 `status=active` 且 `role=dev` 的开发用户和 JWT，仅开发环境能力；生产环境 404 |

### 6.3 `/chat` SSE 关键事件

客户端至少应处理：`queued`、`accepted`、`meta`、`tool_call`、`tool_result`、`approval_required`、`operation_committed`、`write_committed_reply_failed`、`final_answer`、`error`、`done`。

Trace/SSE 的正式字段、状态机、接口命名和整段/单轮召回方式，以
[`2026-08-18-agent-trace-observability-and-recall-design.md`](./2026-08-18-agent-trace-observability-and-recall-design.md)
为准。当前 `/api/v2/traces/{request_id}` 是兼容入口，目标命名使用
`/api/v2/traces/{trace_id}/nodes`、`events` 和 `timeline`。

`client_request_id` 用于重试幂等；`after_seq` 用于断线后从 Redis 事件流继续消费。HITL 审批必须调用 `/approve`，不能仅依据自然语言回复判断写入成功。

## 7. 旧版非核心接口完整清单

以下接口在旧版存在，但当前 v2 没有等价 REST 路由。是否补充取决于 admin-web、运营后台和测试工具是否继续使用。

### 7.1 管理与运营

```text
GET/POST       /admin/users
GET            /admin/users/{user_id}
GET/PUT        /admin/users/{user_id}/quota
PUT            /admin/users/{user_id}/status
PUT            /admin/users/quota/batch
GET            /admin/users/quota-overview

GET            /admin/dashboard/summary
GET            /admin/dashboard/trend?days=
GET            /admin/dashboard/active-users

GET            /admin/stats/tokens
GET            /admin/stats/tokens/daily
GET            /admin/stats/tokens/hourly

GET            /admin/skills
POST           /admin/skills/route-recall
GET            /admin/skills/route-recall/dataset
POST           /admin/skills/route-recall/evaluate
PUT            /admin/skills/{skill_name}/enabled
GET            /admin/prompts
GET            /admin/config
POST           /admin/cache/clear
POST           /admin/prompts/reload

GET            /admin/guardrails-logs
```

### 7.2 Trace、数据飞轮、模拟器和版本

```text
GET            /admin/traces
GET            /admin/traces/requests
GET            /admin/traces/{request_id}/timeline
GET            /admin/traces/{request_id}/diagnostics
GET            /admin/traces/{request_id}/nodes/{node_id}
DELETE         /admin/traces?before=YYYY-MM-DD

GET/POST       /admin/data-flywheel/samples*
GET/POST       /admin/data-flywheel/sessions*
POST           /admin/data-flywheel/sync-sessions
GET            /admin/data-flywheel/sync-sessions/{job_id}
POST           /admin/data-flywheel/prelabels/batch
GET            /admin/data-flywheel/prelabels/batch/{job_id}
POST/DELETE    /admin/data-flywheel/samples/{sample_id}/labels*
POST           /admin/data-flywheel/samples/{sample_id}/prelabel
POST           /admin/data-flywheel/samples/{sample_id}/case-draft
GET/POST       /admin/data-flywheel/repair-candidates
GET/POST       /admin/data-flywheel/repair-packs*
GET/POST       /admin/data-flywheel/review-issue-chains*
GET            /admin/data-flywheel/daily-review/inbox

GET            /simulation/cases
POST           /simulation/run
GET            /simulation/run/{run_id}
GET            /simulation/runs
GET            /simulation/reports/{run_id}

GET            /api/app/version?current_version_code=
```

Trace 不能简单按 URL 对照：旧版是管理员查询接口，v2 `/traces/*` 是 Agent 侧按会话/请求查询的 Trace 能力，鉴权范围和响应结构均不等价。

## 8. Smart Fill 与 MCP 边界

旧版有：

```text
GET  /smart-fill/scenarios
POST /smart-fill/parse
POST /costs/parse
POST /crops/templates/parse
POST /cycles/parse
```

当前 v2 Business 没有 `smart-fill` REST 路由；当前 v2 Agent/Business 内部存在部分 MCP/Skill 解析能力，但不能直接视为前端 REST 已实现。

建议补充：

```text
GET  /api/v2/smart-fill/scenarios
POST /api/v2/smart-fill/parse
```

统一请求：`scene,text,context?`；统一响应：`scene,draft,missing_fields,warnings,trace_id?`。建议场景：`ledger.record`、`crop.template`、`crop.cycle`、`planting.unit`。

## 9. v2 需要补充或明确决策的接口

### P0：影响主链路

| 项目 | 建议 |
|---|---|
| 认证响应 | 统一为 `{access_token,token_type,user,farm_id}`，或提供兼容解析并同步所有客户端 |
| Smart Fill | 补 `/smart-fill/scenarios`、`/smart-fill/parse`，或明确所有旧 `/parse` 接口废弃 |
| 系统模板管理员 CRUD | 补 `POST/PUT/DELETE /crop-templates/system*` 路由；Service 能力已存在 |
| 位置目录 | 补 `/locations/meta`、`/locations/regions`，或正式标记 unavailable |
| 农场状态路径 | 统一 `/farms/{id}/overview` 与 spec 中的 `/farms/{id}/status` |

### P1：前端功能完整性

| 项目 | 建议 |
|---|---|
| Agent 技能展示 | 补 `/api/v2/agent/skills` 或前端改为本地能力清单 |
| 每日建议/报告 | 明确是否迁移 `/daily*`、`/report*`、历史接口 |
| Agent 反馈 | 明确是否迁移 `/feedback`、`/feedback/stats` |
| 农事日志字段 | 决定是否补 `work_order_id,operation_time,photo_urls,worker_ids` |
| 作物/茬口解析 | 接入统一 Smart Fill |

### P2：管理和运维

按实际用户补充：

```text
/admin/users/*
/admin/dashboard/*
/admin/stats/*
/admin/skills/*
/admin/prompts
/admin/config
/admin/traces/*
/admin/data-flywheel/*
/simulation/*
/api/app/version
```

## 10. 前端迁移速查

| 旧路径/字段 | v2 路径/字段 |
|---|---|
| `/costs/*` | `/cost-records/*` |
| `/planting/units/*` | `/planting-units/*` |
| `/planting/workers/*` | `/workers/*` |
| `/planting/work-orders/*` | `/work-orders/*` |
| `/planting/labor/*` | `/labor/*` |
| `/logs/*` | `/farm-logs/*` |
| `/cycles/*` | `/crop-cycles/*` |
| `/crops/templates/*` | `/crop-templates/*` |
| `/auth/me` | `/users/me` |
| `/settings` | `/users/me/settings` |
| `q` | `keyword` |
| `size` | `page_size` |
| 裸数组 | 通常改为 `{items,total}` 或 `{items}` |
| Agent JSON chat | Agent SSE + Turn + `/approve` |
| 旧 `access_token/user` | 当前 v2 扁平 `token/user_id/farm_id`，需统一 |

## 11. 关联文档与维护要求

- 总体接口设计：[2026-08-05-api-spec.md](./2026-08-05-api-spec.md)
- admin-web 缺口分析：[2026-08-11-admin-web-api-gap-analysis.md](./2026-08-11-admin-web-api-gap-analysis.md)
- Agent 并发与 SSE：[2026-08-12-agent-chat-concurrency-harness.md](./2026-08-12-agent-chat-concurrency-harness.md)
- 旧版路由入口：`archive/backend/app/bootstrap/routes.py`
- v2 Business 路由入口：`../../business/api/__init__.py`
- v2 Agent 路由入口：`../../agent/api/__init__.py`

每次新增或修改 v2 HTTP 路由时，应同步更新：

1. 本矩阵中的旧接口映射、请求字段、响应字段和状态；
2. 总体接口 spec 的路径与示例；
3. admin-web 缺口分析中的待补清单；
4. 对应 API contract/集成测试。

## 12. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-08-13 | 首次建立旧版 149 条、v2 Business 84 条、v2 Agent 13 条 HTTP 路由的兼容矩阵；记录运行时代码与 2026-08-05 spec 的路径、字段和能力漂移。 |
