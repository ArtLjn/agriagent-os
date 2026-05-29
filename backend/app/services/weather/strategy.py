"""WeatherStrategy — Provider 路由 + 兜底 + 预警注入。"""

import logging

from app.core.config import settings
from app.services.weather.alert_scraper import AlertScraper
from app.services.weather.base import AirQuality, ProviderError, WeatherData
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

    async def fetch(
        self,
        location: str = "",
        days: int = 7,
        lat: float | None = None,
        lon: float | None = None,
    ) -> WeatherData:
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
                data = await provider.fetch_daily(location, days, lat, lon)
                # 预警爬虫仅支持真实城市名
                if location and location not in ("当前地块", "地块"):
                    try:
                        alerts = self._alert_scraper.fetch_alerts(location)
                        data.alerts = alerts
                    except Exception as exc:
                        logger.warning("预警爬取失败，使用空列表: %s", exc)
                        data.alerts = []
                else:
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
            raise ProviderError(
                f"所有天气 Provider 均不可用: {last_error}"
            )
        raise ProviderError("没有可用的天气 Provider")

    async def fetch_air_quality(
        self, location: str
    ) -> AirQuality | None:
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


def get_weather_strategy() -> WeatherStrategy:
    """获取全局 WeatherStrategy 实例（懒初始化）。"""
    global _weather_strategy
    if _weather_strategy is None:
        providers: list = [OpenMeteoProvider()]
        # 优先使用 API KEY（推荐方式）
        if settings.secrets.qweather_api_key:
            providers.insert(
                0,
                QWeatherProvider(
                    api_key=settings.secrets.qweather_api_key
                ),
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
