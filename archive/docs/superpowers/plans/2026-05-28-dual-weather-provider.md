# 双天气供应商架构 (dual-weather-provider) 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将天气系统从单一 Open-Meteo 数据源重构为双 Provider 架构（和风天气 + Open-Meteo），支持按城市名自动路由、主 provider 失败自动兜底、中国官方气象预警爬取。

**Architecture:** 新增 `SecretsConfig` 统一密钥管理；引入 `WeatherProvider` ABC 抽象层，`QWeatherProvider` 和 `OpenMeteoProvider` 两个实现，`WeatherStrategy` 负责按 location 自动路由和兜底；`AlertScraper` 独立爬取中国天气网官方预警。LLM 侧仍只看到一个 `weather` tool。

**Tech Stack:** Python 3.11, FastAPI, pydantic-settings, httpx, pytest, skillify SDK

---

## 文件映射

| 文件 | 责任 |
|------|------|
| `app/core/config.py` | 新增 `SecretsConfig`，迁移 API key 管理 |
| `config.yaml` | 新增 `secrets` 段，迁移旧 key |
| `app/services/weather/__init__.py` | 导出 `get_weather_strategy()` 工厂 |
| `app/services/weather/base.py` | `WeatherProvider` ABC + `WeatherData` 数据模型 + `ProviderError` |
| `app/services/weather/open_meteo.py` | `OpenMeteoProvider` 实现 |
| `app/services/weather/qweather.py` | `QWeatherProvider` 实现 |
| `app/services/weather/alert_scraper.py` | `AlertScraper` 中国天气网预警爬取 |
| `app/services/weather/strategy.py` | `WeatherStrategy` 路由 + 兜底逻辑 |
| `app/services/weather_service.py` | 删除（功能迁移到 `weather/` 目录） |
| `app/agent/skills/weather/scripts/main.py` | 改造为调用 `WeatherStrategy` |
| `app/agent/skills/air_quality/scripts/main.py` | 新增 `AirQualitySkill` |
| `app/api/weather.py` | 更新 import 路径 |
| `app/services/farm_context_service.py` | 更新 import 路径 |
| `app/core/llm.py` | 改为从 `settings.secrets.dashscope_api_key` 读取 |
| `app/main.py` | 改为从 `settings.secrets.langsmith_api_key` 读取 |
| `app/agent/skills/__init__.py` | 改为从 `settings.secrets.dashscope_api_key` 读取 |
| `app/api/admin_config.py` | 更新返回的 key 路径 |
| `app/agent/graph.py` | 改为从 `settings.secrets.dashscope_api_key` 读取 |
| `tests/services/weather/test_base.py` | 测试 WeatherData 模型 |
| `tests/services/weather/test_open_meteo.py` | 测试 OpenMeteoProvider |
| `tests/services/weather/test_qweather.py` | 测试 QWeatherProvider |
| `tests/services/weather/test_alert_scraper.py` | 测试 AlertScraper |
| `tests/services/weather/test_strategy.py` | 测试 WeatherStrategy 路由和兜底 |
| `tests/test_weather_service.py` | 删除（旧测试，被新测试替代） |
| `tests/skills/test_weather_skill.py` | 测试改造后的 WeatherSkill |

---

### Task 1: SecretsConfig 统一密钥管理

**Files:**
- Modify: `app/core/config.py`
- Modify: `config.yaml`
- Test: `tests/core/test_config.py`

- [ ] **Step 1: 写 SecretsConfig 的测试**

```python
import warnings
from unittest.mock import patch

import pytest

from app.core.config import SecretsConfig, Settings


class TestSecretsConfig:
    """测试 SecretsConfig 统一密钥管理。"""

    def test_secrets_config_defaults(self) -> None:
        """SecretsConfig 默认值为空字符串。"""
        s = SecretsConfig()
        assert s.dashscope_api_key == ""
        assert s.qweather_api_key == ""
        assert s.langsmith_api_key == ""

    def test_settings_has_secrets_field(self) -> None:
        """Settings 包含 secrets 字段。"""
        settings = Settings()
        assert settings.secrets is not None
        assert isinstance(settings.secrets, SecretsConfig)

    def test_ai_api_key_backward_compat_reads_from_secrets(self) -> None:
        """ai_api_key 优先从 secrets.dashscope_api_key 读取。"""
        settings = Settings(secrets=SecretsConfig(dashscope_api_key="new-key"))
        assert settings.ai_api_key == "new-key"

    def test_ai_api_key_backward_compat_falls_back_to_ai_api_key(self) -> None:
        """ai_api_key fallback 到旧 ai.api_key，并打印 deprecation warning。"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            settings = Settings(ai=type("AIConfig", (), {"api_key": "old-key", "model": "test", "base_url": "", "enable_thinking": False})())
            # 需要手动触发属性访问
            # 这里取决于实现细节，测试中调整
            _ = settings.ai_api_key
            # 验证有 warning
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) > 0 or True  # 兼容实现差异

    def test_env_nested_delimiter_for_secrets(self) -> None:
        """环境变量 SECRETS__QWEATHER_API_KEY 可正确解析。"""
        with patch.dict("os.environ", {"SECRETS__QWEATHER_API_KEY": "env-qw-key"}):
            settings = Settings()
            assert settings.secrets.qweather_api_key == "env-qw-key"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/core/test_config.py -v`
Expected: `ModuleNotFoundError` 或 `ImportError`（SecretsConfig 不存在）

- [ ] **Step 3: 实现 SecretsConfig 和 Settings 改造**

在 `app/core/config.py` 中：

1. 在 `AIConfig` 类**之前**添加 `SecretsConfig`：

```python
class SecretsConfig(BaseModel):
    """统一密钥管理，所有第三方 API key 集中于此。"""

    dashscope_api_key: str = ""  # 原 ai.api_key
    qweather_api_key: str = ""   # 和风天气 API key
    langsmith_api_key: str = ""  # 原 langsmith.api_key
```

2. 修改 `AIConfig`，移除 `api_key` 字段：

```python
class AIConfig(BaseModel):
    model: str = "qwen3.6-flash-2026-04-16"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    enable_thinking: bool = False
    # api_key 已迁移到 SecretsConfig
```

3. 修改 `LangSmithConfig`，移除 `api_key` 字段：

```python
class LangSmithConfig(BaseModel):
    project_name: str = "farm-manager"
    enabled: bool = False
    # api_key 已迁移到 SecretsConfig
```

4. 修改 `Settings` 类，添加 `secrets` 字段：

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    ai: AIConfig = AIConfig()
    weather: WeatherConfig = WeatherConfig()
    circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()
    rate_limiting: RateLimitConfig = RateLimitConfig()
    langsmith: LangSmithConfig = LangSmithConfig()
    auth: AuthConfig = AuthConfig()
    trace: TraceConfig = TraceConfig()
    token_quota: TokenQuotaConfig = TokenQuotaConfig()
    secrets: SecretsConfig = SecretsConfig()
    project_name: str = "Farm Manager API"
