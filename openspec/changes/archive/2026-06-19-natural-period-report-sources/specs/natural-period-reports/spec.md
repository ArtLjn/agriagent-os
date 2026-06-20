## ADDED Requirements

### Requirement: 报告使用自然周和自然月时间范围
系统 SHALL 根据 `report_type` 使用固定自然周期生成报告：`weekly` 使用当前日期所在自然周的周一到周日，`monthly` 使用当前日期所在自然月的第一天到最后一天。

#### Scenario: 生成自然周周报
- **WHEN** 用户请求 `POST /agent/report` 且 `report_type` 为 `weekly`
- **THEN** 响应 `structured_data.period.granularity` 为 `week`
- **AND** `structured_data.period.start` 为当前自然周周一
- **AND** `structured_data.period.end` 为当前自然周周日

#### Scenario: 生成自然月月报
- **WHEN** 用户请求 `POST /agent/report` 且 `report_type` 为 `monthly`
- **THEN** 响应 `structured_data.period.granularity` 为 `month`
- **AND** `structured_data.period.start` 为当前自然月第一天
- **AND** `structured_data.period.end` 为当前自然月最后一天

### Requirement: 报告返回 A2UI 友好的结构化数据
`POST /agent/report` SHALL 返回可供 A2UI 渲染的 `structured_data`，包含 `report_type`、`period`、`summary`、`metrics`、`sections`、`recommendations`、`source_summary` 和 `source_refs`。

#### Scenario: 正常返回结构化报告
- **WHEN** 报告生成成功
- **THEN** 响应 SHALL 包含 `content`
- **AND** 响应 SHALL 包含非空 `structured_data.period`
- **AND** 响应 SHALL 包含 `structured_data.sections` 数组
- **AND** 响应 SHALL 包含 `structured_data.source_refs` 数组

#### Scenario: 兼容旧 Markdown 内容
- **WHEN** 报告生成成功
- **THEN** 响应 `content` SHALL 仍为可渲染的文本摘要
- **AND** 新前端 SHALL 能优先使用 `structured_data` 渲染报告详情

### Requirement: 周报和月报使用不同 section schema
系统 SHALL 为周报和月报生成不同的 section 组合，确保两者在内容重点和前端展示上明确区分。

#### Scenario: 周报包含执行复盘 section
- **WHEN** 生成 `weekly` 报告
- **THEN** `structured_data.sections` SHALL 至少包含本周快照、农事执行复盘、作业单状态、财务流水和下周行动建议相关 section

#### Scenario: 月报包含经营分析 section
- **WHEN** 生成 `monthly` 报告
- **THEN** `structured_data.sections` SHALL 至少包含月度指标、环比对比、成本结构、茬口组合、用工汇总、异常事项和下月计划相关 section

### Requirement: 报告信源覆盖稳定业务数据
报告生成 SHALL 使用当前 farm 范围内的稳定业务信源，包括茬口、阶段、农事日志、作业单、成本收入、用工、农场和用户设置。

#### Scenario: 周报收集周期内业务记录
- **WHEN** 生成周报
- **THEN** 系统 SHALL 查询自然周范围内的农事日志、作业单、成本收入和用工记录
- **AND** 系统 SHALL 查询当前活跃茬口及其阶段信息

#### Scenario: 月报收集周期内业务记录
- **WHEN** 生成月报
- **THEN** 系统 SHALL 查询自然月范围内的农事日志、作业单、成本收入和用工记录
- **AND** 系统 SHALL 查询当前活跃茬口及其阶段信息

#### Scenario: 限定当前农场数据
- **WHEN** 生成任意报告
- **THEN** 所有数据库信源 SHALL 按当前 `farm_id` 过滤

### Requirement: 报告包含可追踪信源引用
报告 `structured_data.source_refs` SHALL 记录用于生成报告的关键源记录，每个引用包含稳定 `id`、`source_type`、`source_id`、`label` 和可选 `occurred_on`。

#### Scenario: 成本记录进入信源引用
- **WHEN** 报告使用某条成本记录计算财务 section
- **THEN** `source_refs` SHALL 包含对应 `source_type=cost_record` 的引用

#### Scenario: 作业单进入信源引用
- **WHEN** 报告使用某条作业单生成农事或作业状态 section
- **THEN** `source_refs` SHALL 包含对应 `source_type=operation_work_order` 的引用

#### Scenario: Section 关联信源
- **WHEN** 某个 section 基于一组源记录生成
- **THEN** 该 section SHALL 能通过 `source_ref_ids` 关联到 `source_refs`

### Requirement: 后端确定性生成报告事实
系统 SHALL 由后端确定性生成报告指标、列表、分组、图表数据和信源引用，不得让 LLM 决定财务金额、作业数量、成本分类、时间范围或信源映射。

#### Scenario: 财务指标由数据库计算
- **WHEN** 报告返回收入、支出、净收支、人工成本或未结金额
- **THEN** 这些值 SHALL 来自数据库聚合或确定性计算

#### Scenario: LLM 输出不能覆盖事实字段
- **WHEN** LLM 返回文案结果
- **THEN** 后端 SHALL 只采纳 summary、highlights 或 recommendations 文案
- **AND** 后端 SHALL 忽略 LLM 返回的事实指标、section 类型或 source refs

### Requirement: LLM 只生成报告文案
报告 LLM 调用 SHALL 只负责生成短总结、亮点和建议文案，输入必须基于后端整理后的报告事实。

#### Scenario: LLM 输出合法文案 JSON
- **WHEN** LLM 返回包含 summary 和 recommendations 的合法 JSON
- **THEN** 后端 SHALL 将其合并到 `structured_data.summary` 和 `structured_data.recommendations`

#### Scenario: LLM 输出不可解析
- **WHEN** LLM 输出无法解析或字段缺失
- **THEN** 后端 SHALL 使用确定性 fallback 文案
- **AND** 报告生成 SHALL 继续成功

### Requirement: 天气只作为可选未来风险信源
报告 SHALL 将天气作为可选未来风险信源处理；系统 MAY 使用天气服务生成风险提醒，但天气服务失败或缺失时 SHALL NOT 影响报告生成。月报在没有历史天气存储时 SHALL NOT 生成本月天气复盘。

#### Scenario: 周报包含未来天气风险
- **WHEN** 天气服务返回未来高温、明显降雨或大风风险
- **THEN** 周报 MAY 包含天气风险 section
- **AND** 该 section SHALL 标记 `source_type=weather_service`

#### Scenario: 天气服务失败
- **WHEN** 天气服务调用失败
- **THEN** 报告 SHALL 继续生成
- **AND** 天气 section SHALL 省略或标记不可用

#### Scenario: 月报不伪造历史天气
- **WHEN** 系统没有历史天气存储
- **THEN** 月报 SHALL NOT 生成本月天气复盘 section

### Requirement: 报告支持上一自然周期对比
月报 SHALL 支持与上一自然月对比关键指标；周报 MAY 支持与上一自然周对比关键指标。

#### Scenario: 月报返回环比对比
- **WHEN** 生成月报
- **THEN** `structured_data.sections` SHALL 包含上一自然月对比 section
- **AND** 对比项 SHALL 至少覆盖收入、支出、净收支和农事次数

#### Scenario: 上一周期无数据
- **WHEN** 上一自然周期没有对应数据
- **THEN** 对比 section SHALL 明确标记缺少基线数据
- **AND** 不得编造变化率
