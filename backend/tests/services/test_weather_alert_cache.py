"""测试预警独立缓存功能。"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.weather.base import WeatherData
from app.services.weather.cache import WeatherCache, weather_cache


class TestAlertCacheBasicOps:
    """验证 get_alert / set_alert 基本功能。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> None:
        weather_cache.clear()
        yield
        weather_cache.clear()

    def test_set_and_get_alert(self) -> None:
        """set_alert 写入后 get_alert 能正确读取。"""
        alerts = [
            {"title": "暴雨预警", "severity": "yellow", "description": "6小时内有暴雨"},
        ]
        weather_cache.set_alert("苏州", alerts)

        result, hit = weather_cache.get_alert("苏州")
        assert hit is True
        assert result == alerts

    def test_get_alert_miss_returns_none(self) -> None:
        """未写入的 city 返回 miss。"""
        result, hit = weather_cache.get_alert("不存在的城市")
        assert hit is False
        assert result is None

    def test_alert_and_forecast_use_different_keys(self) -> None:
        """预警缓存和预报缓存 key 不冲突。"""
        alerts = [
            {"title": "高温预警", "severity": "orange", "description": "温度超40度"}
        ]
        weather_cache.set_alert("苏州", alerts)

        # 预报缓存不包含预警数据
        _, forecast_hit = weather_cache.get(WeatherCache.make_key("苏州", days=7))
        assert forecast_hit is False

        # 预警缓存能命中
        _, alert_hit = weather_cache.get_alert("苏州")
        assert alert_hit is True

    def test_alert_ttl_is_1800_seconds(self) -> None:
        """预警缓存默认 TTL 为 1800 秒。"""
        weather_cache.set_alert("苏州", [])

        key = f"{WeatherCache._ALERT_PREFIX}苏州"
        value, expire_at = weather_cache._store[key]
        remaining = expire_at - time.time()
        assert remaining <= 1800
        assert remaining > 1790

    def test_alert_custom_ttl(self) -> None:
        """预警缓存支持自定义 TTL。"""
        weather_cache.set_alert("苏州", [], ttl=60)

        key = f"{WeatherCache._ALERT_PREFIX}苏州"
        value, expire_at = weather_cache._store[key]
        remaining = expire_at - time.time()
        assert remaining <= 60
        assert remaining > 50

    def test_alert_cache_expires_after_ttl(self) -> None:
        """预警缓存在 TTL 过期后返回 miss。"""
        weather_cache.set_alert("苏州", [], ttl=1)
        time.sleep(1.1)

        _, hit = weather_cache.get_alert("苏州")
        assert hit is False


class TestAlertCacheInStrategy:
    """验证 strategy.py 中预警缓存与 alert_scraper 的交互。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> None:
        weather_cache.clear()
        yield
        weather_cache.clear()

    @staticmethod
    def _make_provider(data: WeatherData | None = None) -> MagicMock:
        """构造 mock provider。"""
        from app.services.weather.base import DailyForecast

        if data is None:
            data = WeatherData(
                location="苏州",
                provider="open-meteo",
                daily=[
                    DailyForecast(
                        date="2026-05-29",
                        temp_max=28.0,
                        temp_min=18.0,
                        weather_text="晴",
                        precipitation=0.0,
                        wind_speed=10.0,
                    )
                ],
                alerts=[],
                air_quality=None,
                current_temp=25.0,
            )
        provider = MagicMock()
        provider.can_serve = AsyncMock(return_value=True)
        provider.fetch_daily = AsyncMock(return_value=data)
        return provider

    @staticmethod
    def _make_strategy(providers: list, alert_scraper=None):
        from app.services.weather.strategy import WeatherStrategy

        if alert_scraper is None:
            scraper = MagicMock()
            scraper.fetch_alerts = MagicMock(return_value=[])
        else:
            scraper = alert_scraper
        return WeatherStrategy(providers=providers, alert_scraper=scraper)

    @pytest.mark.asyncio
    async def test_alert_cache_hit_skips_scraper(self) -> None:
        """预警缓存命中时不调用 alert_scraper。"""
        cached_alerts = [
            {"title": "暴雨蓝色预警", "severity": "blue", "description": "预计有暴雨"},
        ]
        weather_cache.set_alert("苏州", cached_alerts)

        scraper = MagicMock()
        scraper.fetch_alerts = MagicMock(return_value=cached_alerts)
        provider = self._make_provider()
        strategy = self._make_strategy([provider], alert_scraper=scraper)

        result = await strategy.fetch(location="苏州", days=7)

        assert result.alerts == cached_alerts
        scraper.fetch_alerts.assert_not_called()

    @pytest.mark.asyncio
    async def test_alert_cache_miss_calls_scraper_and_caches(self) -> None:
        """预警缓存 miss 时调用 alert_scraper 并将结果写入缓存。"""
        fetched_alerts = [
            {
                "title": "高温黄色预警",
                "severity": "yellow",
                "description": "温度达38度",
            },
        ]
        scraper = MagicMock()
        scraper.fetch_alerts = MagicMock(return_value=fetched_alerts)
        provider = self._make_provider()
        strategy = self._make_strategy([provider], alert_scraper=scraper)

        result = await strategy.fetch(location="苏州", days=7)

        assert result.alerts == fetched_alerts
        scraper.fetch_alerts.assert_called_once_with("苏州")

        cached_alerts, hit = weather_cache.get_alert("苏州")
        assert hit is True
        assert cached_alerts == fetched_alerts

    @pytest.mark.asyncio
    async def test_alert_cache_miss_scraper_exception_uses_empty(self) -> None:
        """预警缓存 miss 且 scraper 异常时，alerts 为空列表。"""
        scraper = MagicMock()
        scraper.fetch_alerts = MagicMock(side_effect=Exception("网络超时"))
        provider = self._make_provider()
        strategy = self._make_strategy([provider], alert_scraper=scraper)

        result = await strategy.fetch(location="苏州", days=7)

        assert result.alerts == []

    @pytest.mark.asyncio
    async def test_no_alerts_when_location_is_placeholder(self) -> None:
        """location 为占位符时不请求预警，也不查缓存。"""
        scraper = MagicMock()
        scraper.fetch_alerts = MagicMock(return_value=[])
        provider = self._make_provider()
        strategy = self._make_strategy([provider], alert_scraper=scraper)

        result = await strategy.fetch(location="当前地块", days=7)

        assert result.alerts == []
        scraper.fetch_alerts.assert_not_called()
