---
last_updated: 2026-08-13
status: draft
---

# admin-web 接入接口缺口分析

> Spec ID: 2026-08-11-admin-web-api-gap-analysis
> 状态: draft
> 关联矩阵：[2026-08-13-api-compatibility-matrix.md](./2026-08-13-api-compatibility-matrix.md)
> 目标: 梳理 admin-web 前端预期调用的 REST 接口与 v2 business 实际提供的接口间的差异，
>       标注哪些必须后端补齐、哪些可通过协调 admin-web 复用现有接口或调整调用方式。

> **运行时复核说明（2026-08-13）**：本文件的历史分析以 2026-08-11 快照为基础；当前运行时代码优先以关联矩阵为准。`PUT/PATCH /cost-records/{id}`、`PUT/PATCH /cost-categories/{id}` 和 `GET /labor/wages` 当前均已存在，不再作为待补接口。

## 0. 背景

### 0.1 两端现状

**admin-web（前端）** —— `admin-web/src/api/*.ts` 定义了一套 REST 客户端，主要路径：

| 模块 | 前端调用前缀 | 说明 |
|------|-------------|------|
| costs | `/costs`、`/cost-categories` | 成本记录 CRUD + AI 解析 + 分类 |
| operations | `/planting/*` | 种植域（单元、工人、作业单、工时工资、近期农事、作业类型、债务） |
| dashboard | `/dashboard`、`/admin/dashboard/*` | 农场总览、管理员仪表板 |
| users | `/users/*`、`/admin/users/*` | 用户资料、管理员用户管理 |
| crops / cycles | `/crop-templates/*`、`/crop-cycles/*` | 作物模板、茬口 |
| logs | `/farm-logs/*` | 农事日志 |
| smartFill | `/smart-fill/parse` | AI 智能解析 |
| weather / locations | `/weather`、`/locations/*` | 天气、位置 |
| agent | `/agent/*` | Agent 反馈、配置 |

**v2 business（后端）** —— `v2/business/api/*.py` 按 DDD 业务域组织，实际暴露路径：

| 模块 | 后端前缀 | 说明 |
|------|---------|------|
| costs | `/cost-records/*`、`/cost-categories/*` | 成本记录（注意不是 `/costs/*`） |
| work_orders | `/work-orders/*`、`/planting-units/*`、`/labor/*`、`/recent-operations`、`/operation-types` | 种植域被拆成多个子前缀 |
| workers | `/workers/*` | 工人档案（注意不是 `/planting/workers/*`） |
| dashboard | `/dashboard/*` | 农场仪表板（不含 `/admin/dashboard/*`） |
| users | `/users/me*`、`/admin/users/*` | 用户资料 + 管理员用户管理 |

### 0.2 差异根因

1. **路径前缀差异**：admin-web 沿用旧版 `/costs`、`/planting/*`、`/planting/workers` 聚合路径；v2 按 DDD 拆分成 `/cost-records`、`/workers`、`/work-orders` 等更细粒度的资源。
2. **缺失 Service 方法**：部分 REST 路由需要后端 Service 层提供对应实现（如 `cost_service.update_record`、`cost_category_service.update_category`），当前还未实现。
3. **新增业务能力**：工资查询、结算、管理端统计等功能在 spec 中已经定义，但尚未落成 HTTP 路由。
4. **AI 解析路径变化**：v2 用 `/smart-fill/parse` 统一承接（scene 化），admin-web 仍按旧路径 `/costs/parse`、`/crop-templates/parse`、`/crop-cycles/parse` 调用。

## 1. 接口缺口分类

按处理策略分成四类：

| 类别 | 含义 | 责任方 |
|------|------|--------|
| **A. 路径映射（纯协调）** | 后端已有等价接口，仅前端路径不对 | admin-web 修改调用 |
| **B. 参数/响应协调** | 后端结构已就绪，但字段/过滤项/聚合方式需前端微调 | 双方协调 |
| **C. 后端补齐 Service** | Service 方法缺失，路由已存在或容易添加 | business 补齐 |
| **D. 后端新增路由+Service** | 需要完整新增一条业务能力（新路由 + 可能新 Service 方法） | business 新增 |
| **E. 暂不实现** | admin-web 实际没用到，或用现有接口可组合代替 | 暂缓 |

