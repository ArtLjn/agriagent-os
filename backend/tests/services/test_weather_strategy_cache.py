"""测试 WeatherStrategy.fetch() 的预报缓存集成。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.weather.base import (
    DailyForecast,
    ProviderError,
    WeatherData,
)
from app.services.weather.cache import WeatherCache, weather_cache


def _make_weather_data(
    location: str = "苏州",
    provider: str = "open-meteo",
) -> WeatherData:
    """构造测试用 WeatherData。"""
    return WeatherData(
        location=location,
        provider=provider,
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


def _make_provider(
    can_serve_result: bool = True,
    fetch_daily_result: WeatherData | None = None,
) -> MagicMock:
    """构造 mock provider。"""
    provider = MagicMock()
    provider.can_serve = AsyncMock(return_value=can_serve_result)
    if fetch_daily_result is not None:
        provider.fetch_daily = AsyncMock(return_value=fetch_daily_result)
    else:
        provider.fetch_daily = AsyncMock(return_value=_make_weather_data())
    return provider


# ---------- 缓存 key 生成测试 ----------


class TestCacheKeyGeneration:
    """验证缓存 key 包含所有必要参数。"""

    def test_key_with_location_and_days(self) -> None:
        key = WeatherCache.make_key("苏州", days=7)
        assert key == "苏州|7"

    def test_key_with_lat_lon(self) -> None:
        key = WeatherCache.make_key("苏州", days=7, lat=31.2990, lon=120.5853)
        assert key == "苏州|7|31.2990|120.5853"

    def test_key_with_only_lat(self) -> None:
        key = WeatherCache.make_key("苏州", days=3, lat=31.2990)
        assert key == "苏州|3|31.2990"

    def test_key_empty_location(self) -> None:
        key = WeatherCache.make_key("", days=7, lat=31.0, lon=120.0)
        assert key == "|7|31.0000|120.0000"

    def test_key_different_coords_different_keys(self) -> None:
        key1 = WeatherCache.make_key("苏州", days=7, lat=31.1, lon=120.1)
        key2 = WeatherCache.make_key("苏州", days=7, lat=31.2, lon=120.2)
        assert key1 != key2


# ---------- fetch() 缓存命中测试 ----------


class TestFetchCacheHit:
    """缓存命中时直接返回，不走 provider。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> None:
        weather_cache.clear()
        yield
        weather_cache.clear()

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_data(self) -> None:
        """缓存命中时直接返回缓存数据，不调用 provider。"""
        cached_data = _make_weather_data(location="苏州")
        weather_cache.set(
            WeatherCache.make_key("苏州", days=7),
            cached_data,
        )

        provider = _make_provider()
        strategy = _make_strategy([provider])

        result = await strategy.fetch(location="苏州", days=7)

        assert result is cached_data
        provider.fetch_daily.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_hit_with_coords(self) -> None:
        """带坐标的缓存命中。"""
        cached_data = _make_weather_data(location="苏州")
        weather_cache.set(
            WeatherCache.make_key("苏州", days=7, lat=31.299, lon=120.585),
            cached_data,
        )

        provider = _make_provider()
        strategy = _make_strategy([provider])

        result = await strategy.fetch(location="苏州", days=7, lat=31.299, lon=120.585)

        assert result is cached_data
        provider.fetch_daily.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_different_coords(self) -> None:
        """坐标不同时缓存 miss。"""
        cached_data = _make_weather_data()
        weather_cache.set(
            WeatherCache.make_key("苏州", days=7, lat=31.299, lon=120.585),
            cached_data,
        )

        new_data = _make_weather_data()
        provider = _make_provider(fetch_daily_result=new_data)
        strategy = _make_strategy([provider])

        result = await strategy.fetch(location="苏州", days=7, lat=31.300, lon=120.586)

        assert result is new_data
        provider.fetch_daily.assert_called_once()


# ---------- fetch() 缓存写入测试 ----------