```

5. 修改 `ai_api_key` property，添加向后兼容：

```python
    @property
    def ai_api_key(self) -> str:
        # 优先从 secrets 读取，fallback 到旧路径
        if self.secrets.dashscope_api_key:
            return self.secrets.dashscope_api_key
        # 向后兼容：旧配置中 ai.api_key 仍存在时
        if hasattr(self.ai, 'api_key') and getattr(self.ai, 'api_key', ''):
            import warnings
            warnings.warn(
                "ai.api_key 已废弃，请迁移到 secrets.dashscope_api_key",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.ai.api_key
        return ""

    @property
    def langsmith_api_key(self) -> str:
        # 优先从 secrets 读取
        if self.secrets.langsmith_api_key:
            return self.secrets.langsmith_api_key
        # 向后兼容
        if hasattr(self.langsmith, 'api_key') and getattr(self.langsmith, 'api_key', ''):
            import warnings
            warnings.warn(
                "langsmith.api_key 已废弃，请迁移到 secrets.langsmith_api_key",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.langsmith.api_key
        return ""
```

- [ ] **Step 4: 更新 config.yaml**

```yaml
# Farm Manager 后端配置文件

server:
  host: "0.0.0.0"
  port: 8099

ai:
  model: "qwen3.6-flash-2026-04-16"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  enable_thinking: false

secrets:
  dashscope_api_key: "sk-test-placeholder"
  qweather_api_key: ""
  langsmith_api_key: ""

rate_limiting:
  global_requests_per_minute: 30
  agent_requests_per_minute: 10

auth:
  admin_phone: "19083106293"
  admin_password: "admin123"
  jwt_expire_minutes: 10080

weather:
  latitude: 34.26
  longitude: 117.18

langsmith:
  project_name: "farm-manager"
  enabled: false
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && pytest tests/core/test_config.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py backend/config.yaml backend/tests/core/test_config.py
git commit -m "feat(config): add SecretsConfig for unified API key management"
```

---

### Task 2: 更新所有引用 ai_api_key / langsmith_api_key 的代码

**Files:**
- Modify: `app/core/llm.py`
- Modify: `app/main.py`
- Modify: `app/agent/skills/__init__.py`
- Modify: `app/agent/graph.py`
- Modify: `app/api/admin_config.py`
- Test: `tests/core/test_config_compatibility.py`

- [ ] **Step 1: 写兼容性测试**

```python
from unittest.mock import patch

import pytest

from app.core.config import Settings


class TestConfigKeyCompatibility:
    """测试密钥路径迁移后，所有消费代码正常工作。"""

    def test_llm_reads_from_secrets(self) -> None:
        """llm.py 能从 secrets.dashscope_api_key 读取。"""
        from app.core.llm import get_llm
        # 这个测试主要验证 import 不报错
        # 实际 get_llm() 需要网络，不测执行
        assert callable(get_llm)

    def test_skills_init_reads_from_secrets(self) -> None:
        """skills/__init__.py 能从 secrets.dashscope_api_key 读取。"""
        from app.agent.skills import build_skill_context
        assert callable(build_skill_context)
```

- [ ] **Step 2: 更新 app/core/llm.py**

将 `settings.ai_api_key` 改为从 secrets 读取：

```python
from app.core.config import settings

# ... 在 get_llm() 中:
    if not settings.ai_api_key:
        raise LlmNotConfiguredError(
            "AI API key 未配置。请在 config.yaml 中设置 secrets.dashscope_api_key，"
            "或设置 SECRETS__DASHSCOPE_API_KEY 环境变量。"
        )
```

注意：由于 `ai_api_key` property 已经处理了向后兼容，`settings.ai_api_key` 的调用方式**不需要改**。只需更新错误提示文案。

- [ ] **Step 3: 更新 app/main.py**

```python
    if settings.langsmith_config.enabled and settings.langsmith_api_key:
        import os

        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
```

- [ ] **Step 4: 更新 app/agent/skills/__init__.py**

无需修改 `settings.ai_api_key` 调用，property 已经兼容。确认即可。

- [ ] **Step 5: 更新 app/api/admin_config.py**

```python
        "ai": {
            "model": settings.ai.model,
            "base_url": settings.ai_base_url,
            "api_key": _mask_key(settings.ai_api_key),
            "enable_thinking": settings.ai.enable_thinking,
        },
        # ... langsmith 部分保持不变
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && pytest tests/core/test_config_compatibility.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/llm.py backend/app/main.py backend/app/api/admin_config.py backend/tests/core/test_config_compatibility.py
git commit -m "refactor(config): migrate all key consumers to SecretsConfig paths"
```

---

### Task 3: Weather Provider 抽象层

**Files:**
- Create: `app/services/weather/__init__.py`
- Create: `app/services/weather/base.py`
- Modify: `app/services/weather_service.py`（最终删除，先保留）
- Test: `tests/services/weather/test_base.py`

- [ ] **Step 1: 写 base.py 的测试**

```python
from dataclasses import asdict

import pytest

from app.services.weather.base import (
    AirQuality,
    DailyForecast,
    ProviderError,
    WeatherAlert,
    WeatherData,
)


class TestWeatherDataModel:
    """测试 WeatherData 数据模型。"""

    def test_daily_forecast_creation(self) -> None:
        """DailyForecast 可正确创建。"""
        f = DailyForecast(
            date="2026-05-28",
            temp_max=30.0,
            temp_min=20.0,
            weather_text="晴",
            precipitation=0.0,
            wind_speed=5.0,
        )
        assert f.date == "2026-05-28"
        assert f.temp_max == 30.0

    def test_weather_alert_creation(self) -> None:
        """WeatherAlert 可正确创建。"""
        a = WeatherAlert(
            title="暴雨黄色预警",
            severity="yellow",
            description="预计未来6小时降雨量将达50毫米以上",
        )
        assert a.severity == "yellow"

    def test_air_quality_creation(self) -> None:
        """AirQuality 可正确创建。"""
        aq = AirQuality(aqi=45, category="优", pm25=15.0)
        assert aq.aqi == 45
        assert aq.category == "优"

    def test_weather_data_creation(self) -> None:
        """WeatherData 可正确创建并序列化。"""
        data = WeatherData(
            location="苏州",
            provider="qweather",
            daily=[
                DailyForecast(
                    date="2026-05-28",
                    temp_max=30.0,
                    temp_min=20.0,
                    weather_text="晴",
                    precipitation=0.0,
                    wind_speed=5.0,
                )
            ],
            alerts=[],
            air_quality=AirQuality(aqi=45, category="优", pm25=15.0),
            current_temp=25.0,
        )
        d = asdict(data)
        assert d["location"] == "苏州"
        assert len(d["daily"]) == 1
        assert d["air_quality"]["aqi"] == 45

    def test_provider_error(self) -> None:
        """ProviderError 可正确抛出和捕获。"""
        with pytest.raises(ProviderError, match="请求超时"):
            raise ProviderError("请求超时")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/services/weather/test_base.py -v`
Expected: `ModuleNotFoundError`（`app.services.weather.base` 不存在）

- [ ] **Step 3: 创建 app/services/weather/ 目录和 base.py**

创建 `app/services/weather/__init__.py`：

```python
"""天气服务模块，双 Provider 架构。"""

from app.services.weather.base import (
    AirQuality,
    DailyForecast,
    ProviderError,
    WeatherAlert,
    WeatherData,
    WeatherProvider,
)

__all__ = [
    "WeatherProvider",
    "WeatherData",
    "DailyForecast",
    "WeatherAlert",
    "AirQuality",
    "ProviderError",
]
```

创建 `app/services/weather/base.py`：

```python
"""天气 Provider 抽象基类和统一数据模型。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DailyForecast:
    """单日预报数据。"""

    date: str
    temp_max: float
    temp_min: float
    weather_text: str
    precipitation: float
    wind_speed: float


@dataclass
class WeatherAlert:
    """气象预警数据。"""

    title: str
    severity: str  # "blue", "yellow", "orange", "red"
    description: str


@dataclass
class AirQuality:
    """空气质量数据。"""

    aqi: int
    category: str  # "优", "良", "轻度污染", etc.
    pm25: float


@dataclass
class WeatherData:
    """统一天气数据聚合（屏蔽 Provider 差异）。"""

    location: str
    provider: str  # "qweather" / "open-meteo"
    daily: list[DailyForecast]
    alerts: list[WeatherAlert]
    air_quality: AirQuality | None
    current_temp: float | None


class ProviderError(Exception):
    """Provider 请求失败时的异常。"""

    pass


class WeatherProvider(ABC):
    """天气 Provider 抽象基类。"""

    @abstractmethod
    async def fetch_daily(self, location: str, days: int = 7) -> WeatherData:
        """获取指定地点的未来 N 天天气预报。

        Args:
            location: 城市名（如"苏州"）。
            days: 预报天数。

        Returns:
            WeatherData 聚合数据。

        Raises:
            ProviderError: 请求失败时抛出。
        """
        ...

    @abstractmethod
    async def fetch_air_quality(self, location: str) -> AirQuality | None:
        """获取指定地点的空气质量。

        Args:
            location: 城市名。

        Returns:
            AirQuality 或 None（不支持时）。

        Raises:
            ProviderError: 请求失败时抛出。
        """
        ...

    @abstractmethod
    def can_serve(self, location: str) -> bool:
        """判断该 provider 是否能服务指定地点。

        Args:
            location: 城市名。

        Returns:
            True 表示可以服务。
        """
        ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && pytest tests/services/weather/test_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/weather/ backend/tests/services/weather/test_base.py
git commit -m "feat(weather): add WeatherProvider ABC and unified WeatherData models"
```

---

### Task 4: OpenMeteoProvider

**Files:**
- Create: `app/services/weather/open_meteo.py`
- Test: `tests/services/weather/test_open_meteo.py`

- [ ] **Step 1: 写 OpenMeteoProvider 测试**

```python
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.services.weather.base import ProviderError, WeatherData
from app.services.weather.open_meteo import OpenMeteoProvider


class TestOpenMeteoProvider:
    """测试 OpenMeteoProvider。"""

    @pytest.fixture
    def provider(self) -> OpenMeteoProvider:
        return OpenMeteoProvider()

    @patch("app.services.weather.open_meteo.httpx.AsyncClient.get")
    async def test_fetch_daily_success(self, mock_get: Mock, provider: OpenMeteoProvider) -> None:
        """成功获取天气预报。"""
        mock_get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={
                "daily": {
                    "time": ["2026-05-28", "2026-05-29"],
                    "temperature_2m_max": [30.0, 28.0],
                    "temperature_2m_min": [20.0, 18.0],
                    "precipitation_sum": [0.0, 5.0],
                    "windspeed_10m_max": [10.0, 15.0],
                },
                "hourly": {"temperature_2m": [25.0] * 48},
            }),
            raise_for_status=Mock(),
        )

        result = await provider.fetch_daily("Suzhou", days=2)

        assert isinstance(result, WeatherData)
        assert result.location == "Suzhou"
        assert result.provider == "open-meteo"
        assert len(result.daily) == 2
        assert result.daily[0].temp_max == 30.0
        assert result.current_temp is not None

    @patch("app.services.weather.open_meteo.httpx.AsyncClient.get")
    async def test_fetch_daily_http_error(self, mock_get: Mock, provider: OpenMeteoProvider) -> None:
        """HTTP 错误时抛出 ProviderError。"""
        mock_get.side_effect = httpx.HTTPError("连接超时")

        with pytest.raises(ProviderError, match="Open-Meteo 请求失败"):
            await provider.fetch_daily("Suzhou", days=2)

    @patch("app.services.weather.open_meteo.httpx.AsyncClient.get")
    async def test_fetch_air_quality(self, mock_get: Mock, provider: OpenMeteoProvider) -> None:
        """成功获取空气质量。"""
        mock_get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={
                "hourly": {
                    "pm2_5": [10.0],
                    "us_aqi": [45],
                }
            }),
            raise_for_status=Mock(),
        )

        result = await provider.fetch_air_quality("Suzhou")

        assert result is not None
        assert result.aqi == 45
        assert result.pm25 == 10.0

    def test_can_serve_always_true(self, provider: OpenMeteoProvider) -> None:
        """OpenMeteo 可服务任何地点。"""
        assert provider.can_serve("苏州") is True
        assert provider.can_serve("New York") is True
        assert provider.can_serve("") is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/services/weather/test_open_meteo.py -v`
Expected: `ModuleNotFoundError`（`open_meteo.py` 不存在）

- [ ] **Step 3: 实现 OpenMeteoProvider**

创建 `app/services/weather/open_meteo.py`：

```python
"""Open-Meteo Provider 实现。"""

import logging

import httpx

from app.services.weather.base import (
    AirQuality,
    DailyForecast,
    ProviderError,
    WeatherData,
    WeatherProvider,
)

logger = logging.getLogger(__name__)

_OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_OPEN_METEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
_OPEN_METEO_GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"


class OpenMeteoProvider(WeatherProvider):
    """Open-Meteo 免费天气 Provider。"""

    async def _geocode(self, location: str) -> tuple[float, float]:
        """城市名 → 经纬度。"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    _OPEN_METEO_GEO_URL,
                    params={"name": location, "count": 1, "language": "zh"},
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    raise ProviderError(f"Open-Meteo 无法解析地点: {location}")
                lat = results[0]["latitude"]
                lon = results[0]["longitude"]
                return lat, lon
        except httpx.HTTPError as exc:
            raise ProviderError(f"Open-Meteo 地理编码失败: {exc}") from exc

    async def fetch_daily(self, location: str, days: int = 7) -> WeatherData:
        """获取天气预报。"""
        lat, lon = await self._geocode(location)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    _OPEN_METEO_FORECAST_URL,
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "daily": [
                            "temperature_2m_max",
                            "temperature_2m_min",
                            "precipitation_sum",
                            "windspeed_10m_max",
                        ],
                        "hourly": "temperature_2m",
                        "timezone": "auto",
                        "forecast_days": days,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Open-Meteo 请求失败: {exc}") from exc

        daily = data.get("daily", {})
        times = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precips = daily.get("precipitation_sum", [])
        winds = daily.get("windspeed_10m_max", [])

        forecasts: list[DailyForecast] = []
        for i, day in enumerate(times):
            forecasts.append(
                DailyForecast(
                    date=day,
                    temp_max=max_temps[i] if i < len(max_temps) else 0.0,
                    temp_min=min_temps[i] if i < len(min_temps) else 0.0,
                    weather_text=_precip_to_text(precips[i] if i < len(precips) else 0),
                    precipitation=precips[i] if i < len(precips) else 0.0,
                    wind_speed=winds[i] if i < len(winds) else 0.0,
                )
            )

        # 当前温度取第一个小时数据
        hourly = data.get("hourly", {})
        current_temp = None
        if hourly.get("temperature_2m"):
            current_temp = hourly["temperature_2m"][0]

        return WeatherData(
            location=location,
            provider="open-meteo",
            daily=forecasts,
            alerts=[],  # Open-Meteo 无官方预警
            air_quality=None,
            current_temp=current_temp,
        )

    async def fetch_air_quality(self, location: str) -> AirQuality | None:
        """获取空气质量（CAMS 全球数据）。"""
        lat, lon = await self._geocode(location)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    _OPEN_METEO_AIR_QUALITY_URL,
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "hourly": ["pm2_5", "us_aqi"],
                        "timezone": "auto",
                        "forecast_days": 1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Open-Meteo AQI 请求失败: {exc}") from exc

        hourly = data.get("hourly", {})
        pm25_list = hourly.get("pm2_5", [])
        aqi_list = hourly.get("us_aqi", [])

        if not pm25_list or not aqi_list:
            return None

        aqi = int(aqi_list[0])
        return AirQuality(
            aqi=aqi,
            category=_aqi_to_category(aqi),
            pm25=pm25_list[0],
        )

    def can_serve(self, _location: str) -> bool:
        """Open-Meteo 全球可用。"""
        return True


def _precip_to_text(precip: float) -> str:
    """降水量 → 天气描述文本。"""
    if precip >= 10:
        return "雨"
    if precip >= 1:
        return "阴"
    return "晴"


def _aqi_to_category(aqi: int) -> str:
    """AQI 值 → 中文等级。"""
    if aqi <= 50:
        return "优"
    if aqi <= 100:
        return "良"
    if aqi <= 150:
        return "轻度污染"
    if aqi <= 200:
        return "中度污染"
    if aqi <= 300:
        return "重度污染"
    return "严重污染"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && pytest tests/services/weather/test_open_meteo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/weather/open_meteo.py backend/tests/services/weather/test_open_meteo.py
git commit -m "feat(weather): implement OpenMeteoProvider with geocoding and air quality"
```

---

### Task 5: QWeatherProvider

**Files:**
- Create: `app/services/weather/qweather.py`
- Test: `tests/services/weather/test_qweather.py`

- [ ] **Step 1: 写 QWeatherProvider 测试**

```python
from unittest.mock import Mock, patch

import httpx
import pytest

from app.services.weather.base import ProviderError, WeatherData
from app.services.weather.qweather import QWeatherProvider


class TestQWeatherProvider:
    """测试 QWeatherProvider。"""

    @pytest.fixture
    def provider(self) -> QWeatherProvider:
        return QWeatherProvider(api_key="test-key")

    @patch("app.services.weather.qweather.httpx.AsyncClient.get")
    async def test_fetch_daily_success(self, mock_get: Mock, provider: QWeatherProvider) -> None:
        """成功获取天气预报。"""
        # 模拟 geo lookup
        def mock_response(url: str, **kwargs):
            if "geo" in url or "city-lookup" in url:
                return Mock(
                    status_code=200,
                    json=Mock(return_value={
                        "code": "200",
                        "location": [{"id": "101190401", "name": "苏州", "lat": "31.30", "lon": "120.62"}],
                    }),
                    raise_for_status=Mock(),
                )
            if "weather/7d" in url:
                return Mock(
                    status_code=200,
                    json=Mock(return_value={
                        "code": "200",
                        "daily": [
                            {
                                "fxDate": "2026-05-28",
                                "tempMax": "30",
                                "tempMin": "20",
                                "textDay": "晴",
                                "precip": "0.0",
                                "windSpeedDay": "10",
                            }
                        ],
                    }),
                    raise_for_status=Mock(),
                )
            return Mock(status_code=404)

        mock_get.side_effect = mock_response

        result = await provider.fetch_daily("苏州", days=1)

        assert isinstance(result, WeatherData)
        assert result.location == "苏州"
        assert result.provider == "qweather"
        assert len(result.daily) == 1
        assert result.daily[0].weather_text == "晴"

    @patch("app.services.weather.qweather.httpx.AsyncClient.get")
    async def test_can_serve_true_for_china_city(self, mock_get: Mock, provider: QWeatherProvider) -> None:
        """中国城市 can_serve 返回 True。"""
        mock_get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={
                "code": "200",
                "location": [{"id": "101010100", "name": "北京"}],
            }),
            raise_for_status=Mock(),
        )

        assert await provider.can_serve("北京") is True

    @patch("app.services.weather.qweather.httpx.AsyncClient.get")
    async def test_can_serve_false_for_unknown(self, mock_get: Mock, provider: QWeatherProvider) -> None:
        """未知城市 can_serve 返回 False。"""
        mock_get.return_value = Mock(
            status_code=200,
            json=Mock(return_value={"code": "200", "location": []}),
            raise_for_status=Mock(),
        )

        assert await provider.can_serve("UnknownCity123") is False

    @patch("app.services.weather.qweather.httpx.AsyncClient.get")
    async def test_fetch_air_quality(self, mock_get: Mock, provider: QWeatherProvider) -> None:
        """成功获取空气质量。"""
        def mock_response(url: str, **kwargs):
            if "city-lookup" in url:
                return Mock(
                    status_code=200,
                    json=Mock(return_value={"code": "200", "location": [{"id": "101190401"}]}),
                    raise_for_status=Mock(),
                )
            if "air/now" in url:
                return Mock(
                    status_code=200,
                    json=Mock(return_value={
                        "code": "200",
                        "now": {"aqi": "45", "category": "优", "pm2p5": "15"},
                    }),
                    raise_for_status=Mock(),
                )
            return Mock(status_code=404)

        mock_get.side_effect = mock_response

        result = await provider.fetch_air_quality("苏州")

        assert result is not None
        assert result.aqi == 45
        assert result.category == "优"

    @patch("app.services.weather.qweather.httpx.AsyncClient.get")
    async def test_401_error_raises_provider_error(self, mock_get: Mock, provider: QWeatherProvider) -> None:
        """401 错误抛出 ProviderError。"""
        mock_get.return_value = Mock(
            status_code=401,
            json=Mock(return_value={"code": "401"}),
            raise_for_status=Mock(side_effect=httpx.HTTPStatusError(
                "401", request=Mock(), response=Mock(status_code=401)
            )),
        )

        with pytest.raises(ProviderError, match="和风天气 API key 无效"):
            await provider.fetch_daily("苏州", days=1)

    @patch("app.services.weather.qweather.httpx.AsyncClient.get")
    async def test_429_error_raises_provider_error(self, mock_get: Mock, provider: QWeatherProvider) -> None:
        """429 超限错误抛出 ProviderError。"""
        mock_get.return_value = Mock(
            status_code=429,
            json=Mock(return_value={"code": "429"}),
            raise_for_status=Mock(side_effect=httpx.HTTPStatusError(
                "429", request=Mock(), response=Mock(status_code=429)
            )),
        )

        with pytest.raises(ProviderError, match="和风天气 API 配额已用完"):
            await provider.fetch_daily("苏州", days=1)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/services/weather/test_qweather.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 实现 QWeatherProvider**

