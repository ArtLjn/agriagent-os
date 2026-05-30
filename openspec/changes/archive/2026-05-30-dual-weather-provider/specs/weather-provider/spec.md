## ADDED Requirements

### Requirement: WeatherProvider 抽象接口
系统 SHALL 定义 `WeatherProvider` 抽象基类，所有天气数据源 SHALL 实现此接口。接口方法包括 `fetch_daily(location, days)` 和 `can_serve(location)`。

#### Scenario: Provider 实现接口
- **WHEN** 新增一个天气数据源（如 WeatherKit）
- **THEN** 只需实现 `WeatherProvider` 的抽象方法即可接入，无需修改 Skill 层或路由层

#### Scenario: can_serve 判断
- **WHEN** `QWeatherProvider.can_serve("伦敦")` 被调用
- **THEN** 返回 `False`（和风天气对海外数据覆盖有限）

### Requirement: 统一输出模型 WeatherData
所有 Provider SHALL 返回统一的 `WeatherData` 数据结构，包含 `location`、`provider`、`daily`（列表）、`alerts`（列表）、`air_quality`（可选）、`current_temp`（可选）。

#### Scenario: Open-Meteo 返回统一结构
- **WHEN** `OpenMeteoProvider.fetch_daily("北京", 7)` 被调用
- **THEN** 返回 `WeatherData` 对象，`provider="open-meteo"`，`daily` 包含 7 天 `DailyForecast`，`alerts` 为本地阈值检测结果

#### Scenario: 和风天气返回统一结构
- **WHEN** `QWeatherProvider.fetch_daily("苏州", 7)` 被调用
- **THEN** 返回 `WeatherData` 对象，`provider="qweather"`，`alerts` 包含官方预警数据

### Requirement: Provider 路由策略
系统 SHALL 按优先级自动选择 provider：中国城市 → 和风天气优先（预报/指数/AQI），海外城市 → Open-Meteo。和风天气 key 未配置时全部走 Open-Meteo。预警数据独立于 provider，通过 `AlertScraper`（中国天气网爬虫）获取，不消耗和风天气 API 配额。

#### Scenario: 中国城市路由到和风天气
- **WHEN** 用户查询"苏州天气"，和风天气 API key 已配置
- **THEN** `WeatherStrategy` 选择 `QWeatherProvider` 作为主 provider，预警通过 `AlertScraper` 获取

#### Scenario: 海外城市路由到 Open-Meteo
- **WHEN** 用户查询"伦敦天气"
- **THEN** `WeatherStrategy` 选择 `OpenMeteoProvider`，预警走本地阈值检测

#### Scenario: 和风天气未配置时全走 Open-Meteo
- **WHEN** `secrets.qweather_api_key` 为空
- **THEN** 预报走 `OpenMeteoProvider`，中国城市预警仍通过 `AlertScraper` 获取

### Requirement: Provider 故障自动兜底
主 provider 请求失败时 SHALL 自动尝试次 provider。兜底对 Skill 层和 LLM 完全透明。

#### Scenario: 和风天气超时兜底到 Open-Meteo
- **WHEN** 和风天气 API 请求超时（>10s）
- **THEN** 自动调用 `OpenMeteoProvider.fetch_daily()`，返回结果中 `provider` 标记为实际使用的 provider

#### Scenario: 两个 Provider 都失败
- **WHEN** 和风天气和 Open-Meteo 都请求失败
- **THEN** 返回 `SkillResult(status=FAILED)`，reply 包含友好错误信息"天气数据暂时不可用，请稍后再试"

### Requirement: WeatherSkill 对外接口不变
`get_weather_forecast` tool 的 `parameters_schema` 和调用方式 SHALL 保持不变。LLM 无感知 provider 切换。

#### Scenario: LLM 调用天气 tool
- **WHEN** LLM 调用 `get_weather_forecast(location="苏州")`
- **THEN** Skill 内部自动路由到和风天气，返回格式化天气预报文本

#### Scenario: location 参数实际生效
- **WHEN** LLM 调用 `get_weather_forecast(location="南京")`
- **THEN** 查询南京的天气（不再使用硬编码坐标）
