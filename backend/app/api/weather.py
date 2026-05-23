"""天气 API 路由，提供天气预报数据接口。"""

from fastapi import APIRouter

from app.core.config import settings
from app.services.weather_service import fetch_weather

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/forecast")
def get_forecast(days: int = 7):
    """获取未来 N 天天气预报原始数据。"""
    data = fetch_weather(
        settings.weather_latitude,
        settings.weather_longitude,
        days=days,
    )
    return data


__all__ = ["router"]