## 2. 逐项缺口分析

### 2.1 成本/收入记录 (`/costs*` vs `/cost-records*`)

| # | admin-web 调用 | v2 现状 | 分类 | 处理 |
|---|---------------|--------|------|------|
| 1 | `GET  /costs` (listRecords) | `GET /cost-records` 已在 `records_router` | **A** | admin-web 改为 `/cost-records` |
| 2 | `POST /costs` (createRecord) | `POST /cost-records` 已存在 | **A** | admin-web 改为 `/cost-records` |
| 3 | `PUT  /costs/{id}` (updateRecord) | `PUT/PATCH /cost-records/{id}` 已存在 | **A** | admin-web 改为 `/cost-records/{id}` |
| 4 | `DELETE /costs/{id}` (deleteRecord) | `DELETE /cost-records/{id}` 已存在 | **A** | admin-web 改为 `/cost-records` |
| 5 | `GET /costs/cycles/{id}/profit` | `GET /cost-records/cycles/{id}/profit` 已存在 | **A** | admin-web 改为 `/cost-records/...` |
| 6 | `GET /costs/summary/{year}` (getYearlySummary) | `GET /cost-records/summary/yearly?year=` 已存在 | **B** | admin-web 改为 `/cost-records/summary/yearly?year=` |
| 7 | `POST /costs/parse` (parseCostRecord) | **无**，只有统一 `POST /smart-fill/parse`（scene=`ledger.record`） | **A** | admin-web 改调 `/smart-fill/parse` 并传 `scene="ledger.record"` |
| 8 | `GET /cost-categories` | 已存在 | — | 无需调整 |
| 9 | `POST /cost-categories` | 已存在 | — | 无需调整 |
| 10 | `DELETE /cost-categories/{id}` | 已存在 | — | 无需调整 |
| 11 | `PUT /cost-categories/{id}` | `PUT/PATCH /cost-categories/{id}` 已存在 | **A** | admin-web 保持资源路径并适配 v2 响应 |

### 2.2 种植域（单元/工人/作业单/工时）

| # | admin-web 调用 | v2 现状 | 分类 | 处理 |
|---|---------------|--------|------|------|
| 12 | `GET  /planting/units` | `GET /planting-units` 已存在（operations_router） | **A** | admin-web 改路径 |
| 13 | `POST /planting/units` | `POST /planting-units` 已存在 | **A** | admin-web 改路径 |
| 14 | `PUT  /planting/units/{id}` | `PUT /planting-units/{id}` 已存在 | **A** | admin-web 改路径 |
| 15 | `DELETE /planting/units/{id}` | `DELETE /planting-units/{id}` 已存在 | **A** | admin-web 改路径 |
| 16 | `GET  /planting/workers` | `GET /workers` 已存在 | **A** | admin-web 改路径 |
| 17 | `GET  /planting/workers/summary` | `GET /workers/summary` 已存在 | **A** | admin-web 改路径 |
| 18 | `POST /planting/workers` | `POST /workers` 已存在 | **A** | admin-web 改路径 |
| 19 | `PUT  /planting/workers/{id}` | `PUT /workers/{id}` 已存在 | **A** | admin-web 改路径 |
| 20 | `DELETE /planting/workers/{id}` | `DELETE /workers/{id}` 已存在 | **A** | admin-web 改路径 |
| 21 | `GET  /planting/operation-types` | `GET /operation-types` 已存在 | **A** | admin-web 改路径 |
| 22 | `GET  /planting/work-orders` | `GET /work-orders` 已存在 | **A** | admin-web 改路径 |
| 23 | `GET  /planting/work-orders/{id}` | `GET /work-orders/{id}` 已存在 | **A** | admin-web 改路径 |
| 24 | `POST /planting/work-orders` | `POST /work-orders` 已存在 | **A** | admin-web 改路径 |
| 25 | `POST /planting/work-orders/{id}/settle`（结算） | `POST /work-orders/{id}/settle` 已存在 | **A** | admin-web 改路径 |
| 26 | `GET  /planting/recent-operations` | `GET /recent-operations` 已存在 | **A** | admin-web 改路径 |
| 27 | `GET  /planting/labor/unsettled-summary` | `GET /labor/unsettled-summary` 已存在 | **A** | admin-web 改路径 |
| 28 | `POST /planting/labor/wages` | `POST /labor/wages` 已存在 | **A** | admin-web 改路径 |
| 29 | `PUT  /planting/labor/wages/{id}`（admin-web 未直接使用） | `PATCH /labor/wages/{id}` 已存在 | **E** | admin-web 暂无调用，保持 PATCH 即可 |
| 30 | **工资查询**：按未结/按月/按工人查询（spec 需求） | `labor_service.query_wages()` 已实现，但未暴露 HTTP 路由 | **D** | 后端新增 `GET /labor/wages?mode=unpaid\|monthly\|worker&...` 路由 |

