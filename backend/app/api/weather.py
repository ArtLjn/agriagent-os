"""天气 API 路由，提供天气预报数据接口。"""

from fastapi import APIRouter

from app.infra.settings import settings
from app.services.weather_service import fetch_weather, check_weather_warnings

router = APIRouter(prefix="/weather", tags=["weather"])

_PLACEHOLDER_LOCATIONS = {"", "当前地块", "地块"}


@router.get("/forecast")
async def get_forecast(
    days: int = 7,
    location: str = "当前地块",
    lat: float | None = None,
    lon: float | None = None,
):
    """获取未来 N 天天气预报。

    Args:
        days: 预报天数（默认 7 天）。
        location: 城市名（默认"当前地块"）。
        lat: 纬度（与 lon 配合使用，优先级高于 location）。
        lon: 经度（与 lat 配合使用，优先级高于 location）。
    """
    if (lat is None or lon is None) and location.strip() in _PLACEHOLDER_LOCATIONS:
        lat = settings.weather_latitude
        lon = settings.weather_longitude
    data = await fetch_weather(location, days, lat, lon)
    warnings = check_weather_warnings(data)
    data["warnings"] = warnings
    return data


__all__ = ["router"]
