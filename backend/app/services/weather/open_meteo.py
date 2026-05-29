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

    async def fetch_daily(
        self,
        location: str = "",
        days: int = 7,
        lat: float | None = None,
        lon: float | None = None,
    ) -> WeatherData:
        """获取天气预报。"""
        # 优先使用传入的坐标，否则 geocoding
        if lat is None or lon is None:
            if location:
                lat, lon = await self._geocode(location)
            else:
                raise ProviderError("未提供位置信息")
        else:
            location = location or f"{lat:.2f},{lon:.2f}"

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

    async def can_serve(self, _location: str) -> bool:
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
