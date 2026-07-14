## Context

当前天气系统由三部分组成：
- `app/services/weather_service.py`：单文件，直接调用 Open-Meteo API，包含 `fetch_weather()` 和本地阈值预警 `check_weather_warnings()`
- `app/skills/weather/scripts/main.py`：`WeatherSkill` 类，硬编码坐标（`settings.weather_latitude/longitude`），30 分钟缓存
- `app/core/config.py`：`WeatherConfig` 仅有 `latitude`/`longitude`，无 API key 管理

问题：
1. Open-Meteo 无中国官方预警、无生活指数、无分钟降水
2. API key 散落在 `AIConfig.api_key`、`LangSmithConfig.api_key`，新增和风天气 key 会继续分散
3. `WeatherSkill.parameters_schema` 的 `location` 参数"仅作标注"，实际查询用配置坐标——无法查询其他地点
4. 预警靠硬编码阈值（高温>=35、降水>=50），不是官方发布的预警

外部 API 能力对比：

| 能力 | Open-Meteo | 和风天气免费版 |
|------|-----------|--------------|
| 全球预报 | 16天 | 7天（中国30天） |
| 中国官方预警 | 无 | 有（5分钟更新） |
| 生活指数 | 无 | 16种 |
| 分钟降水 | 无 | 1km精度 |
| 空气质量 | CAMS全球 | 中国1km |
| 台风路径 | 无 | 有 |
| API key | 不需要 | 需要（免费1000次/天） |

## Goals / Non-Goals

**Goals:**
- 实现双 Provider 天气架构：和风天气（中国主）+ Open-Meteo（国际 + 兜底）
- LLM 侧只看到一个 `weather` tool，provider 切换透明
- 统一 API key 管理，所有第三方密钥收归 `SecretsConfig`
- 支持按 location 自动路由 provider（中国城市 → 和风天气优先，海外 → Open-Meteo）
- 主 provider 失败自动兜底到次 provider
- 支持查询任意地点（不再硬编码坐标）

**Non-Goals:**
- 不做分钟降水 skill（和风天气有数据但农场 app 当前不需要这么细粒度）
- 不做台风路径 skill（独立功能，后续可加）
- 不做缓存层改造（继续用现有 `@cached` 装饰器）
- 不做 Open-Meteo 付费版或和风天气付费版

## Decisions

### D1: SecretsConfig 统一密钥管理

**选择**: 新增顶层 `SecretsConfig`，持有所有第三方 API key。各业务 Config（`AIConfig`、`WeatherConfig`、`LangSmithConfig`）移除 `api_key` 字段。

```python
class SecretsConfig(BaseModel):
    dashscope_api_key: str = ""        # 原 ai.api_key
    qweather_api_key: str = ""         # 新增
    langsmith_api_key: str = ""        # 原 langsmith.api_key
```

**备选方案**:
- A) 各 Config 继续持有自己的 api_key → 当前状态，key 分散难管理
- B) 环境变量直接读取，不走 Config → 绕过了 pydantic-settings 的验证和类型安全
- C) .env 文件 + python-dotenv → 与现有 YAML 配置体系冲突

**理由**: 项目已有 `pydantic-settings` + YAML 配置体系。`SecretsConfig` 延续这个模式，key 统一管理，支持 `config.yaml` + 环境变量两种来源。环境变量格式 `SECRETS__QWEATHER_API_KEY`，符合 pydantic-settings 的 `env_nested_delimiter`。

### D2: Provider Strategy 模式（非多 Skill）

**选择**: 保持一个 `WeatherSkill`，内部按 provider strategy 路由。不是注册两个独立 skill。

**备选方案**:
- A) 两个独立 Skill（`get_weather_china` + `get_weather_intl`）→ LLM 需要判断用哪个，选错概率高
- B) 一个 Skill + `provider` 参数让 LLM 选 → LLM 不懂 provider 概念
- C) skillify 的 `is_dispatch` 路由 → dispatch 是按 pattern 分发到 sub-skill，不适合按地理位置路由

**理由**: LLM 只需理解"查天气"这一个意图。Provider 选择是基础设施层的决策，不应暴露给 LLM。

### D3: 城市名 → 坐标双路径解析

**选择**: 和风天气用城市 ID（`location` 参数传 `101020100` 或城市名自动 lookup），Open-Meteo 用经纬度。统一接口接受城市名，各 provider 内部自行解析。

```
用户传 "苏州" →
  和风天气: /lookup?location=苏州 → 101190401 → /weather?location=101190401
  Open-Meteo: geocoding?name=Suzhou → 31.30,120.62 → /forecast?lat=31.30&lon=120.62
```

**理由**: 屏蔽 provider 的地理编码差异，调用方只传城市名。

### D4: 预警独立爬取——中国天气网 /dingzhi/ 页面

**选择**: 中国官方气象预警从 weather.com.cn 的 `/dingzhi/{city_code}.html` 页面爬取，不消耗和风天气 API 配额。

