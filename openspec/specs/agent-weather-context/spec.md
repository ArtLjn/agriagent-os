## Purpose

定义 agent-weather-context 能力的行为要求。

## Requirements

### Requirement: farm_context 天气坐标来源
系统 SHALL 从 `user_settings` 表读取用户的 `default_lat` / `default_lon` 作为天气查询坐标。当用户无设置时，降级使用 config.yaml 中的默认坐标。

#### Scenario: 用户有城市设置
- **WHEN** `farm_context_service.build_summary()` 被调用且该用户在 `user_settings` 中有 `default_lat=39.9, default_lon=116.41`
- **THEN** 天气查询使用 lat=39.9, lon=116.41

#### Scenario: 用户无城市设置
- **WHEN** `farm_context_service.build_summary()` 被调用且该用户在 `user_settings` 中无记录或 lat/lon 为 null
- **THEN** 天气查询降级使用 config.yaml 默认坐标（34.26, 117.28）

### Requirement: WeatherSkill 使用用户坐标
Agent 的 WeatherSkill SHALL 从用户设置中读取坐标，而非使用服务端全局配置。

#### Scenario: 用户请求天气
- **WHEN** 用户通过 Agent 问"今天天气"且 `user_settings` 中有 `default_lat=31.3, default_lon=120.62`
- **THEN** WeatherSkill 使用 lat=31.3, lon=120.62 查询天气

#### Scenario: 用户无设置
- **WHEN** 用户通过 Agent 问"今天天气"但 `user_settings` 中无坐标
- **THEN** WeatherSkill 降级使用 config.yaml 默认坐标
