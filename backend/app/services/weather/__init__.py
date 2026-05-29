"""天气服务模块，双 Provider 架构。"""

from app.services.weather.base import (
    AirQuality,
    DailyForecast,
    ProviderError,
    WeatherAlert,
    WeatherData,
    WeatherProvider,
)
from app.services.weather.strategy import WeatherStrategy, get_weather_strategy

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