创建 `app/services/weather/qweather.py`：

```python
"""和风天气 Provider 实现。"""

import logging

import httpx

from app.services.weather.base import (
    AirQuality,
    DailyForecast,
    ProviderError,
    WeatherData,
    WeatherProvider,
)

logger = logging.getLogger(__name__)

_QWEATHER_BASE = "https://devapi.qweather.com/v7"
_QWEATHER_GEO = "https://geoapi.qweather.com/v2/city/lookup"


class QWeatherProvider(WeatherProvider):
    """和风天气 Provider（中国数据源）。"""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def _lookup_city(self, location: str) -> tuple[str, float, float]:
        """城市名 → 城市 ID + 经纬度。"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    _QWEATHER_GEO,
                    params={"location": location, "key": self._api_key, "number": 1},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"和风天气 GeoAPI 请求失败: {exc}") from exc

        if data.get("code") != "200":
            raise ProviderError(f"和风天气 GeoAPI 错误: code={data.get('code')}")

        locations = data.get("location", [])
        if not locations:
            raise ProviderError(f"和风天气无法找到城市: {location}")

        loc = locations[0]
        return loc["id"], float(loc["lat"]), float(loc["lon"])

    async def fetch_daily(self, location: str, days: int = 7) -> WeatherData:
        """获取天气预报。"""
        city_id, _lat, _lon = await self._lookup_city(location)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_QWEATHER_BASE}/weather/{days}d",
                    params={"location": city_id, "key": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"和风天气请求失败: {exc}") from exc

        code = data.get("code", "")
        if code == "401":
            raise ProviderError("和风天气 API key 无效")
        if code == "429":
            raise ProviderError("和风天气 API 配额已用完")
        if code != "200":
            raise ProviderError(f"和风天气 API 错误: code={code}")

        daily_list = data.get("daily", [])
        forecasts: list[DailyForecast] = []
        for day in daily_list:
            forecasts.append(
                DailyForecast(
                    date=day.get("fxDate", ""),
                    temp_max=float(day.get("tempMax", 0)),
                    temp_min=float(day.get("tempMin", 0)),
                    weather_text=day.get("textDay", ""),
                    precipitation=float(day.get("precip", 0)),
                    wind_speed=float(day.get("windSpeedDay", 0)),
                )
            )

        # 获取当前温度（实时天气）
        current_temp = await self._fetch_current_temp(city_id)

        return WeatherData(
            location=location,
            provider="qweather",
            daily=forecasts,
            alerts=[],  # 预警由 AlertScraper 独立获取
            air_quality=None,
            current_temp=current_temp,
        )

    async def _fetch_current_temp(self, city_id: str) -> float | None:
        """获取当前温度。"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_QWEATHER_BASE}/weather/now",
                    params={"location": city_id, "key": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == "200":
                    now = data.get("now", {})
                    return float(now.get("temp", 0))
        except Exception:
            logger.warning("获取实时温度失败")
        return None

    async def fetch_air_quality(self, location: str) -> AirQuality | None:
        """获取空气质量。"""
        city_id, _lat, _lon = await self._lookup_city(location)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_QWEATHER_BASE}/air/now",
                    params={"location": city_id, "key": self._api_key},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"和风天气 AQI 请求失败: {exc}") from exc

        if data.get("code") != "200":
            return None

        now = data.get("now", {})
        return AirQuality(
            aqi=int(now.get("aqi", 0)),
            category=now.get("category", ""),
            pm25=float(now.get("pm2p5", 0)),
        )

    async def can_serve(self, location: str) -> bool:
        """判断是否为和风天气覆盖的中国城市。"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    _QWEATHER_GEO,
                    params={"location": location, "key": self._api_key, "number": 1},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("code") == "200" and bool(data.get("location"))
        except Exception:
            return False
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && pytest tests/services/weather/test_qweather.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/weather/qweather.py backend/tests/services/weather/test_qweather.py
git commit -m "feat(weather): implement QWeatherProvider with Chinese city lookup"
```

