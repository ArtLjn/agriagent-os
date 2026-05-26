## 1. SecretsConfig 统一密钥管理

- [ ] 1.1 `app/core/config.py` — 新增 `SecretsConfig` 类，持有 `dashscope_api_key`、`qweather_api_key`、`langsmith_api_key`，默认空字符串
- [ ] 1.2 `app/core/config.py` — `Settings` 新增 `secrets: SecretsConfig` 字段
- [ ] 1.3 `app/core/config.py` — `AIConfig` 移除 `api_key` 字段，`LangSmithConfig` 移除 `api_key` 字段
- [ ] 1.4 `app/core/config.py` — 添加向后兼容：`Settings.ai_api_key` 属性优先读 `secrets.dashscope_api_key`，fallback 到 `ai.api_key`（若存在），打印 deprecation warning
- [ ] 1.5 `app/core/llm.py` — 更新为从 `settings.secrets.dashscope_api_key` 获取 API key
- [ ] 1.6 `app/core/llm.py` — LangSmith 配置同理，从 `settings.secrets.langsmith_api_key` 获取
- [ ] 1.7 `config.yaml` — 新增 `secrets` 段，将原 `ai.api_key` 迁移到 `secrets.dashscope_api_key`，新增 `secrets.qweather_api_key` 占位

## 2. Weather Provider 抽象层

- [ ] 2.1 创建 `app/services/weather/` 目录，添加 `__init__.py`
- [ ] 2.2 `app/services/weather/base.py` — 定义 `WeatherData`、`DailyForecast`、`WeatherAlert`、`AirQuality` dataclass
- [ ] 2.3 `app/services/weather/base.py` — 定义 `WeatherProvider` ABC：`fetch_daily(location, days) -> WeatherData`、`fetch_air_quality(location) -> AirQuality | None`、`can_serve(location) -> bool`
- [ ] 2.4 `app/services/weather/base.py` — 定义 `ProviderError` 异常类
- [ ] 2.5 `app/services/weather/open_meteo.py` — 从现有 `weather_service.py` 迁移 `fetch_weather` 为 `OpenMeteoProvider`，实现 `WeatherProvider` 接口
- [ ] 2.6 `app/services/weather/open_meteo.py` — 城市名 → 坐标：调用 Open-Meteo Geocoding API
- [ ] 2.7 `app/services/weather/open_meteo.py` — 实现 `fetch_air_quality()`，调用 Open-Meteo Air Quality API
- [ ] 2.8 删除旧 `app/services/weather_service.py`（已被 `weather/` 目录替代）
- [ ] 2.9 更新所有引用 `weather_service` 的 import 路径

## 3. 和风天气 Provider

- [ ] 3.1 `app/services/weather/qweather.py` — 实现 `QWeatherProvider`，构造函数接受 `api_key` 参数
- [ ] 3.2 实现城市名解析：调用和风天气 GeoAPI `city-lookup`，返回城市 ID 和坐标
- [ ] 3.3 实现天气预报：调用 `/v7/weather/7d`，解析为 `list[DailyForecast]`
- [ ] 3.4 实现生活指数：调用 `/v7/indices/1d`，提取感冒、穿衣、紫外线等指数
- [ ] 3.5 实现空气质量：调用 `/v7/air/now`，解析为 `AirQuality`（AQI、PM2.5、等级）
- [ ] 3.6 实现 `can_serve()`：若 GeoAPI `city-lookup` 有结果则返回 True
- [ ] 3.7 错误处理：401（key 无效）、429（超限）、超时（10s）均抛出 `ProviderError`

## 4. 中国天气网预警爬虫

