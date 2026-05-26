## ADDED Requirements

### Requirement: 和风天气预报
`QWeatherProvider` SHALL 通过和风天气 API 获取 7 天天气预报，包括最高/最低温度、天气状况、降水量、风力。

#### Scenario: 获取苏州 7 天预报
- **WHEN** `QWeatherProvider.fetch_daily("苏州", 7)` 被调用
- **THEN** 调用和风天气 `/v7/weather/7d` API，返回 7 天 `DailyForecast` 列表

#### Scenario: 城市名自动解析
- **WHEN** 传入城市名"苏州"
- **THEN** 先调用 GeoAPI `city-lookup` 获取城市 ID，再用 ID 查询天气

### Requirement: 和风天气官方预警
`QWeatherProvider` SHALL 获取中国气象局发布的实时灾害预警（台风、暴雨、雷电、高温等），覆盖中国所有市县。

#### Scenario: 有预警时返回
- **WHEN** 苏州当前有"暴雨黄色预警"
- **THEN** `WeatherData.alerts` 包含 `WeatherAlert(title="暴雨黄色预警", severity="yellow", description=...)`

#### Scenario: 无预警时返回空列表
- **WHEN** 查询城市当前无任何预警
- **THEN** `WeatherData.alerts` 为空列表 `[]`

### Requirement: 和风天气生活指数
`QWeatherProvider` SHALL 获取生活指数数据（感冒、穿衣、紫外线、运动等），并格式化到预报文本中。

#### Scenario: 生活指数包含在回复中
- **WHEN** 用户查询苏州天气
- **THEN** SkillResult.reply 包含生活指数信息，如"感冒指数：较易发，注意保暖"

### Requirement: 和风天气 API 错误处理
`QWeatherProvider` SHALL 正确处理和风天气 API 的错误响应，包括 401（key 无效）、429（超限）、网络超时。

#### Scenario: API key 无效
- **WHEN** 和风天气返回 HTTP 401
- **THEN** Provider 抛出 `ProviderError`，strategy 自动兜底到 Open-Meteo，日志记录"和风天气 API 认证失败"

#### Scenario: 请求超限
- **WHEN** 和风天气返回 HTTP 429
- **THEN** Provider 抛出 `ProviderError`，strategy 自动兜底到 Open-Meteo

#### Scenario: 网络超时
- **WHEN** 和风天气 API 请求超过 10 秒
- **THEN** Provider 抛出 `ProviderError`，strategy 自动兜底到 Open-Meteo
