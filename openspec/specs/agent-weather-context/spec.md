## Purpose

定义 agent-weather-context 能力的行为要求。

## Requirements

### Requirement: farm_context 天气坐标来源
系统 SHALL 从当前用户默认农场读取经营地区作为天气查询主来源。当用户默认农场缺少经营地区时，系统 SHALL 降级读取 `user_settings` 表中的 `default_lat` / `default_lon` / `default_city`；当用户设置也缺失时，降级使用 config.yaml 中的默认坐标。

#### Scenario: 农场有经营地区
- **WHEN** `farm_context_service.build_summary()` 被调用且当前 farm location 为"睢宁县"
- **THEN** 天气查询使用当前 farm 的经营地区"睢宁县"

#### Scenario: 农场有经营坐标
- **WHEN** `farm_context_service.build_summary()` 被调用且当前 farm 有经营地区坐标 lat=33.9, lon=117.95
- **THEN** 天气查询优先使用 lat=33.9, lon=117.95

#### Scenario: 农场无经营地区但用户有旧城市设置
- **WHEN** `farm_context_service.build_summary()` 被调用且当前 farm 无经营地区，但该用户在 `user_settings` 中有 `default_lat=39.9, default_lon=116.41`
- **THEN** 天气查询使用 lat=39.9, lon=116.41 作为兼容兜底

#### Scenario: 用户无城市设置
- **WHEN** `farm_context_service.build_summary()` 被调用且当前 farm 无经营地区，该用户在 `user_settings` 中无记录或 lat/lon 为 null
- **THEN** 天气查询降级使用 config.yaml 默认坐标（34.26, 117.28）

### Requirement: WeatherSkill 使用用户坐标
Agent 的 WeatherSkill SHALL 在用户未明确指定城市时使用当前用户默认农场经营地区，而非直接使用服务端全局配置。仅当当前农场经营地区缺失时，WeatherSkill SHALL 读取用户设置坐标作为兼容兜底，再降级到服务端默认坐标。

#### Scenario: 用户请求天气
- **WHEN** 用户通过 Agent 问"今天天气"且当前 farm location 为"睢宁县"
- **THEN** WeatherSkill 使用"睢宁县"查询天气

#### Scenario: 用户明确指定城市
- **WHEN** 用户通过 Agent 问"北京今天天气"且当前 farm location 为"睢宁县"
- **THEN** WeatherSkill 使用"北京"查询本次天气，不修改默认农场经营地区

#### Scenario: 用户无农场地区但有旧设置
- **WHEN** 用户通过 Agent 问"今天天气"且当前 farm 无经营地区，但 `user_settings` 中有 `default_lat=31.3, default_lon=120.62`
- **THEN** WeatherSkill 使用 lat=31.3, lon=120.62 查询天气

#### Scenario: 用户无设置
- **WHEN** 用户通过 Agent 问"今天天气"但当前 farm 无经营地区且 `user_settings` 中无坐标
- **THEN** WeatherSkill 降级使用 config.yaml 默认坐标
