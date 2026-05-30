## ADDED Requirements

### Requirement: 空气质量查询 Skill
系统 SHALL 提供 `get_air_quality` Skill，获取指定城市的空气质量数据（AQI、PM2.5、空气质量等级）。

#### Scenario: 中国城市走和风天气 AQI
- **WHEN** LLM 调用 `get_air_quality(location="苏州")`，和风天气 key 已配置
- **THEN** 通过和风天气空气质量 API 获取数据，返回包含 AQI 数值、等级、PM2.5

#### Scenario: 海外城市走 Open-Meteo CAMS
- **WHEN** LLM 调用 `get_air_quality(location="伦敦")`
- **THEN** 通过 Open-Meteo Air Quality API 获取数据，返回包含 PM10、PM2.5、European AQI

#### Scenario: 空气质量数据格式化
- **WHEN** 获取到空气质量数据
- **THEN** SkillResult.reply 包含格式化文本，如"苏州空气质量：AQI 52（良），PM2.5: 35μg/m³"

### Requirement: 空气质量 Skill 参数定义
`get_air_quality` SHALL 接受一个参数 `location`（城市名，字符串类型，必填）。

#### Scenario: 参数 schema 定义
- **WHEN** LLM 获取 `get_air_quality` 的 tool schema
- **THEN** schema 包含 `location`（type=string, required=true, description="查询空气质量的地点"）
