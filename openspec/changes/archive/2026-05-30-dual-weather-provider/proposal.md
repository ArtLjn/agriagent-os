## Why

当前天气 skill 仅接入 Open-Meteo 单一数据源。Open-Meteo 对中国地区**无官方气象预警**（台风、暴雨、雷电等），预警逻辑靠本地阈值硬编码（高温>=35°C、降水>=50mm），远不如中国气象局发布的官方预警准确。同时 Open-Meteo 缺少中国区生活指数（感冒、穿衣、紫外线等）和分钟级降水预报，对农场精细化管理不足。

和风天气（QWeather）是中国气象局授权数据服务商，提供官方预警（5分钟更新）、16种生活指数、1km精度分钟降水、台风路径追踪。免费版 1000次/天，配合缓存完全够用。

## What Changes

- 新增和风天气 Provider 实现（`weather_service.py` 扩展为多 provider 架构）
- 重构 `WeatherSkill` 为 Provider Strategy 模式：统一接口，按 location 自动路由 provider，主 provider 失败自动兜底
- 统一 API Key 管理：新增 `SecretsConfig` 集中管理所有第三方 API key（和风天气、DashScope、LangSmith 等），各业务 Config 不再直接持有 api_key 字段，统一从 `settings.secrets` 读取。支持环境变量优先 + config.yaml 兜底
- 统一 `WeatherData` 输出模型，屏蔽 provider 差异
- LLM 侧仍只看到一个 `weather` tool，无感知 provider 切换
- 预警数据独立于 provider，通过爬取中国天气网（weather.com.cn `/dingzhi/` 页面）获取官方气象预警，免费且不消耗和风天气 API 配额。爬取失败时降级为 Open-Meteo 本地阈值检测
- 新增空气质量查询能力（和风天气 AQI + Open-Meteo CAMS）

## Capabilities

### New Capabilities
- `secrets-management`: API Key 统一管理——`SecretsConfig` 集中持有所有第三方密钥，各业务模块通过 `settings.secrets.xxx_key` 访问，不再散落在各自 Config 中
- `weather-provider`: 天气 Provider 抽象层——统一接口定义、Provider 路由策略、自动兜底机制
- `qweather-provider`: 和风天气 Provider 实现——天气预报、生活指数、空气质量、分钟降水（不含预警，预警独立爬取）
- `weather-alert-scraper`: 中国天气网预警爬虫——免费获取官方气象预警，独立于 provider，不消耗 API 配额
- `weather-air-quality`: 空气质量查询——通过和风天气或 Open-Meteo CAMS 获取 AQI 数据

### Modified Capabilities
- `prompt-template-management`: `base.j2` 中 `<user_context>` 需传递天气相关上下文（如当前预警状态摘要）

## Impact

- **代码**: `app/services/weather_service.py` 大幅重构（单文件 → provider 目录），`app/skills/weather/` 改为调用统一接口
- **配置**: `config.py` 新增 `SecretsConfig`，`AIConfig.api_key` / `LangSmithConfig.api_key` 迁移到 `SecretsConfig`，`WeatherConfig` 不再持有 api_key。`config.yaml` 新增 `secrets` 段
- **依赖**: 无新依赖（继续使用 `httpx`）
- **API**: LLM tool 接口不变（`weather`），新增 `get_air_quality` tool
- **数据源**: 新增和风天气 API（需注册获取 API key，免费版即可）
- **迁移**: 现有 `ai.api_key` / `langsmith.api_key` 配置路径变更，需更新 config.yaml 或环境变量