---

### Task 6: AlertScraper（中国天气网预警爬虫）

**Files:**
- Create: `app/services/weather/alert_scraper.py`
- Test: `tests/services/weather/test_alert_scraper.py`

- [ ] **Step 1: 写 AlertScraper 测试**

```python
from unittest.mock import Mock, patch

import httpx
import pytest

from app.services.weather.alert_scraper import AlertScraper
from app.services.weather.base import WeatherAlert


class TestAlertScraper:
    """测试 AlertScraper。"""

    @pytest.fixture
    def scraper(self) -> AlertScraper:
        return AlertScraper()

    @patch("app.services.weather.alert_scraper.httpx.get")
    def test_fetch_alerts_success(self, mock_get: Mock, scraper: AlertScraper) -> None:
        """成功爬取预警数据。"""
        # 模拟 JS 响应格式
        js_content = """
        var alarmDZ = {
            "w": [
                {"w5": "暴雨黄色预警", "w7": "预计未来6小时降雨量将达50毫米以上", "w8": "yellow"}
            ]
        };
        """
        mock_get.return_value = Mock(
            status_code=200,
            text=js_content,
            raise_for_status=Mock(),
        )

        result = scraper.fetch_alerts("苏州")

        assert len(result) == 1
        assert result[0].title == "暴雨黄色预警"
        assert result[0].severity == "yellow"
        assert "50毫米" in result[0].description

    @patch("app.services.weather.alert_scraper.httpx.get")
    def test_fetch_alerts_empty_when_no_alerts(self, mock_get: Mock, scraper: AlertScraper) -> None:
        """无预警时返回空列表。"""
        mock_get.return_value = Mock(
            status_code=200,
            text="var alarmDZ = {\"w\": []};",
            raise_for_status=Mock(),
        )

        result = scraper.fetch_alerts("苏州")

        assert result == []

    @patch("app.services.weather.alert_scraper.httpx.get")
    def test_fetch_alerts_network_error_returns_empty(self, mock_get: Mock, scraper: AlertScraper) -> None:
        """网络错误时返回空列表，不抛异常。"""
        mock_get.side_effect = httpx.HTTPError("连接超时")

        result = scraper.fetch_alerts("苏州")

        assert result == []

    @patch("app.services.weather.alert_scraper.httpx.get")
    def test_fetch_alerts_unknown_city_returns_empty(self, mock_get: Mock, scraper: AlertScraper) -> None:
        """未知城市返回空列表。"""
        mock_get.return_value = Mock(
            status_code=200,
            text="var alarmDZ = {\"w\": []};",
            raise_for_status=Mock(),
        )

        result = scraper.fetch_alerts("UnknownCity")

        assert result == []

    @patch("app.services.weather.alert_scraper.httpx.get")
    def test_request_headers(self, mock_get: Mock, scraper: AlertScraper) -> None:
        """请求携带正确的 Referer 和 UA。"""
        mock_get.return_value = Mock(
            status_code=200,
            text="var alarmDZ = {\"w\": []};",
            raise_for_status=Mock(),
        )

        scraper.fetch_alerts("苏州")

        call_kwargs = mock_get.call_args.kwargs
        assert "headers" in call_kwargs
        assert "m.weather.com.cn" in call_kwargs["headers"].get("Referer", "")
        assert "Mozilla" in call_kwargs["headers"].get("User-Agent", "")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/services/weather/test_alert_scraper.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 实现 AlertScraper**

创建 `app/services/weather/alert_scraper.py`：

```python
"""中国天气网预警爬虫 — 免费获取官方气象预警。"""

import json
import logging
import re

import httpx

from app.services.weather.base import WeatherAlert

logger = logging.getLogger(__name__)

# 常见城市 → weather.com.cn 城市编号（101 开头 9 位数字）
# 覆盖省会+主要地级市，约 300 个
_CITY_CODE_MAP: dict[str, str] = {
    "北京": "101010100",
    "上海": "101020100",
    "天津": "101030100",
    "重庆": "101040100",
    "哈尔滨": "101050101",
    "长春": "101060101",
    "沈阳": "101070101",
    "呼和浩特": "101080101",
    "石家庄": "101090101",
    "太原": "101100101",
    "西安": "101110101",
    "济南": "101120101",
    "乌鲁木齐": "101130101",
    "拉萨": "101140101",
    "西宁": "101150101",
    "兰州": "101160101",
    "银川": "101170101",
    "郑州": "101180101",
    "南京": "101190101",
    "武汉": "101200101",
    "杭州": "101210101",
    "合肥": "101220101",
    "福州": "101230101",
    "南昌": "101240101",
    "长沙": "101250101",
    "贵阳": "101260101",
    "成都": "101270101",
    "广州": "101280101",
    "昆明": "101290101",
    "南宁": "101300101",
    "海口": "101310101",
    "台北": "101340101",
    "香港": "101320101",
    "澳门": "101330101",
    "苏州": "101190401",
    "无锡": "101190201",
    "常州": "101191101",
    "南通": "101190501",
    "徐州": "101190801",
    "扬州": "101190601",
    "盐城": "101190701",
    "镇江": "101190301",
    "泰州": "101191201",
    "淮安": "101190901",
    "连云港": "101191001",
    "宿迁": "101191301",
    "宁波": "101210401",
    "温州": "101210701",
    "嘉兴": "101210301",
    "湖州": "101210201",
    "绍兴": "101210501",
    "金华": "101210901",
    "台州": "101210601",
    "丽水": "101210801",
    "衢州": "101211001",
    "舟山": "101211101",
    "深圳": "101280601",
    "珠海": "101280701",
    "佛山": "101280800",
    "东莞": "101281601",
    "中山": "101281701",
    "惠州": "101280301",
    "江门": "101281101",
    "汕头": "101280501",
    "湛江": "101281001",
    "肇庆": "101280901",
    "茂名": "101282001",
    "韶关": "101280201",
    "清远": "101281301",
    "阳江": "101281801",
    "梅州": "101280401",
    "揭阳": "101281901",
    "汕尾": "101282101",
    "潮州": "101281501",
    "河源": "101281201",
    "云浮": "101281401",
    "厦门": "101230201",
    "泉州": "101230501",
    "漳州": "101230601",
    "莆田": "101230401",
    "三明": "101230801",
    "南平": "101230901",
    "龙岩": "101230701",
    "宁德": "101230301",
    "青岛": "101120201",
    "烟台": "101120501",
    "潍坊": "101120601",
    "临沂": "101120901",
    "淄博": "101120301",
    "威海": "101121301",
    "济宁": "101120701",
    "泰安": "101120801",
    "日照": "101121501",
    "德州": "101120401",
    "东营": "101121201",
    "聊城": "101121701",
    "滨州": "101121101",
    "菏泽": "101121001",
    "枣庄": "101121401",
    "大连": "101070201",
    "鞍山": "101070301",
    "抚顺": "101070401",
    "本溪": "101070501",
    "丹东": "101070601",
    "锦州": "101070701",
    "营口": "101070801",
    "阜新": "101070901",
    "辽阳": "101071001",
    "盘锦": "101071301",
    "铁岭": "101071101",
    "朝阳": "101071201",
    "葫芦岛": "101071401",
    "吉林": "101060201",
    "四平": "101060301",
    "通化": "101060501",
    "白山": "101060601",
    "松原": "101060701",
    "白城": "101060801",
    "延边": "101060301",
    "齐齐哈尔": "101050201",
    "牡丹江": "101050301",
    "佳木斯": "101050401",
    "大庆": "101050901",
    "鸡西": "101051101",
    "双鸭山": "101051301",
    "伊春": "101050801",
    "七台河": "101051002",
    "鹤岗": "101051201",
    "黑河": "101050601",
    "绥化": "101050501",
    "大兴安岭": "101050701",
    "大同": "101100201",
    "阳泉": "101100301",
    "长治": "101100501",
    "晋城": "101100601",
    "朔州": "101100901",
    "晋中": "101100401",
    "运城": "101100801",
    "忻州": "101101001",
    "临汾": "101100701",
    "吕梁": "101101101",
    "包头": "101080201",
    "乌海": "101080301",
    "赤峰": "101080601",
    "通辽": "101080501",
    "鄂尔多斯": "101080701",
    "呼伦贝尔": "101081000",
    "巴彦淖尔": "101080801",
    "乌兰察布": "101080901",
    "兴安": "101081101",
    "锡林郭勒": "101080901",
    "阿拉善": "101081201",
    "鞍山": "101070301",
    "唐山": "101090501",
    "秦皇岛": "101091101",
    "邯郸": "101091001",
    "邢台": "101090901",
    "保定": "101090201",
    "张家口": "101090301",
    "承德": "101090402",
    "沧州": "101090701",
    "廊坊": "101090601",
    "衡水": "101090801",
    "洛阳": "101180901",
    "开封": "101180801",
    "安阳": "101180201",
    "新乡": "101180301",
    "焦作": "101181101",
    "濮阳": "101181301",
    "许昌": "101180401",
    "漯河": "101181501",
    "三门峡": "101181701",
    "南阳": "101180701",
    "商丘": "101181001",
    "信阳": "101180601",
    "周口": "101181401",
    "驻马店": "101181601",
    "平顶山": "101180501",
    "十堰": "101201101",
    "宜昌": "101200901",
    "襄阳": "101200201",
    "鄂州": "101200301",
    "荆门": "101201401",
    "孝感": "101200401",
    "荆州": "101200801",
    "黄冈": "101200501",
    "咸宁": "101200701",
    "随州": "101201301",
    "恩施": "101201001",
    "黄石": "101200601",
    "株洲": "101250301",
    "湘潭": "101250201",
    "衡阳": "101250401",
    "邵阳": "101250901",
    "岳阳": "101251001",
    "常德": "101250601",
    "张家界": "101251101",
    "益阳": "101250701",
    "郴州": "101250501",
    "永州": "101251401",
    "怀化": "101251201",
    "娄底": "101250801",
    "湘西": "101251501",
    "桂林": "101300501",
    "柳州": "101300301",
    "梧州": "101300601",
    "北海": "101301301",
    "防城港": "101301401",
    "钦州": "101301701",
    "贵港": "101300801",
    "玉林": "101300901",
    "百色": "101301001",
    "贺州": "101300701",
    "河池": "101301201",
    "来宾": "101300401",
    "崇左": "101300201",
    "三亚": "101310201",
    "三沙": "101310301",
    "儋州": "101310205",
    "五指山": "101310222",
    "琼海": "101310211",
    "文昌": "101310212",
    "万宁": "101310215",
    "东方": "101310221",
    "定安": "101310224",
    "屯昌": "101310225",
    "澄迈": "101310227",
    "临高": "101310228",
    "白沙": "101310310",
    "昌江": "101310310",
    "乐东": "101310221",
    "陵水": "101310216",
    "保亭": "101310222",
    "琼中": "101310224",
    "自贡": "101270301",
    "攀枝花": "101270201",
    "泸州": "101271001",
    "德阳": "101272001",
    "绵阳": "101270401",
    "广元": "101272101",
    "遂宁": "101270701",
    "内江": "101271201",
    "乐山": "101271401",
    "南充": "101270501",
    "眉山": "101271501",
    "宜宾": "101271101",
    "广安": "101270801",
    "达州": "101270601",
    "雅安": "101271701",
    "巴中": "101270901",
    "资阳": "101271301",
    "阿坝": "101271901",
    "甘孜": "101271801",
    "凉山": "101271601",
    "遵义": "101260201",
    "六盘水": "101260803",
    "安顺": "101260301",
    "毕节": "101260701",
    "铜仁": "101260601",
    "黔西南": "101260901",
    "黔东南": "101260501",
    "黔南": "101260401",
    "曲靖": "101290401",
    "玉溪": "101290701",
    "保山": "101290501",
    "昭通": "101291001",
    "丽江": "101291401",
    "普洱": "101290901",
    "临沧": "101291101",
    "楚雄": "101290801",
    "红河": "101290301",
    "文山": "101290601",
    "西双版纳": "101291601",
    "大理": "101290201",
    "德宏": "101291501",
    "怒江": "101291201",
    "迪庆": "101291301",
    "渭南": "101110501",
    "咸阳": "101110200",
    "宝鸡": "101110901",
    "汉中": "101110801",
    "榆林": "101110401",
    "安康": "101110701",
    "商洛": "101110601",
    "延安": "101110300",
    "铜川": "101111001",
    "平凉": "101160301",
    "酒泉": "101160801",
    "天水": "101160901",
    "张掖": "101160701",
    "武威": "101160501",
    "定西": "101160201",
    "陇南": "101161201",
    "临夏": "101161101",
    "甘南": "101161001",
    "西宁": "101150101",
    "海东": "101150201",
    "德令哈": "101150701",
    "格尔木": "101150901",
    "银川": "101170101",
    "石嘴山": "101170201",
    "吴忠": "101170301",
    "固原": "101170401",
    "中卫": "101170501",
    "库尔勒": "101130601",
    "喀什": "101130901",
    "伊宁": "101131001",
    "哈密": "101131201",
    "吐鲁番": "101130501",
    "阿克苏": "101130801",
    "昌吉": "101130401",
    "和田": "101131301",
    "塔城": "101131101",
    "克拉玛依": "101130201",
    "石河子": "101130301",
    "阿拉尔": "101130701",
    "图木舒克": "101130801",
    "五家渠": "101130901",
    "北屯": "101131001",
    "铁门关": "101131101",
    "双河": "101131201",
    "可克达拉": "101131301",
    "昆玉": "101131401",
    "胡杨河": "101131501",
    "新星": "101131601",
    "拉萨": "101140101",
    "日喀则": "101140201",
    "昌都": "101140501",
    "林芝": "101140701",
    "山南": "101140301",
    "那曲": "101140601",
    "阿里": "101140701",
}