**理由**:
- weather.com.cn 是中国气象局官网，`/dingzhi/` 页面发布官方预警，数据权威
- 预警页面结构简单（纯数据列表），比预报页面稳定得多，爬虫风险可控
- 爬取预警不消耗和风天气 1000 次/天配额，和风配额只花在预报 + 指数 + AQI 上
- 爬取失败降级为 Open-Meteo 本地阈值检测（现有逻辑），不影响核心功能
- 参考 `aahl/skills@tianqi`（1.1K 安装）的已有实现

**爬取逻辑**:
```python
# 城市名 → weather.com.cn 城市编号（101020100 格式）
# → GET https://d1.weather.com.cn/dingzhi/101020100.html
# → 解析返回的 JS 变量中的预警数据
# → 缓存 10 分钟（预警更新频率约 5 分钟）
```

**备选方案**:
- A) 和风天气 `/v7/warning/now` API → 消耗配额，每次查天气多 1 次调用
- B) 纯本地阈值检测 → 不准确，非官方预警
- C) 彩云天气 API → 需要 API token

### D5: 路由策略——预报走 API，预警走爬虫

**选择**: 分层策略：
1. **预报/指数/AQI**：和风天气 API（中国）或 Open-Meteo（国际/兜底）
2. **预警**：weather.com.cn 爬虫（中国，免费）或 Open-Meteo 本地阈值（兜底）
3. 主 provider 请求失败 → 自动兜底到另一个 provider
4. 和风天气 key 未配置 → 全部走 Open-Meteo + 预警爬虫

**中国城市判断**: 和风天气 GeoAPI 的 `city-lookup` 接口，若返回结果则为中国城市。预警爬虫使用 weather.com.cn 的城市编号体系（101 开头 9 位数字）。

### D6: 统一输出模型 WeatherData

```python
@dataclass
class DailyForecast:
    date: str
    temp_max: float
    temp_min: float
    weather_text: str       # "晴"、"多云转小雨"
    precipitation: float
    wind_speed: float

@dataclass
class WeatherAlert:
    title: str              # "暴雨黄色预警"
    severity: str           # "yellow"/"orange"/"red"
    description: str

@dataclass
class AirQuality:
    aqi: int
    category: str           # "优"、"良"、"轻度污染"
    pm25: float

@dataclass
class WeatherData:
    location: str
    provider: str           # "qweather" / "open-meteo"
    daily: list[DailyForecast]
    alerts: list[WeatherAlert]
    air_quality: AirQuality | None
    current_temp: float | None
```

**理由**: Skill 的 `execute` 返回 `SkillResult(reply=text)`，内部用 `WeatherData` 聚合数据后格式化为文本。`WeatherData` 结构化数据存入 `SkillResult.data` 供后续扩展（如前端天气卡片）。

### D7: 文件组织

```
app/services/weather/
├── __init__.py            # 导出 get_weather_service
├── base.py                # WeatherProvider ABC + WeatherData 模型
├── strategy.py            # WeatherStrategy 路由 + 兜底
├── open_meteo.py          # OpenMeteoProvider（从现有 weather_service.py 迁移）
├── qweather.py            # QWeatherProvider（新增）
└── alert_scraper.py       # 中国天气网预警爬虫（免费，不消耗 API 配额）
```

**理由**: 现有 `weather_service.py` 是单文件 86 行，拆为 provider 目录后各 provider 独立演化。`strategy.py` 负责路由逻辑，skill 层只需调用 `get_weather_service().fetch(location, days)`。

## Risks / Trade-offs

- **[和风天气 API key 未配置]** → 降级为纯 Open-Meteo 模式 + 预警爬虫，天气查询和预警不中断
- **[和风天气免费版 1000 次/天超限]** → 预警走爬虫不消耗配额；预报配合 30 分钟缓存，每天实际调用量约 50-100 次；超限后自动兜底 Open-Meteo
- **[API key 迁移 breaking change]** → `ai.api_key` → `secrets.dashscope_api_key`，旧配置路径失效。→ 兼容期保留 `ai.api_key` 作为 fallback，打印 deprecation warning
- **[城市名解析不一致]** → 同一个城市名，和风天气和 Open-Meteo 可能解析到不同坐标。→ 对农场场景影响极小（农场位置固定，首次查询后缓存）
- **[和风天气 API 响应格式变更]** → 用 Pydantic model 校验响应，解析失败走兜底
- **[weather.com.cn 预警页面改版]** → 爬虫解析失败时降级为 Open-Meteo 本地阈值检测。预警页面结构简单（纯数据列表），改版概率低。→ 爬虫代码独立于 provider，修复不影响预报功能

## Migration Plan

1. 新增 `SecretsConfig`，保留旧字段兼容（`ai.api_key` 仍可用，优先读 `secrets.dashscope_api_key`）
2. 拆分 `weather_service.py` → `services/weather/` 目录
3. 实现 `QWeatherProvider`
4. 实现 `WeatherStrategy` 路由
5. 改造 `WeatherSkill` 调用 strategy
6. 更新 `config.yaml` 模板，增加 `secrets` 段
7. 移除旧字段兼容（下个版本）
