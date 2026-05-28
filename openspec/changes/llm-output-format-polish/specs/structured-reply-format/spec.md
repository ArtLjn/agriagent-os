## ADDED Requirements

### Requirement: Weather forecast renders as Markdown table
`get_weather_forecast` skill 的回复 SHALL 使用 Markdown 表格展示天气数据，包含 emoji 天气图标、日期、温度、降水量。只展示未来 3 天（非 7 天）。表格前加地点 emoji，表格后附天气预警。

#### Scenario: Normal weather forecast
- **WHEN** `get_weather_forecast` 成功返回 3 天天气数据
- **THEN** 回复 SHALL 以 `📍 {地点}` 开头
- **AND** 包含 Markdown 表格，列：日期、天气、最高温、最低温、降水
- **AND** 日期格式为 `M/D`（如 `5/28`）
- **AND** 天气列使用 emoji（☀️🌤️⛅🌥️🌧️⛈️等）

#### Scenario: Weather with warnings
- **WHEN** 天气数据包含预警信息
- **THEN** 表格后 SHALL 附加 `⚠️` 开头的预警行

#### Scenario: Weather with no data
- **WHEN** 天气查询无数据
- **THEN** 回复 SHALL 返回 `🌤️ 暂时获取不到天气数据，请稍后再试。`

### Requirement: Pending action confirmation uses emoji and readable format
`build_confirm_message` SHALL 为每个 write skill 生成带 emoji 前缀、中文参数名的确认文案。参数 SHALL 使用可读格式而非技术字段名。

#### Scenario: Create cost record confirmation
- **WHEN** pending action 是 `create_cost_record`，params `{amount: 50, category: "化肥", record_type: "cost"}`
- **THEN** 确认文案 SHALL 为 `💰 确认记账：化肥 50元（支出），确认吗？`

#### Scenario: Create crop cycle confirmation
- **WHEN** pending action 是 `create_crop_cycle`，params `{crop_name: "西瓜", season: "春季"}`
- **THEN** 确认文案 SHALL 为 `🌱 确认创建茬口：西瓜·春季，确认吗？`

#### Scenario: Create crop template confirmation
- **WHEN** pending action 是 `create_crop_template`，params `{crop_name: "玉米"}`
- **THEN** 确认文案 SHALL 为 `📋 确认创建作物模板：玉米，确认吗？`

#### Scenario: Log farm activity confirmation
- **WHEN** pending action 是 `log_farm_activity`，params `{operation_type: "浇水"}`
- **THEN** 确认文案 SHALL 为 `📝 确认记录农事：浇水，确认吗？`

#### Scenario: Settle debt confirmation
- **WHEN** pending action 是 `settle_debt`，params `{counterparty: "老王", amount: 500}`
- **THEN** 确认文案 SHALL 为 `💳 确认还款：老王 500元，确认吗？`

#### Scenario: Update crop stage confirmation
- **WHEN** pending action 是 `update_crop_stage`，params `{stage_name: "开花期"}`
- **THEN** 确认文案 SHALL 为 `🔄 确认更新阶段：开花期，确认吗？`

### Requirement: Crop cycle creation result uses emoji and ordered list
`create_crop_cycle` skill 的 `_format_reply` SHALL 使用 ✅ emoji 标记成功，📋 emoji 标记阶段规划，有序列表展示阶段。

#### Scenario: Successful crop cycle creation
- **WHEN** 茬口「春季西瓜」成功创建，有 3 个阶段
- **THEN** 回复 SHALL 以 `✅ 茬口「春季西瓜」已创建！` 开头
- **AND** 阶段用有序列表展示，每项包含阶段名、日期范围、天数
- **AND** 日期格式为 `M/D`

### Requirement: Prompt template includes emoji and format guidance
`base.j2` SHALL 包含【回复风格】段落，指导 LLM 在自由生成场景使用 emoji 和 Markdown 格式。

#### Scenario: Prompt contains format rules
- **WHEN** 渲染 system prompt
- **THEN** prompt SHALL 包含 emoji 使用规则（建议用 🌱💡⚠️📊 等）
- **AND** 包含 Markdown 格式规则（用列表、加粗组织内容）
- **AND** 保持口语化短句要求