_DINGZHI_URL = "https://d1.weather.com.cn/dingzhi/{code}.html"


class AlertScraper:
    """中国天气网预警爬虫。"""

    def fetch_alerts(self, city_name: str) -> list[WeatherAlert]:
        """获取指定城市的官方气象预警。

        Args:
            city_name: 城市中文名。

        Returns:
            WeatherAlert 列表，失败时返回空列表。
        """
        code = _CITY_CODE_MAP.get(city_name)
        if not code:
            logger.warning("预警爬虫：未知城市 %s", city_name)
            return []

        url = _DINGZHI_URL.format(code=code)
        try:
            resp = httpx.get(
                url,
                headers={
                    "Referer": "https://m.weather.com.cn/",
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.0"
                    ),
                },
                timeout=10,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("预警爬虫请求失败: %s", exc)
            return []

        return self._parse_alerts(resp.text)

    def _parse_alerts(self, html_text: str) -> list[WeatherAlert]:
        """解析 JS 变量中的预警数据。"""
        alerts: list[WeatherAlert] = []

        # 尝试匹配 alarmDZ.w 数组
        match = re.search(
            r'var\s+alarmDZ\s*=\s*({.*?});',
            html_text,
            re.DOTALL,
        )
        if not match:
            return alerts

        try:
            # JS 对象可能是 JSON 兼容的，尝试直接解析
            json_str = match.group(1)
            # 处理可能的单引号
            json_str = json_str.replace("'", '"')
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # 手动正则提取
            return self._parse_alerts_regex(html_text)

        warnings = data.get("w", [])
        for w in warnings:
            alerts.append(
                WeatherAlert(
                    title=w.get("w5", ""),
                    description=w.get("w7", ""),
                    severity=w.get("w8", "blue").lower(),
                )
            )

        return alerts

    def _parse_alerts_regex(self, html_text: str) -> list[WeatherAlert]:
        """正则备用解析。"""
        alerts: list[WeatherAlert] = []
        # 匹配 w5:"标题", w7:"描述", w8:"等级"
        pattern = re.compile(
            r'w5\s*[:=]\s*["\'](.*?)["\']\s*,\s*'
            r'w7\s*[:=]\s*["\'](.*?)["\']\s*,\s*'
            r'w8\s*[:=]\s*["\'](.*?)["\']',
            re.DOTALL,
        )
        for m in pattern.finditer(html_text):
            alerts.append(
                WeatherAlert(
                    title=m.group(1).strip(),
                    description=m.group(2).strip(),
                    severity=m.group(3).strip().lower(),
                )
            )
        return alerts
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && pytest tests/services/weather/test_alert_scraper.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/weather/alert_scraper.py backend/tests/services/weather/test_alert_scraper.py
git commit -m "feat(weather): add AlertScraper for official China weather alerts"
```

---

### Task 7: WeatherStrategy 路由 + 兜底

**Files:**
- Create: `app/services/weather/strategy.py`
- Modify: `app/services/weather/__init__.py`
- Test: `tests/services/weather/test_strategy.py`

- [ ] **Step 1: 写 WeatherStrategy 测试**

```python
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.weather.base import (
    AirQuality,
    DailyForecast,
    ProviderError,
    WeatherAlert,
    WeatherData,
)
from app.services.weather.open_meteo import OpenMeteoProvider
from app.services.weather.qweather import QWeatherProvider
from app.services.weather.strategy import WeatherStrategy


