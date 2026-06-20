## Why

当前周报/月报虽然已经按周/月查询部分业务数据，但两者在返回内容和前端体验上差异不明显，且报告建议缺少可追踪信源。移动端计划使用 A2UI 渲染报告，需要后端提供稳定的结构化数据协议，而不是仅依赖 Markdown 或让 LLM 随机生成完整 JSON。

## What Changes

- 周报固定使用自然周范围，月报固定使用自然月范围，并在响应中明确返回 period label、start、end、granularity。
- 新增自然周期报告结构化数据协议，区分 weekly 和 monthly 的 section schema。
- 报告信源扩展为可追踪的业务来源：茬口阶段、农事日志、作业单、成本收入、用工、农场/用户设置，以及可选天气风险。
- 后端确定性生成指标、分组、列表、图表数据和 source refs；LLM 只负责生成 summary、highlights、recommendations 等短文案。
- 保留现有 `content` 字段作为兼容 Markdown 摘要，同时让 `structured_data` 成为 A2UI 主渲染入口。
- 报告记录写入信源摘要和结构化数据，便于后续排查“报告内容来自哪些记录”。

## Capabilities

### New Capabilities
- `natural-period-reports`: 定义自然周/月报告的时间范围、信源边界、结构化响应、LLM 输出边界和 A2UI 友好 section 协议。

### Modified Capabilities
- `report-history`: 报告历史详情继续展示历史记录，但应优先使用 `structured_data` 渲染，Markdown `content` 作为兼容 fallback。

## Impact

- 后端报告生成服务：`backend/app/services/report_data_service.py`、`backend/app/services/agent_report_service.py`。
- 后端 schema：`backend/app/schemas/structured_report.py`、`backend/app/schemas/agent.py`。
- 报告接口：`POST /agent/report`、`GET /agent/reports`、`GET /agent/report-history` 的响应内容。
- 数据来源：`crop_cycles`、`cycle_stages`、`farm_logs`、`operation_work_orders`、`cost_records`、`labor_entries`、`workers`、`farms`、`user_settings`，以及天气服务。
- 移动端报告详情和历史列表后续可使用 A2UI section 渲染。