- [ ] 4.1 `app/services/weather/alert_scraper.py` — 实现 `AlertScraper` 类
- [ ] 4.2 维护常见城市 → weather.com.cn 城市编号映射表（至少覆盖全国省会+地级市，约 300 个）
- [ ] 4.3 实现 `fetch_alerts(city_name) -> list[WeatherAlert]`：城市名 → 编号 → 请求 `https://d1.weather.com.cn/dingzhi/{code}.html` → 解析预警数据
- [ ] 4.4 请求伪装：设置 `Referer: https://m.weather.com.cn/` 和浏览器 UA
- [ ] 4.5 响应解析：处理 JS 变量格式的返回数据，提取预警标题、等级（黄/橙/红/蓝）、描述
- [ ] 4.6 独立缓存：TTL 10 分钟，使用 `@cached(ttl_seconds=600)`
- [ ] 4.7 容错降级：网络超时/解析失败时返回空列表，记录 warning 日志，不抛异常

## 5. Provider 路由 + 兜底策略

- [ ] 5.1 `app/services/weather/strategy.py` — 实现 `WeatherStrategy`，持有 `providers: list[WeatherProvider]`（按优先级排序）和 `alert_scraper: AlertScraper`
- [ ] 5.2 `WeatherStrategy.__init__` — 根据 `secrets.qweather_api_key` 是否配置决定 provider 列表：有 key → `[QWeatherProvider, OpenMeteoProvider]`，无 key → `[OpenMeteoProvider]`
- [ ] 5.3 `WeatherStrategy.fetch(location, days)` — 遍历 providers，第一个 `can_serve(location)=True` 的作为主 provider，失败则尝试下一个
- [ ] 5.4 `WeatherStrategy.fetch(location, days)` — 预报数据从 provider 获取后，叠加 `AlertScraper.fetch_alerts()` 获取预警数据（provider 返回的 alerts 字段置空，由 strategy 统一注入爬虫预警）
- [ ] 5.5 `WeatherStrategy.fetch_air_quality(location)` — 同理，优先和风天气 AQI，兜底 Open-Meteo CAMS
- [ ] 5.6 `app/services/weather/__init__.py` — 导出 `get_weather_strategy()` 工厂函数（单例，懒初始化）

## 6. WeatherSkill 改造

- [ ] 5.1 `app/skills/weather/scripts/main.py` — `WeatherSkill.execute()` 改为调用 `WeatherStrategy.fetch(location, days)`
- [ ] 5.2 `parameters_schema` — `location` 参数 description 改为"城市名（如苏州、北京）"，不再标注"仅作标注"
- [ ] 5.3 `WeatherSkill.execute()` — 将 `WeatherData` 格式化为包含预警、指数的完整文本
- [ ] 5.4 `WeatherSkill.execute()` — `SkillResult.data` 存储 `WeatherData` 的 dict 序列化（供后续前端扩展）
- [ ] 5.5 新建 `app/skills/air_quality/` — `AirQualitySkill`，tool 名 `get_air_quality`，参数 `location`（必填），调用 `WeatherStrategy.fetch_air_quality()`

## 7. Prompt 模板更新

- [ ] 6.1 `prompts/base.j2` — `<user_context>` 段新增可选的 `{{ weather_alert_summary }}`（如"当前有暴雨黄色预警"），条件渲染（无预警时不显示）

## 8. 端到端验证

- [ ] 8.1 测试：和风天气 key 未配置时，全部走 Open-Meteo，天气查询正常
- [ ] 8.2 测试：和风天气 key 已配置，查询中国城市走和风天气，返回生活指数
- [ ] 8.3 测试：预警爬虫正常返回官方预警数据
- [ ] 8.4 测试：预警爬虫失败时静默降级，预报不受影响
- [ ] 8.5 测试：和风天气超时/失败，自动兜底到 Open-Meteo
- [ ] 8.6 测试：查询海外城市走 Open-Meteo
- [ ] 8.7 测试：`get_air_quality` 正常返回 AQI 数据
- [ ] 8.8 测试：`secrets.dashscope_api_key` 环境变量优先于 config.yaml
- [ ] 8.9 测试：密钥不出现在日志或错误消息中
- [ ] 8.10 测试：预警缓存 10 分钟内不重复请求