### 2.3 债务

| # | admin-web 调用 | v2 现状 | 分类 | 处理 |
|---|---------------|--------|------|------|
| 31 | `GET  /debts` | 已存在（`debts.router`） | — | 无需调整 |
| 32 | `POST /debts` | 已存在 | — | 无需调整 |
| 33 | `POST /debts/settle` | 已存在 | — | 无需调整 |

### 2.4 Dashboard / 仪表板

| # | admin-web 调用 | v2 现状 | 分类 | 处理 |
|---|---------------|--------|------|------|
| 34 | `GET  /dashboard` | 已存在（`dashboard.router`） | — | 无需调整 |
| 35 | `GET  /dashboard/recent-operations` | 已存在 | — | 无需调整 |
| 36 | `GET  /dashboard/cost-summary` | 已存在 | — | 无需调整 |
| 37 | `GET  /dashboard/active-cycles` | 已存在 | — | 无需调整 |
| 38 | `GET  /dashboard/unsettled-labor` | 已存在 | — | 无需调整 |
| 39 | `GET  /admin/dashboard/summary` | **无**，无对应 admin 仪表板 Service | **E** | admin-web 暂用普通 `/dashboard` 或后续新增 |
| 40 | `GET  /admin/dashboard/trend?days=` | **无** | **E** | 同上 |
| 41 | `GET  /admin/dashboard/active-users` | **无** | **E** | 同上 |

### 2.5 其他

| # | admin-web 调用 | v2 现状 | 分类 | 处理 |
|---|---------------|--------|------|------|
| 42 | `GET/PUT /users/settings` | `GET /users/me/settings`、`PATCH /users/me/settings` 已存在 | **A** | admin-web 改路径 |
| 43 | `GET  /agent/feedback/stats` | **无** | **E** | agent 反馈统计不属于本轮 |
| 44 | `GET  /api/app/version` | **无**，移动端版本检查 | **E** | admin-web 未真实依赖 |
| 45 | `POST /crop-templates/parse` | **无**；AI 解析已迁移到 `/smart-fill/parse` scene=`crop.template` | **A** | admin-web 改路径 |
| 46 | `POST /crop-cycles/parse` | **无**；应走 `/smart-fill/parse` scene=`crop.cycle` | **A** | admin-web 改路径 |

## 3. 结论与建议

### 3.1 真实需要后端新增的接口（C+D 合计 3 条）

按优先级排序：

| 优先级 | 接口 | 类型 | 工作量 | 理由 |
|--------|------|------|--------|------|
| **已完成** | `PUT/PATCH /cost-records/{id}` | v2 已实现 | — | 当前代码已有 `cost_service.update_record` 与 REST 路由。 |
| **已完成** | `PUT/PATCH /cost-categories/{id}` | v2 已实现 | — | 当前代码已有 `cost_category_service.update_category` 与 REST 路由。 |
| **已完成** | `GET /labor/wages?mode=...` | v2 已实现 | — | 当前代码已有 `labor_service.query_wages` 与 REST 路由。 |

