## 1. 后端：数据模型与数据库

- [x] 1.1 创建 `backend/app/models/user_setting.py`：定义 `UserSetting` 模型（user_id, default_city, default_lat, default_lon, created_at, updated_at）
- [x] 1.2 在 `backend/app/models/__init__.py` 中导入 `UserSetting`，确保 `create_all` 时自动建表
- [x] 1.3 创建 `backend/app/schemas/settings.py`：扩展 `UserSettingsResponse` 和 `UserSettingsUpdate` schema，加入 default_city / default_lat / default_lon 字段

## 2. 后端：API 扩展

- [x] 2.1 修改 `backend/app/api/user_settings.py`：`GET /settings` 读取 `user_settings` 表数据，合并 `display_name` 返回
- [x] 2.2 修改 `backend/app/api/user_settings.py`：`PUT /settings` 支持 default_city / default_lat / default_lon 的部分更新，首次写入时自动创建记录

## 3. 后端：Agent 天气上下文

- [x] 3.1 修改 `backend/app/services/farm_context_service.py`：`_build_weather_line` 接收 `farm_id`，通过 farm→user→user_setting 链路获取用户坐标，无记录时降级到 config 默认值
- [x] 3.2 修改 `backend/app/agent/skills/weather/scripts/main.py`：WeatherSkill 从用户设置读取坐标，降级逻辑同上

## 4. 移动端：GPS 定位与城市匹配

- [x] 4.1 在 `FarmManagerMobile/src/utils/` 中创建 `locationUtils.ts`：实现 `requestLocationPermission()` 和 `getCurrentPosition()` 封装
- [x] 4.2 在 `FarmManagerMobile/src/utils/` 中创建 `cityMatcher.ts`：实现 Haversine 距离计算 + `findNearestCity(lat, lon)` 函数
- [x] 4.3 修改 `FarmManagerMobile/src/stores/settingsStore.ts`：新增 `syncToServer()` 方法，调用 `PUT /settings` 同步城市设置到后端

## 5. 移动端：定位流程集成

- [x] 5.1 修改注册流程（RegisterScreen）：注册成功后调用定位 → 匹配城市 → 存本地 + 同步服务端
- [x] 5.2 修改 App 启动流程（AppNavigator 或 HomeScreen）：检查服务端是否有 default_city，若无则触发定位补全
- [x] 5.3 修改设置页（SettingsScreen）：城市切换时调用 `syncToServer()` 同步到服务端

## 6. 测试

- [x] 6.1 后端测试：`backend/tests/test_user_settings_api.py` — 测试 GET/PUT /settings 的正常流程、首次创建、部分更新、未认证访问
- [x] 6.2 后端测试：`farm_context_service` 测试用户有/无设置时的坐标来源
- [x] 6.3 验证：启动后端服务，通过 curl 测试 API，确认建表和数据读写正常