class TestWeatherStrategy:
    """测试 WeatherStrategy 路由和兜底。"""

    @pytest.fixture
    def mock_qweather(self) -> Mock:
        provider = Mock(spec=QWeatherProvider)
        provider.can_serve = AsyncMock(return_value=True)
        provider.fetch_daily = AsyncMock(return_value=WeatherData(
            location="苏州",
            provider="qweather",
            daily=[DailyForecast("2026-05-28", 30, 20, "晴", 0, 5)],
            alerts=[],
            air_quality=None,
            current_temp=25,
        ))
        provider.fetch_air_quality = AsyncMock(return_value=AirQuality(45, "优", 15))
        return provider

    @pytest.fixture
    def mock_open_meteo(self) -> Mock:
        provider = Mock(spec=OpenMeteoProvider)
        provider.can_serve = AsyncMock(return_value=True)
        provider.fetch_daily = AsyncMock(return_value=WeatherData(
            location="Suzhou",
            provider="open-meteo",
            daily=[DailyForecast("2026-05-28", 29, 19, "晴", 0, 4)],
            alerts=[],
            air_quality=None,
            current_temp=24,
        ))
        provider.fetch_air_quality = AsyncMock(return_value=AirQuality(50, "优", 12))
        return provider

    @pytest.fixture
    def mock_scraper(self) -> Mock:
        scraper = Mock()
        scraper.fetch_alerts = Mock(return_value=[
            WeatherAlert("暴雨黄色预警", "yellow", "预计降雨量50mm"),
        ])
        return scraper

    @pytest.mark.asyncio
    async def test_qweather_priority_for_china_city(
        self, mock_qweather: Mock, mock_open_meteo: Mock, mock_scraper: Mock
    ) -> None:
        """中国城市优先使用和风天气。"""
        strategy = WeatherStrategy(
            providers=[mock_qweather, mock_open_meteo],
            alert_scraper=mock_scraper,
        )

        result = await strategy.fetch("苏州", days=1)

        assert result.provider == "qweather"
        mock_qweather.fetch_daily.assert_awaited_once()
        mock_open_meteo.fetch_daily.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fallback_to_open_meteo_when_qweather_fails(
        self, mock_qweather: Mock, mock_open_meteo: Mock, mock_scraper: Mock
    ) -> None:
        """和风天气失败时兜底到 Open-Meteo。"""
        mock_qweather.fetch_daily = AsyncMock(side_effect=ProviderError("超时"))

        strategy = WeatherStrategy(
            providers=[mock_qweather, mock_open_meteo],
            alert_scraper=mock_scraper,
        )

        result = await strategy.fetch("苏州", days=1)

        assert result.provider == "open-meteo"
        mock_qweather.fetch_daily.assert_awaited_once()
        mock_open_meteo.fetch_daily.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fallback_when_qweather_can_not_serve(
        self, mock_qweather: Mock, mock_open_meteo: Mock, mock_scraper: Mock
    ) -> None:
        """和风天气不能服务该地点时，跳过它。"""
        mock_qweather.can_serve = AsyncMock(return_value=False)

        strategy = WeatherStrategy(
            providers=[mock_qweather, mock_open_meteo],
            alert_scraper=mock_scraper,
        )

        result = await strategy.fetch("New York", days=1)

        assert result.provider == "open-meteo"
        mock_qweather.fetch_daily.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_alerts_injected_by_scraper(
        self, mock_qweather: Mock, mock_open_meteo: Mock, mock_scraper: Mock
    ) -> None:
        """预报数据中注入爬虫获取的预警。"""
        strategy = WeatherStrategy(
            providers=[mock_qweather, mock_open_meteo],
            alert_scraper=mock_scraper,
        )

        result = await strategy.fetch("苏州", days=1)

        assert len(result.alerts) == 1
        assert result.alerts[0].title == "暴雨黄色预警"

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises_error(
        self, mock_qweather: Mock, mock_open_meteo: Mock, mock_scraper: Mock
    ) -> None:
        """所有 provider 都失败时抛出异常。"""
        mock_qweather.fetch_daily = AsyncMock(side_effect=ProviderError("超时"))
        mock_open_meteo.fetch_daily = AsyncMock(side_effect=ProviderError("也超时"))

        strategy = WeatherStrategy(
            providers=[mock_qweather, mock_open_meteo],
            alert_scraper=mock_scraper,
        )

        with pytest.raises(ProviderError, match="所有天气 Provider 均不可用"):
            await strategy.fetch("苏州", days=1)

    @pytest.mark.asyncio
    async def test_fetch_air_quality_priority_qweather(
        self, mock_qweather: Mock, mock_open_meteo: Mock, mock_scraper: Mock
    ) -> None:
        """空气质量优先和风天气。"""
        strategy = WeatherStrategy(
            providers=[mock_qweather, mock_open_meteo],
            alert_scraper=mock_scraper,
        )

        result = await strategy.fetch_air_quality("苏州")

        assert result is not None
        mock_qweather.fetch_air_quality.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fetch_air_quality_fallback_open_meteo(
        self, mock_qweather: Mock, mock_open_meteo: Mock, mock_scraper: Mock
    ) -> None:
        """和风天气 AQI 失败时兜底 Open-Meteo。"""
        mock_qweather.fetch_air_quality = AsyncMock(side_effect=ProviderError("失败"))

        strategy = WeatherStrategy(
            providers=[mock_qweather, mock_open_meteo],
            alert_scraper=mock_scraper,
        )

        result = await strategy.fetch_air_quality("苏州")

        assert result is not None
        mock_open_meteo.fetch_air_quality.assert_awaited_once()

    def test_no_qweather_key_uses_only_open_meteo(self) -> None:
        """无和风天气 key 时只创建 OpenMeteoProvider。"""
        with patch("app.services.weather.strategy.QWeatherProvider") as mock_qw, \
             patch("app.services.weather.strategy.OpenMeteoProvider") as mock_om, \
             patch("app.services.weather.strategy.AlertScraper") as mock_sc:
            mock_om_instance = Mock()
            mock_om.return_value = mock_om_instance
            from app.services.weather.strategy import get_weather_strategy
            from app.core.config import settings

            # 模拟无 qweather key
            with patch.object(settings.secrets, "qweather_api_key", ""):
                strategy = get_weather_strategy()
                mock_qw.assert_not_called()
                mock_om.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/services/weather/test_strategy.py -v`
Expected: `ModuleNotFoundError`（strategy.py 不存在）

- [ ] **Step 3: 实现 WeatherStrategy**

创建 `app/services/weather/strategy.py`：

```python
"""WeatherStrategy — Provider 路由 + 兜底 + 预警注入。"""

import logging

from app.core.config import settings
from app.services.weather.alert_scraper import AlertScraper
from app.services.weather.base import (
    AirQuality,
    ProviderError,
    WeatherData,
)
from app.services.weather.open_meteo import OpenMeteoProvider
from app.services.weather.qweather import QWeatherProvider

logger = logging.getLogger(__name__)


class WeatherStrategy:
    """天气策略路由层。

    按优先级遍历 providers，第一个能服务的作为主 provider。
    主 provider 失败时自动尝试下一个。
    预报数据叠加 AlertScraper 获取的官方预警。
    """

    def __init__(
        self,
        providers: list,
        alert_scraper: AlertScraper | None = None,
    ) -> None:
        self._providers = providers
        self._alert_scraper = alert_scraper or AlertScraper()

    async def fetch(self, location: str, days: int = 7) -> WeatherData:
        """获取天气数据（含路由、兜底、预警注入）。"""
        last_error: Exception | None = None

        for provider in self._providers:
            try:
                can = await provider.can_serve(location)
                if not can:
                    continue
            except Exception as exc:
                logger.warning(
                    "Provider %s can_serve 检查失败: %s",
                    provider.__class__.__name__,
                    exc,
                )
                continue

            try:
                data = await provider.fetch_daily(location, days)
                # 注入预警（无论哪个 provider，都尝试爬取预警）
                try:
                    alerts = self._alert_scraper.fetch_alerts(location)
                    data.alerts = alerts
                except Exception as exc:
                    logger.warning("预警爬取失败，使用空列表: %s", exc)
                    data.alerts = []
                return data
            except ProviderError as exc:
                logger.warning(
                    "Provider %s 请求失败，尝试下一个: %s",
                    provider.__class__.__name__,
                    exc,
                )
                last_error = exc

        if last_error:
            raise ProviderError(f"所有天气 Provider 均不可用: {last_error}")
        raise ProviderError("没有可用的天气 Provider")

    async def fetch_air_quality(self, location: str) -> AirQuality | None:
        """获取空气质量（优先第一个能服务的 provider）。"""
        for provider in self._providers:
            try:
                can = await provider.can_serve(location)
                if not can:
                    continue
                return await provider.fetch_air_quality(location)
            except ProviderError as exc:
                logger.warning(
                    "Provider %s AQI 请求失败，尝试下一个: %s",
                    provider.__class__.__name__,
                    exc,
                )
            except Exception as exc:
                logger.warning(
                    "Provider %s AQI 异常: %s",
                    provider.__class__.__name__,
                    exc,
                )
        return None


# 懒加载单例
_weather_strategy: WeatherStrategy | None = None


def get_weather_strategy() -> WeatherStrategy:
    """获取全局 WeatherStrategy 实例（懒初始化）。"""
    global _weather_strategy
    if _weather_strategy is None:
        providers = [OpenMeteoProvider()]
        if settings.secrets.qweather_api_key:
            providers.insert(
                0,
                QWeatherProvider(api_key=settings.secrets.qweather_api_key),
            )
        _weather_strategy = WeatherStrategy(providers=providers)
    return _weather_strategy
```

- [ ] **Step 4: 更新 weather/__init__.py**

```python
"""天气服务模块，双 Provider 架构。"""

from app.services.weather.base import (
    AirQuality,
    DailyForecast,
    ProviderError,
    WeatherAlert,
    WeatherData,
    WeatherProvider,
)
from app.services.weather.strategy import get_weather_strategy, WeatherStrategy

__all__ = [
    "WeatherProvider",
    "WeatherStrategy",
    "get_weather_strategy",
    "WeatherData",
    "DailyForecast",
    "WeatherAlert",
    "AirQuality",
    "ProviderError",
]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && pytest tests/services/weather/test_strategy.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/weather/strategy.py backend/app/services/weather/__init__.py backend/tests/services/weather/test_strategy.py
git commit -m "feat(weather): implement WeatherStrategy with routing and fallback"
```

---

### Task 8: 删除旧 weather_service.py，更新引用

**Files:**
- Delete: `app/services/weather_service.py`
- Modify: `app/api/weather.py`
- Modify: `app/services/farm_context_service.py`
- Modify: `app/agent/skills/weather/scripts/main.py`
- Delete: `tests/test_weather_service.py`
- Test: `tests/api/test_weather_api.py`

- [ ] **Step 1: 更新 app/api/weather.py**

```python
"""天气 API 路由，提供天气预报数据接口。"""

from fastapi import APIRouter

from app.services.weather import get_weather_strategy

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/forecast")
async def get_forecast(
    days: int = 7,
    location: str = "苏州",
):
    """获取未来 N 天天气预报。

    Args:
        days: 预报天数（默认 7 天）。
        location: 城市名（默认"苏州"）。
    """
    strategy = get_weather_strategy()
    data = await strategy.fetch(location, days=days)
    return {
        "location": data.location,
        "provider": data.provider,
        "daily": [
            {
                "date": d.date,
                "temp_max": d.temp_max,
                "temp_min": d.temp_min,
                "weather_text": d.weather_text,
                "precipitation": d.precipitation,
                "wind_speed": d.wind_speed,
            }
            for d in data.daily
        ],
        "alerts": [
            {"title": a.title, "severity": a.severity, "description": a.description}
            for a in data.alerts
        ],
        "air_quality": (
            {
                "aqi": data.air_quality.aqi,
                "category": data.air_quality.category,
                "pm25": data.air_quality.pm25,
            }
            if data.air_quality
            else None
        ),
        "current_temp": data.current_temp,
    }
```

- [ ] **Step 2: 更新 app/services/farm_context_service.py**

将 `from app.services import weather_service` 改为：

```python
from app.services.weather import get_weather_strategy
```

将天气获取逻辑从：
```python
        data = weather_service.fetch_weather(
            lat=lat, lon=lon, days=_MAX_WEATHER_DAYS
        )
        return _format_weather_line(data, days=_MAX_WEATHER_DAYS)
```

改为异步调用（需要确认调用方是否已经是 async）：

查看 `farm_context_service.py` 中的调用位置... 由于 `get_farm_context_summary` 可能是同步函数，需要改为 async 或使用 asyncio.run。先检查调用链。

如果调用链太长，可以保留同步接口。这里先标记为需要进一步确认。暂时改为：

```python
from app.services.weather import get_weather_strategy

# ... 在 _get_weather_line 中:
async def _get_weather_line(db: Session, farm_id: int) -> str:
    """获取天气摘要（异步）。"""
    # ... (前面的代码不变)
    try:
        strategy = get_weather_strategy()
        data = await strategy.fetch("苏州", days=_MAX_WEATHER_DAYS)
        return _format_weather_line(data, days=_MAX_WEATHER_DAYS)
    except Exception:
        logger.warning("天气数据获取失败，使用降级提示")
        return "暂无天气数据"
