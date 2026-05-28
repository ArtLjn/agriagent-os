## Why

用户的城市偏好（决定天气数据）和默认设置只存在移动端 AsyncStorage 中，换设备或重装就丢失。后端 Agent 的天气建议用的是硬编码坐标（苏州/徐州），和用户实际位置不一致，导致建议不准。

## What Changes

- 新增 `user_settings` 数据库表，持久化用户的城市偏好（城市名 + 经纬度）
- 新增 `GET/PUT /settings` API 扩展，支持读写 default_city / default_lat / default_lon
- 移动端注册后或首次登录时，请求 GPS 定位权限，自动获取当前位置设为默认城市
- 移动端设置变更同步到服务端，后端 Agent 读取用户真实坐标做天气建议
- 后端 `farm_context_service` 和 `WeatherSkill` 从用户设置读取坐标，不再用硬编码值

## Capabilities

### New Capabilities
- `user-settings-api`: 后端用户设置 API（读写 default_city / default_lat / default_lon）
- `gps-city-detection`: 移动端 GPS 定位 + 逆地理编码，首次自动设置默认城市

### Modified Capabilities
- `agent-weather-context`: Agent 天气上下文从硬编码坐标改为读取用户设置

## Impact

- **后端**：新增 `user_settings` 模型，扩展 `/settings` API，修改 `farm_context_service` 和 `WeatherSkill` 读取用户坐标
- **移动端**：新增 GPS 定位流程（注册后/首次登录），settingsStore 同步到服务端
- **数据库**：新增 `user_settings` 表
- **测试**：后端 settings API 测试、farm_context_service 坐标来源测试
