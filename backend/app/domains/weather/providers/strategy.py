"""WeatherStrategy — Provider 路由 + 兜底 + 预警注入。"""

import asyncio
import logging

from app.shared.config import settings
from app.domains.weather.location_catalog import find_region
from app.domains.weather.providers.alert_scraper import AlertScraper
from app.domains.weather.providers.base import AirQuality, ProviderError, WeatherAlert, WeatherData
from app.domains.weather.providers.cache import weather_cache
from app.domains.weather.providers.open_meteo import OpenMeteoProvider
from app.domains.weather.providers.qweather import QWeatherProvider

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

    async def fetch(
        self,
        location: str = "",
        days: int = 7,
        lat: float | None = None,
        lon: float | None = None,
    ) -> WeatherData:
        """获取天气数据（缓存优先，Provider + 预警并行获取）。"""
        # 缓存查询
        cache_key = weather_cache.make_key(location, days, lat, lon)
        cached, hit = weather_cache.get(cache_key)
        if hit:
            logger.debug("缓存命中 key=%s", cache_key)
            return cached

        last_error: Exception | None = None
        alert_location = _alert_location_for(location)
        need_alerts = bool(alert_location)

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
                daily_coro = provider.fetch_daily(location, days, lat, lon)
                if need_alerts and alert_location:
                    cached_alerts, alert_hit = weather_cache.get_alert(alert_location)
                    if alert_hit:
                        data = await daily_coro
                        data.alerts = _merge_alerts(data.alerts, cached_alerts)
                    else:
                        data, alerts = await asyncio.gather(
                            daily_coro,
                            asyncio.to_thread(
                                self._alert_scraper.fetch_alerts, alert_location
                            ),
                            return_exceptions=True,
                        )
                        alerts = alerts if isinstance(alerts, list) else []
                        data.alerts = _merge_alerts(data.alerts, alerts)
                        weather_cache.set_alert(alert_location, alerts)
                else:
                    data = await daily_coro
                    data.alerts = []
                # 成功获取后写入缓存
                weather_cache.set(cache_key, data, ttl=600)
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


_weather_strategy: WeatherStrategy | None = None


def _alert_location_for(location: str) -> str:
    """把区县级天气地点映射成预警查询地点。"""
    cleaned = location.strip()
    if not cleaned or cleaned in ("当前地块", "地块"):
        return ""

    region = find_region(cleaned)
    if not region:
        return _strip_city_suffix(cleaned)

    city = str(region.get("city") or "").strip()
    if city:
        return _strip_city_suffix(city)
    name = str(region.get("name") or cleaned).strip()
    return _strip_city_suffix(name)


def _strip_city_suffix(value: str) -> str:
    """预警源常以“苏州”匹配全市及区县预警。"""
    return value[:-1] if value.endswith("市") and len(value) > 1 else value


def _merge_alerts(
    primary: list[WeatherAlert] | list | None,
    secondary: list[WeatherAlert] | list | None,
) -> list:
    """合并 provider 预警和外部预警，按标题+描述去重。"""
    merged: list = []
    seen: set[tuple[str, str]] = set()
    for alert in [*(primary or []), *(secondary or [])]:
        title = getattr(alert, "title", None)
        description = getattr(alert, "description", None)
        if isinstance(alert, dict):
            title = alert.get("title")
            description = alert.get("description")
        key = (str(title or ""), str(description or ""))
        if key in seen:
            continue
        seen.add(key)
        merged.append(alert)
    return merged


def get_weather_strategy() -> WeatherStrategy:
    """获取全局 WeatherStrategy 实例（懒初始化）。"""
    global _weather_strategy
    if _weather_strategy is None:
        providers: list = [OpenMeteoProvider()]
        # 优先使用 API KEY（推荐方式）
        if settings.secrets.qweather_api_key:
            providers.insert(
                0,
                QWeatherProvider(api_key=settings.secrets.qweather_api_key),
            )
        # 降级：签名认证（已弃用，仅作为备用）
        elif settings.secrets.qweather_appid and settings.secrets.qweather_appsecret:
            providers.insert(
                0,
                QWeatherProvider(
                    appid=settings.secrets.qweather_appid,
                    appsecret=settings.secrets.qweather_appsecret,
                ),
            )
        _weather_strategy = WeatherStrategy(providers=providers)
    return _weather_strategy