> 说明：上述三项在历史版本中曾被判断为后端缺口，但截至 2026-08-13 已由运行时代码补齐；当前真正缺口以关联矩阵第 9 节为准。

### 3.2 协调 admin-web 可立即生效（A+B，约 30 条）

| 策略 | 数量 | 示例 |
|------|------|------|
| 仅改路径前缀 | 22 | `/costs/*` → `/cost-records/*`、`/planting/workers/*` → `/workers/*`、`/planting/units/*` → `/planting-units/*` |
| 换统一解析入口 | 3 | `/costs/parse`、`/crop-templates/parse`、`/crop-cycles/parse` → `/smart-fill/parse?scene=` |
| 微调 URL + Query | 2 | `/costs/summary/{year}` → `/cost-records/summary/yearly?year=`、`/users/settings` → `/users/me/settings` |
| 支持用已有接口替代 | 3 | 工资 `PUT` 改用 `PATCH`、管理端仪表盘用普通 `dashboard` 聚合、债务接口保持不变 |

建议由 admin-web 侧按"路径前缀"批量替换：
- `s|/costs(?!/parse$)(?!/summary)(?!/cycles)(?!/categories)(?!/records)|/cost-records|g`（语义上替换成本记录的路径）
- `s|/planting/workers|/workers|g`
- `s|/planting/|/|g`（子路由已拆分到顶层，去除 `planting` 前缀）

### 3.3 暂缓实现的接口（E）

- `/admin/dashboard/*`：管理员仪表板当前 admin-web 尚无实际页面支撑，可后续与管理员运营模块一起规划。
- `/agent/feedback/stats`、`/api/app/version`：非核心业务，可延后或改为前端本地实现。
- `PUT /labor/wages/{id}`：admin-web 暂未使用，保持现有 `PATCH` 语义不变。

## 4. 实施顺序建议

| 阶段 | 工作内容 | 责任方 | 预计工时 |
|------|---------|--------|---------|
| **S0** | admin-web 批量调整路径前缀（A+B 全量约 30 条） | 前端 | 0.5 天 |
| **S1** | 后端补齐 `cost_service.update_record` + 路由（P0-1） | 后端 | 0.5 天 |
| **S2** | 后端补齐 `cost_category_service.update_category` + 路由（P0-2） | 后端 | 0.5 天 |
| **S3** | 后端新增 `GET /labor/wages` 查询路由，复用 `labor_service.query_wages`（P1） | 后端 | 0.5 天 |
| **S4** | 端到端联调 + 修复 admin-web 类型定义（`CostRecord` 等 TS 接口对齐） | 双方 | 0.5 天 |

**合计**：后端 1.5 人日、前端 1.0 人日，即可打通 admin-web 接入主链路。

## 5. 风险与开放问题

1. **路径别名的取舍**：是否在后端保留 `/costs/*`、`/planting/*` 兼容路由？
   - 建议：**不保留**。v2 已按 DDD 重构，保留兼容路径会延续技术债，且 admin-web 迁移成本仅 0.5 天。

2. **`/costs/summary/{year}` 路径语义**：v2 用 query 参数而不是路径参数，admin-web 侧需配合调整 URL 构造。

3. **管理端仪表盘 `/admin/dashboard/*`**：目前属于 admin-web 专属需求，不在普通业务域边界内。建议单独建 `admin_service`，不要塞进 `dashboard.router`。

4. **智能解析入口迁移**：三条旧的 `/parse` 路径都应迁到 `/smart-fill/parse`，由 scene 参数区分。admin-web 调用侧需同步传 scene，后端保证 scene 存在时响应结构兼容旧接口。

## 6. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-08-11 | 初版：3 类共 46 项缺口分类分析；给出 3 条后端补齐 + 30 条协调建议 + 4 条暂缓建议 |