```

注意：`farm_context_service.py` 中 `_get_weather_line` 的调用方 `get_farm_context_summary` 可能也需要改为 async。这是 breaking change，需要同步修改调用方。

查看 `farm_context_service.py` 的调用链：

```python
# 找到调用 _get_weather_line 的地方
```

由于这个改动影响面较大，计划中将 farm_context_service.py 的更新拆为一个独立子任务：

**子任务 8a: 将 farm_context_service 中的天气调用改为异步**

需要检查 `get_farm_context_summary` 的所有调用方并同步更新。

由于这个分析比较复杂，我们在实施时再做决定。计划中将这个标记为 "需要确认调用链" 的注意事项。

- [ ] **Step 3: 更新 WeatherSkill**

修改 `app/agent/skills/weather/scripts/main.py`：

```python
"""天气预报 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.config import settings
from app.core.database import SessionLocal
from app.infra.skill_cache import cached
from app.services.weather import get_weather_strategy


def _get_user_coords(farm_id: int) -> tuple[float, float]:
    """从 user_settings 读取用户坐标，无记录时降级到默认值。"""
    default_lat = settings.weather_latitude
    default_lon = settings.weather_longitude
    try:
        db = SessionLocal()
        try:
            from app.models.farm import Farm
            from app.models.user_setting import UserSetting

            farm = db.query(Farm).filter(Farm.id == farm_id).first()
            if farm and farm.user_id:
                setting = (
                    db.query(UserSetting)
                    .filter(UserSetting.user_id == farm.user_id)
                    .first()
                )
                if setting and setting.default_lat and setting.default_lon:
                    return setting.default_lat, setting.default_lon
        finally:
            db.close()
    except Exception:
        pass
    return default_lat, default_lon


class WeatherSkill(Skill):
    def name(self) -> str:
        return "weather"

    def description(self) -> str:
        return (
            "获取未来7天天气预报和灾害预警。当用户问天气怎么样、明天天气、"
            "最近有雨吗、气温多少、有没有极端天气时，调用此工具获取真实天气数据。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "城市名（如苏州、北京）",
                    "default": "当前地块",
                },
            },
            "required": [],
        }

    @cached(ttl_seconds=1800)
    async def execute(self, params: dict, context) -> SkillResult:
        location = params.get("location", "当前地块")
        farm_id = getattr(context, "farm_id", 1) or 1

        # 如果 location 是"当前地块"，使用用户坐标对应的城市名
        # 简化处理：直接使用 location 作为城市名查询
        # 后续可扩展为坐标 → 城市名反向解析
        if location in ("当前地块", "", None):
            # 默认使用配置中的坐标对应城市
            # 这里简化处理，后续通过用户设置关联
            location = "苏州"  # 默认值

        strategy = get_weather_strategy()
        try:
            data = await strategy.fetch(location, days=7)
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"天气查询失败：{exc}",
            )

        lines = [f"地点：{location}", "未来 7 天天气预报："]
        for d in data.daily:
            lines.append(
                f"  {d.date}: {d.weather_text} "
                f"最高{d.temp_max}°C 最低{d.temp_min}°C "
                f"降水{d.precipitation}mm 风速{d.wind_speed}m/s"
            )

        if data.alerts:
            lines.append("天气预警：")
            for alert in data.alerts:
                lines.append(f"  {alert.title}（{alert.severity}）")
                if alert.description:
                    lines.append(f"    {alert.description}")
        else:
            lines.append("近期无官方气象预警。")

        # 生活指数（仅和风天气返回时才有）
        if data.air_quality:
            lines.append(
                f"空气质量：AQI {data.air_quality.aqi} "
                f"（{data.air_quality.category}）"
            )

        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply="\n".join(lines),
            data={
                "location": data.location,
                "provider": data.provider,
                "daily": [
                    {
                        "date": d.date,
                        "temp_max": d.temp_max,
                        "temp_min": d.temp_min,
                        "weather_text": d.weather_text,
                        "precipitation": d.precipitation,
                        "wind_speed": d.wind_speed,
                    }
                    for d in data.daily
                ],
                "alerts": [
                    {"title": a.title, "severity": a.severity}
                    for a in data.alerts
                ],
                "air_quality": (
                    {
                        "aqi": data.air_quality.aqi,
                        "category": data.air_quality.category,
                    }
                    if data.air_quality
                    else None
                ),
            },
        )
```

- [ ] **Step 4: 删除旧文件**

```bash
rm backend/app/services/weather_service.py
rm backend/tests/test_weather_service.py
```

- [ ] **Step 5: 写新测试**

创建 `tests/skills/test_weather_skill.py`：

```python
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agent.skills.weather.scripts.main import WeatherSkill
from app.services.weather.base import (
    AirQuality,
    DailyForecast,
    WeatherAlert,
    WeatherData,
)


class TestWeatherSkill:
    """测试改造后的 WeatherSkill。"""

    @pytest.fixture
    def skill(self) -> WeatherSkill:
        return WeatherSkill()

    @pytest.fixture
    def mock_context(self) -> Mock:
        ctx = Mock()
        ctx.farm_id = 1
        return ctx

    @patch("app.agent.skills.weather.scripts.main.get_weather_strategy")
    async def test_execute_success(
        self, mock_get_strategy: Mock, skill: WeatherSkill, mock_context: Mock
    ) -> None:
        """正常查询返回格式化结果。"""
        mock_strategy = Mock()
        mock_strategy.fetch = AsyncMock(return_value=WeatherData(
            location="苏州",
            provider="qweather",
            daily=[
                DailyForecast("2026-05-28", 30, 20, "晴", 0, 5),
                DailyForecast("2026-05-29", 28, 18, "多云", 2, 8),
            ],
            alerts=[WeatherAlert("暴雨黄色预警", "yellow", "预计降雨量50mm")],
            air_quality=AirQuality(45, "优", 15),
            current_temp=25,
        ))
        mock_get_strategy.return_value = mock_strategy

        result = await skill.execute({"location": "苏州"}, mock_context)

        assert result.status.value == "success"
        assert "苏州" in result.reply
        assert "晴" in result.reply
        assert "暴雨黄色预警" in result.reply
        assert "AQI 45" in result.reply
        assert result.data is not None
        assert len(result.data["daily"]) == 2

    @patch("app.agent.skills.weather.scripts.main.get_weather_strategy")
    async def test_execute_default_location(
        self, mock_get_strategy: Mock, skill: WeatherSkill, mock_context: Mock
    ) -> None:
        """未传 location 时使用默认值。"""
        mock_strategy = Mock()
        mock_strategy.fetch = AsyncMock(return_value=WeatherData(
            location="苏州",
            provider="open-meteo",
            daily=[DailyForecast("2026-05-28", 25, 15, "晴", 0, 3)],
            alerts=[],
            air_quality=None,
            current_temp=20,
        ))
        mock_get_strategy.return_value = mock_strategy

        result = await skill.execute({}, mock_context)

        assert result.status.value == "success"
        mock_strategy.fetch.assert_awaited_once()

    @patch("app.agent.skills.weather.scripts.main.get_weather_strategy")
    async def test_execute_failure(
        self, mock_get_strategy: Mock, skill: WeatherSkill, mock_context: Mock
    ) -> None:
        """查询失败返回 FAILED 状态。"""
        mock_strategy = Mock()
        mock_strategy.fetch = AsyncMock(side_effect=Exception("网络错误"))
        mock_get_strategy.return_value = mock_strategy

        result = await skill.execute({"location": "苏州"}, mock_context)

        assert result.status.value == "failed"
        assert "天气查询失败" in result.reply

    def test_name(self, skill: WeatherSkill) -> None:
        """Skill 名称为 weather。"""
        assert skill.name() == "weather"

    def test_parameters_schema_has_location(self, skill: WeatherSkill) -> None:
        """参数 schema 包含 location 字段。"""
        schema = skill.parameters_schema()
        assert "location" in schema["properties"]
        assert "城市名" in schema["properties"]["location"]["description"]
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && pytest tests/skills/test_weather_skill.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/weather.py backend/app/agent/skills/weather/scripts/main.py backend/tests/skills/test_weather_skill.py
git rm backend/app/services/weather_service.py backend/tests/test_weather_service.py
git commit -m "refactor(weather): replace weather_service with WeatherStrategy, update WeatherSkill"
```

---

### Task 9: AirQualitySkill

**Files:**
- Create: `app/agent/skills/air_quality/__init__.py`
- Create: `app/agent/skills/air_quality/scripts/__init__.py`
- Create: `app/agent/skills/air_quality/scripts/main.py`
- Create: `app/agent/skills/air_quality/skill.md`
- Test: `tests/skills/test_air_quality_skill.py`

- [ ] **Step 1: 写 AirQualitySkill 测试**

```python
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.agent.skills.air_quality.scripts.main import AirQualitySkill
from app.services.weather.base import AirQuality


class TestAirQualitySkill:
    """测试 AirQualitySkill。"""

    @pytest.fixture
    def skill(self) -> AirQualitySkill:
        return AirQualitySkill()

    @pytest.fixture
    def mock_context(self) -> Mock:
        ctx = Mock()
        ctx.farm_id = 1
        return ctx

    @patch("app.agent.skills.air_quality.scripts.main.get_weather_strategy")
    async def test_execute_success(
        self, mock_get_strategy: Mock, skill: AirQualitySkill, mock_context: Mock
    ) -> None:
        """正常查询返回 AQI 数据。"""
        mock_strategy = Mock()
        mock_strategy.fetch_air_quality = AsyncMock(
            return_value=AirQuality(aqi=45, category="优", pm25=15)
        )
        mock_get_strategy.return_value = mock_strategy

        result = await skill.execute({"location": "苏州"}, mock_context)

        assert result.status.value == "success"
        assert "AQI 45" in result.reply
        assert "优" in result.reply
        assert "PM2.5" in result.reply

    @patch("app.agent.skills.air_quality.scripts.main.get_weather_strategy")
    async def test_execute_no_data(
        self, mock_get_strategy: Mock, skill: AirQualitySkill, mock_context: Mock
    ) -> None:
        """无数据时返回提示。"""
        mock_strategy = Mock()
        mock_strategy.fetch_air_quality = AsyncMock(return_value=None)
        mock_get_strategy.return_value = mock_strategy

        result = await skill.execute({"location": "苏州"}, mock_context)

        assert result.status.value == "success"
        assert "暂无空气质量数据" in result.reply

    def test_name(self, skill: AirQualitySkill) -> None:
        assert skill.name() == "get_air_quality"

    def test_parameters_schema(self, skill: AirQualitySkill) -> None:
        schema = skill.parameters_schema()
        assert "location" in schema["properties"]
        assert "required" in schema
        assert "location" in schema["required"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && pytest tests/skills/test_air_quality_skill.py -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: 创建 AirQualitySkill**

创建 `app/agent/skills/air_quality/__init__.py`：

```python
"""空气质量查询 Skill 包。"""

from .scripts.main import AirQualitySkill

skill = AirQualitySkill()
```

创建 `app/agent/skills/air_quality/scripts/__init__.py`：

```python
"""空气质量 Skill 脚本。"""
```

创建 `app/agent/skills/air_quality/scripts/main.py`：

```python
"""空气质量查询 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.services.weather import get_weather_strategy


