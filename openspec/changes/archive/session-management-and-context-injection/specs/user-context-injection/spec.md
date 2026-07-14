## ADDED Requirements

### Requirement: 用户上下文结构化注入
系统 SHALL 将用户关键信息以 XML 格式注入 `base.j2` 的 `<user_context>` 段。注入内容包含：用户所在城市/位置（`Farm.location`）、称呼（`Farm.display_name`）、当前季节。

#### Scenario: location 有值时注入
- **WHEN** `Farm.location` 为"苏州"
- **THEN** system prompt 包含 `<user_context><location>苏州</location><name>农友</name><season>春季</season></user_context>`

#### Scenario: location 为空时不注入 location 节点
- **WHEN** `Farm.location` 为 NULL
- **THEN** system prompt 的 `<user_context>` 段不包含 `<location>` 节点，但 LLM 会追问用户所在城市

#### Scenario: 季节自动计算
- **WHEN** 当前日期为 7 月 15 日
- **THEN** `<season>` 值为"夏季"（3-5月春、6-8月夏、9-11月秋、12-2月冬）

### Requirement: 城市信息传递给 skill
当 LLM 通过 function calling 调用需要 location 参数的 skill 时，LLM SHALL 使用 `<user_context>` 中的 location 值作为参数。

#### Scenario: 天气查询使用注入的城市
- **WHEN** 用户问"明天天气怎么样"，`<user_context>` 中 location 为"苏州"
- **THEN** LLM 调用 `weather` 时传入 `location: "苏州"`

#### Scenario: location 为空时 LLM 追问
- **WHEN** 用户问"明天天气怎么样"，`<user_context>` 中无 location
- **THEN** LLM 回复询问用户所在城市，不调用天气 skill
