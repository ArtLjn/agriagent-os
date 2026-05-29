## ADDED Requirements

### Requirement: Backend weather forecast cache
系统 SHALL 在 `strategy.fetch()` 层缓存天气预报响应。缓存 key 由 `(location, days, lat, lon)` 组成。缓存 TTL 为 10 分钟。命中缓存时 SHALL 直接返回缓存数据，不发起外部 HTTP 请求。

#### Scenario: Cache miss — first request
- **WHEN** 请求"宁德"3 天预报，缓存无记录
- **THEN** 系统发起外部 API 请求，返回结果并写入缓存

#### Scenario: Cache hit — repeated request
- **WHEN** 请求"宁德"3 天预报，10 分钟内已有缓存
- **THEN** 系统直接返回缓存数据，不发起任何外部请求

#### Scenario: Cache expired
- **WHEN** 缓存超过 10 分钟后再次请求
- **THEN** 系统重新请求外部 API 并更新缓存

### Requirement: Backend alert cache
系统 SHALL 独立缓存气象局预警数据。缓存 key 为 `city_name`，TTL 为 30 分钟。

#### Scenario: Alert cache hit
- **WHEN** 30 分钟内重复请求同一城市预警
- **THEN** 直接返回缓存的预警列表，不调用气象局 API

#### Scenario: Alert cache expired
- **WHEN** 预警缓存超过 30 分钟
- **THEN** 重新抓取气象局预警并更新缓存

### Requirement: Frontend weather AsyncStorage cache
前端 SHALL 将天气数据持久化到 AsyncStorage。打开 App 时先展示缓存数据，后台静默刷新。缓存 key 为 `weather_cache_<cityName>`。

#### Scenario: App cold start with cache
- **WHEN** 用户打开 App，AsyncStorage 中有"宁德"的缓存天气数据
- **THEN** 立即展示缓存数据，同时后台发起网络请求刷新

#### Scenario: App cold start without cache
- **WHEN** 用户首次打开 App，无缓存数据
- **THEN** 显示加载状态，发起网络请求获取天气