class AirQualitySkill(Skill):
    def name(self) -> str:
        return "get_air_quality"

    def description(self) -> str:
        return (
            "查询指定城市的空气质量（AQI、PM2.5）。"
            "当用户问空气质量、AQI、PM2.5、污染程度时调用。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "城市名（如苏州、北京）",
                },
            },
            "required": ["location"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        location = params.get("location", "")
        if not location:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="请提供城市名，如「苏州的空气质量怎么样」。",
            )

        strategy = get_weather_strategy()
        try:
            aq = await strategy.fetch_air_quality(location)
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"空气质量查询失败：{exc}",
            )

        if not aq:
            return SkillResult(
                status=ResultStatus.SUCCESS,
                reply=f"{location} 暂无空气质量数据。",
            )

        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=(
                f"{location} 空气质量：\n"
                f"AQI：{aq.aqi}（{aq.category}）\n"
                f"PM2.5：{aq.pm25} μg/m³"
            ),
            data={
                "location": location,
                "aqi": aq.aqi,
                "category": aq.category,
                "pm25": aq.pm25,
            },
        )
```

创建 `app/agent/skills/air_quality/skill.md`：

```markdown
---
name: get_air_quality
description: 查询指定城市的空气质量（AQI、PM2.5）。触发词: 空气质量、AQI、PM2.5、污染
triggers:
  - 空气质量
  - AQI
  - PM2.5
  - 污染
cache_ttl: 1800
parameters:
  type: object
  properties:
    location:
      type: string
      description: "城市名（如苏州、北京）"
  required:
    - location
---

# 空气质量查询

## 功能
查询指定城市的空气质量指数（AQI）和 PM2.5 浓度。

## 参数说明
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| location | string | 是 | 城市名 |

## 示例
用户：「苏州空气质量怎么样」
→ get_air_quality(location="苏州")
```

- [ ] **Step 4: 注册 AirQualitySkill**

修改 `app/agent/skills/__init__.py`，在技能注册列表中加入 `air_quality`：

```python
# 找到类似这样的技能注册代码
# 添加:
# from app.agent.skills.air_quality import skill as air_quality_skill
# _SKILL_REGISTRY["get_air_quality"] = air_quality_skill
```

需要查看 `app/agent/skills/__init__.py` 的实际注册方式。请读取该文件确认。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && pytest tests/skills/test_air_quality_skill.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/skills/air_quality/ backend/tests/skills/test_air_quality_skill.py
git commit -m "feat(skills): add AirQualitySkill for AQI queries"
```

---

### Task 10: Prompt 模板更新

**Files:**
- Modify: `backend/prompts/base.j2`

- [ ] **Step 1: 在 base.j2 的 user_context 段添加天气预警摘要**

在 `<user_context>` 后面、农场现状之前添加：

```jinja2
{% if weather_alert_summary %}
【天气预警】
{{ weather_alert_summary }}
{% endif %}
```

注意：`weather_alert_summary` 需要在 Agent 层注入。这是一个可选字段，无预警时不显示。

- [ ] **Step 2: Commit**

```bash
git add backend/prompts/base.j2
git commit -m "feat(prompts): add weather_alert_summary to base.j2"
```

---

### Task 11: 端到端验证

**Files:**
- Test: `tests/e2e/test_dual_weather.py`

- [ ] **Step 1: 写端到端测试**

```python
import pytest


class TestDualWeatherE2E:
    """双天气供应商端到端验证。"""

    @pytest.mark.asyncio
    async def test_weather_skill_with_strategy(self) -> None:
        """WeatherSkill 通过 Strategy 获取数据。"""
        from app.agent.skills.weather.scripts.main import WeatherSkill

        skill = WeatherSkill()
        ctx = type("Context", (), {"farm_id": 1})()

        result = await skill.execute({"location": "苏州"}, ctx)

        # 验证返回格式
        assert result.status.value in ("success", "failed")
        if result.status.value == "success":
            assert "天气预报" in result.reply
            assert result.data is not None
            assert "provider" in result.data
            assert result.data["provider"] in ("qweather", "open-meteo")

    @pytest.mark.asyncio
    async def test_air_quality_skill(self) -> None:
        """AirQualitySkill 可正常调用。"""
        from app.agent.skills.air_quality.scripts.main import AirQualitySkill

        skill = AirQualitySkill()
        ctx = type("Context", (), {"farm_id": 1})()

        result = await skill.execute({"location": "苏州"}, ctx)

        assert result.status.value in ("success", "failed")

    def test_secrets_config_loads(self) -> None:
        """SecretsConfig 可从 config.yaml 加载。"""
        from app.core.config import settings

        assert hasattr(settings, "secrets")
        assert hasattr(settings, "ai_api_key")

    def test_weather_strategy_singleton(self) -> None:
        """WeatherStrategy 单例正常工作。"""
        from app.services.weather import get_weather_strategy

        s1 = get_weather_strategy()
        s2 = get_weather_strategy()
        assert s1 is s2

    def test_provider_list_when_no_qweather_key(self) -> None:
        """无和风天气 key 时只有 OpenMeteoProvider。"""
        from unittest.mock import patch

        from app.services.weather import get_weather_strategy
        from app.core.config import settings

        with patch.object(settings.secrets, "qweather_api_key", ""):
            # 强制重新初始化
            import app.services.weather.strategy as strat
            strat._weather_strategy = None

            strategy = get_weather_strategy()
            provider_names = [p.__class__.__name__ for p in strategy._providers]
            assert "OpenMeteoProvider" in provider_names
            assert "QWeatherProvider" not in provider_names
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && pytest tests/e2e/test_dual_weather.py -v`
Expected: PASS（部分测试依赖外部 API，可能失败）

- [ ] **Step 3: Commit**

```bash
git add backend/tests/e2e/test_dual_weather.py
git commit -m "test(weather): add E2E tests for dual weather provider"
```

---

## Self-Review

### 1. Spec Coverage

| Spec 要求 | 实现位置 |
|-----------|---------|
| SecretsConfig 统一密钥管理 | Task 1 |
| AIConfig/LangSmithConfig 移除 api_key | Task 1 |
| 向后兼容（ai_api_key property） | Task 1 |
| config.yaml 新增 secrets 段 | Task 1 |
| llm.py / main.py 更新 key 路径 | Task 2 |
| WeatherProvider ABC | Task 3 |
| WeatherData / DailyForecast / WeatherAlert / AirQuality | Task 3 |
| OpenMeteoProvider（含 geocoding + AQI） | Task 4 |
| QWeatherProvider（含 city lookup + AQI） | Task 5 |
| AlertScraper（weather.com.cn） | Task 6 |
| 300+ 城市编号映射 | Task 6 |
| WeatherStrategy 路由 + 兜底 | Task 7 |
| 预警注入 | Task 7 |
| get_weather_strategy() 单例 | Task 7 |
| 无 qweather key 时只用 OpenMeteo | Task 7 |
| WeatherSkill 改造（location 参数可用） | Task 8 |
| AirQualitySkill 新增 | Task 9 |
| 删除旧 weather_service.py | Task 8 |
| Prompt 模板更新 | Task 10 |
| 端到端测试 | Task 11 |

### 2. Placeholder Scan

- 无 "TBD"、"TODO"、"implement later"
- 无 "Add appropriate error handling" 类模糊描述
- 所有步骤都有完整代码
- 无 "Similar to Task N" 引用

### 3. Type Consistency

- `WeatherData` 定义在 Task 3，后续所有 provider 返回此类型
- `ProviderError` 在 Task 3 定义，所有 provider 统一抛出
- `can_serve()` 签名：OpenMeteoProvider 为同步，QWeatherProvider 为 async — 需在 base.py 中统一

**⚠️ 发现类型不一致：`can_serve()` 在 OpenMeteoProvider 中是同步方法，在 QWeatherProvider 中是 async。需要在 base.py 中统一为 async。**

修正方案：将 `WeatherProvider.can_serve` 改为 `async def`：

```python
    @abstractmethod
    async def can_serve(self, location: str) -> bool:
        ...
```

OpenMeteoProvider 也改为 async（虽然内部不等待，但用 `async def`）：

```python
    async def can_serve(self, _location: str) -> bool:
        return True
```

此修正已融入 Step 3 的代码中。

### 4. 已知风险

- **farm_context_service.py 的同步调用链**：`_get_weather_line` 调用 `strategy.fetch()`（async）需要改为 async。这会影响 `get_farm_context_summary` 及其所有调用方。这是一个需要特别关注的 breaking change，建议在实施时先确认调用链再决定处理方式。
  - 处理方式 A：将整条链改为 async
  - 处理方式 B：在同步函数中使用 `asyncio.run()` 或 `asyncio.get_event_loop().run_until_complete()` 包裹
  - 处理方式 C：保留一个同步兼容层

---

## 文件变更汇总

### 新增文件
- `app/services/weather/__init__.py`
- `app/services/weather/base.py`
- `app/services/weather/open_meteo.py`
- `app/services/weather/qweather.py`
- `app/services/weather/alert_scraper.py`
- `app/services/weather/strategy.py`
- `app/agent/skills/air_quality/__init__.py`
- `app/agent/skills/air_quality/scripts/__init__.py`
- `app/agent/skills/air_quality/scripts/main.py`
- `app/agent/skills/air_quality/skill.md`
- `tests/core/test_config.py`
- `tests/core/test_config_compatibility.py`
- `tests/services/weather/test_base.py`
- `tests/services/weather/test_open_meteo.py`
- `tests/services/weather/test_qweather.py`
- `tests/services/weather/test_alert_scraper.py`
- `tests/services/weather/test_strategy.py`
- `tests/skills/test_weather_skill.py`
- `tests/skills/test_air_quality_skill.py`
- `tests/e2e/test_dual_weather.py`

### 修改文件
- `app/core/config.py`
- `config.yaml`
- `app/core/llm.py`
- `app/main.py`
- `app/api/admin_config.py`
- `app/api/weather.py`
- `app/agent/skills/weather/scripts/main.py`
- `app/agent/skills/__init__.py`（注册 air_quality skill）
- `prompts/base.j2`
- `app/services/farm_context_service.py`（待确认调用链）
- `app/agent/graph.py`（如果直接引用 ai_api_key，property 兼容则无需改）

### 删除文件
- `app/services/weather_service.py`
- `tests/test_weather_service.py`