class TestFetchCacheWrite:
    """provider 成功获取数据后写入缓存。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> None:
        weather_cache.clear()
        yield
        weather_cache.clear()

    @pytest.mark.asyncio
    async def test_cache_written_after_successful_fetch(self) -> None:
        """provider 成功后，缓存被写入。"""
        data = _make_weather_data()
        provider = _make_provider(fetch_daily_result=data)
        strategy = _make_strategy([provider])

        result = await strategy.fetch(location="苏州", days=7)

        assert result is data
        cached, hit = weather_cache.get(WeatherCache.make_key("苏州", days=7))
        assert hit is True
        assert cached is data

    @pytest.mark.asyncio
    async def test_cache_not_written_on_provider_error(self) -> None:
        """provider 全部失败时不写入缓存。

        使用 location="" 使 need_alerts=False，走 else 分支，
        这样 ProviderError 能正确触发 failover。
        """
        provider = MagicMock()
        provider.can_serve = AsyncMock(return_value=True)
        provider.fetch_daily = AsyncMock(side_effect=ProviderError("API 限流"))
        strategy = _make_strategy([provider])

        with pytest.raises(ProviderError, match="所有天气 Provider"):
            await strategy.fetch(location="", days=7, lat=31.0, lon=120.0)

        _, hit = weather_cache.get(
            WeatherCache.make_key("", days=7, lat=31.0, lon=120.0)
        )
        assert hit is False

    @pytest.mark.asyncio
    async def test_cache_written_with_correct_ttl(self) -> None:
        """缓存使用默认 TTL=600s。"""
        provider = _make_provider()
        strategy = _make_strategy([provider])

        await strategy.fetch(location="苏州", days=7)

        key = WeatherCache.make_key("苏州", days=7)
        _, hit = weather_cache.get(key)
        assert hit is True
        # 验证 TTL 通过检查存储结构中的过期时间
        import time

        value, expire_at = weather_cache._store[key]
        assert expire_at - time.time() <= 600
        assert expire_at - time.time() > 590

    @pytest.mark.asyncio
    async def test_cache_written_with_coords_key(self) -> None:
        """带坐标请求的缓存 key 包含坐标。"""
        data = _make_weather_data()
        provider = _make_provider(fetch_daily_result=data)
        strategy = _make_strategy([provider])

        await strategy.fetch(location="苏州", days=7, lat=31.299, lon=120.585)

        key = WeatherCache.make_key("苏州", days=7, lat=31.299, lon=120.585)
        cached, hit = weather_cache.get(key)
        assert hit is True
        assert cached is data


# ---------- fetch() 正常流程（缓存 miss 走 provider）----------


class TestFetchCacheMissFallback:
    """缓存 miss 时走原有 provider 逻辑。"""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> None:
        weather_cache.clear()
        yield
        weather_cache.clear()

    @pytest.mark.asyncio
    async def test_no_provider_raises_error(self) -> None:
        """没有可用 provider 时抛出异常（缓存 miss）。"""
        strategy = _make_strategy([])

        with pytest.raises(ProviderError, match="没有可用的天气 Provider"):
            await strategy.fetch(location="苏州", days=7)

    @pytest.mark.asyncio
    async def test_first_provider_fails_tries_next(self) -> None:
        """第一个 provider 失败时尝试第二个（缓存 miss）。

        使用 location="" 使 need_alerts=False，走 else 分支，
        这样 ProviderError 能正确触发 failover。
        """
        fail_provider = MagicMock()
        fail_provider.can_serve = AsyncMock(return_value=True)
        fail_provider.fetch_daily = AsyncMock(side_effect=ProviderError("超时"))

        success_data = _make_weather_data()
        success_provider = _make_provider(fetch_daily_result=success_data)

        strategy = _make_strategy([fail_provider, success_provider])

        result = await strategy.fetch(location="", days=7, lat=31.0, lon=120.0)

        assert result is success_data
        # 成功后应写入缓存
        cached, hit = weather_cache.get(
            WeatherCache.make_key("", days=7, lat=31.0, lon=120.0)
        )
        assert hit is True


# ---------- 辅助函数 ----------


def _make_strategy(providers: list):
    """构造 WeatherStrategy 实例，使用 mock alert_scraper。"""
    from app.services.weather.strategy import WeatherStrategy

    mock_scraper = MagicMock()
    mock_scraper.fetch_alerts = MagicMock(return_value=[])
    return WeatherStrategy(providers=providers, alert_scraper=mock_scraper)
