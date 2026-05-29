"""天气 API 路由，提供天气预报数据接口。"""

from fastapi import APIRouter

from app.services.weather_service import fetch_weather, check_weather_warnings

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/forecast")
async def get_forecast(
    days: int = 7,
    location: str = "当前地块",
):
    """获取未来 N 天天气预报。

    Args:
        days: 预报天数（默认 7 天）。
        location: 城市名（默认"当前地块"）。
    """
    data = await fetch_weather(location, days)
    warnings = check_weather_warnings(data)
    data["warnings"] = warnings
    return data


__all__ = ["router"]
