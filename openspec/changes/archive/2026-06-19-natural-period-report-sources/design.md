## Context

当前报告接口 `POST /agent/report` 返回 `content` 和简单 `structured_data`。数据主要来自活跃茬口、周期内农事日志、周期内成本记录，周报和月报只在时间窗口上不同，返回结构和内容重点接近。今日建议已经完成信源治理：先收集结构化候选，再排序/降噪，最后让 LLM 只改写候选文案。自然周期报告应借鉴这个边界，但报告不是今日行动列表，而是周期复盘和经营分析，需要更稳定、更适合 A2UI 的 section 数据。

本变更保持现有报告接口和历史接口兼容，不要求一次性替换前端。后端先产出稳定协议，移动端可逐步从 Markdown 渲染迁移到 A2UI section 渲染。

## Goals / Non-Goals

**Goals:**
- 周报固定表示自然周，月报固定表示自然月，并在响应中明确时间边界。
- 扩充报告信源，覆盖茬口、阶段、农事日志、作业单、成本收入、用工、农场定位和可选天气风险。
- 让 weekly 和 monthly 返回不同 section schema，避免两类报告只是日期不同。
- 让后端确定性生成指标、列表、分组、图表数据和信源引用。
- 限制 LLM 只生成短总结、亮点和建议文案，避免 LLM 生成整份 A2UI JSON。
- 保留 `content` 字段兼容旧端，同时把 `structured_data` 作为新端主渲染数据。

**Non-Goals:**
- 不新增任意日期范围报告；本次只支持自然周和自然月。
- 不要求前端立刻完成 A2UI 渲染迁移。
- 不做历史天气复盘，除非已有可追溯天气存储；天气只用于未来风险提醒。
- 不让 LLM 直接决定财务指标、作业状态、成本分类、信源引用或 section 结构。

## Decisions

### Decision 1: 使用自然周期而不是自定义日期范围

周报使用当前日期所在自然周的周一到周日，月报使用当前日期所在自然月的 1 日到月末。响应中返回 `period.start`、`period.end`、`period.label`、`period.granularity`。这符合用户当前选择，也能让缓存、历史列表和 A2UI 标题更稳定。

替代方案是支持任意日期范围。它更灵活，但会引入更多缓存键、历史筛选和 UI 交互复杂度，不适合当前阶段。

### Decision 2: 报告使用 section schema 区分周报/月报

周报侧重执行复盘和近期行动，包含 `weekly_snapshot`、`operation_review`、`work_order_status`、`crop_stage_updates`、`finance_flow`、`weather_risks`、`next_actions`。

月报侧重经营结果和结构分析，包含 `monthly_kpis`、`period_comparison`、`cost_structure`、`cycle_portfolio`、`operation_distribution`、`labor_summary`、`finance_exceptions`、`next_month_plan`。

替代方案是让同一组 sections 按 report_type 动态填充。这样实现更省事，但用户会感觉周报和月报只是同一报告换了标题。

### Decision 3: 后端生成 A2UI 友好结构，LLM 只补文案

`structured_data` 由后端生成稳定字段：
- `period`
- `summary`
- `metrics`
- `sections`
- `recommendations`
- `source_summary`
- `source_refs`

LLM 输入为后端整理好的报告事实和候选建议，输出只允许包含 `summary.text`、`highlights` 和 `recommendations` 文案字段。后端解析失败时使用确定性 fallback 文案。

替代方案是让 LLM 输出完整 JSON。该方案对今日建议可接受，但报告 JSON 包含图表、列表、指标和信源，字段更多，schema 漂移风险更高。

### Decision 4: 信源使用可追踪 source refs

每个 section 可以附带 `source_ref_ids`。`source_refs` 使用统一结构：
- `id`: 稳定引用 ID，例如 `cost_record:123`
- `source_type`: `crop_cycle`、`cycle_stage`、`farm_log`、`operation_work_order`、`cost_record`、`labor_entry`、`worker`、`farm`、`user_setting`、`weather_service`
- `source_id`: 数据库 ID，外部服务可为空
- `label`: 面向排查的简短说明
- `occurred_on`: 业务日期，可为空

这能支持后续报告详情解释、调试、数据飞轮和用户追问。

### Decision 5: 数据源分 P0/P1/P2

P0 是当前业务库稳定信源：茬口、阶段、农事日志、作业单、成本收入、用工、农场和用户设置。P1 是从 P0 派生的比较、异常、覆盖率。P2 是可选外部信源，当前只用于天气风险提醒。

报告生成不因 P2 天气失败而失败；天气缺失时对应 section 可省略或标记 unavailable。

## Risks / Trade-offs

- [Risk] `structured_data` 变大，历史记录 meta 体积增加。→ 控制明细数量，列表 section 返回 top N 和聚合结果，完整明细可后续通过详情接口扩展。
- [Risk] 旧端仍依赖 Markdown。→ 保留 `content`，由结构化数据渲染一份兼容摘要。
- [Risk] 作业单和旧农事日志可能重复表达同一操作。→ 先分别返回并在 section 中标识来源，后续通过 source_type/source_id 和时间/类型做去重。
- [Risk] 天气服务不稳定。→ 天气作为 P2 可选信源，不影响报告生成主流程。
- [Risk] 与现有 report-history spec 有重叠。→ 本能力定义报告生成和结构化内容；report-history 只负责历史列表和详情入口。

## Migration Plan

1. 扩展后端 schema，新增 period、metrics、sections、recommendations、source_summary、source_refs。
2. 重构报告数据服务，先生成确定性报告事实，再调用 LLM 生成少量文案。
3. 保存报告时把完整结构化数据写入 `AgentRecord.meta`，`content` 保持兼容摘要。
4. 历史接口返回旧记录时，缺少新结构则继续返回原 content，前端 fallback 渲染 Markdown。
5. 移动端后续逐步切换为 A2UI 渲染 `structured_data.sections`。
