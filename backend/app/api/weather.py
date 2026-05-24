"""天气 API 路由，提供天气预报数据接口。"""

from fastapi import APIRouter

from app.core.config import settings
from app.services.weather_service import fetch_weather

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/forecast")
def get_forecast(
    days: int = 7,
    lat: float | None = None,
    lon: float | None = None,
):
    """获取未来 N 天天气预报原始数据。

    Args:
        days: 预报天数（默认 7 天）。
        lat: 纬度（可选，默认使用服务端配置）。
        lon: 经度（可选，默认使用服务端配置）。
    """
    latitude = lat if lat is not None else settings.weather_latitude
    longitude = lon if lon is not None else settings.weather_longitude
    data = fetch_weather(latitude, longitude, days=days)
    return data


__all__ = ["router"]
