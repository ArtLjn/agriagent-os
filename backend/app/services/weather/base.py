"""天气 Provider 抽象基类和统一数据模型。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DailyForecast:
    """单日预报数据。"""

    date: str
    temp_max: float
    temp_min: float
    weather_text: str
    precipitation: float
    wind_speed: float


@dataclass
class WeatherAlert:
    """气象预警数据。"""

    title: str
    severity: str  # "blue", "yellow", "orange", "red"
    description: str


@dataclass
class AirQuality:
    """空气质量数据。"""

    aqi: int
    category: str  # "优", "良", "轻度污染", etc.
    pm25: float


@dataclass
class WeatherData:
    """统一天气数据聚合（屏蔽 Provider 差异）。"""

    location: str
    provider: str  # "qweather" / "open-meteo"
    daily: list[DailyForecast]
    alerts: list[WeatherAlert]
    air_quality: AirQuality | None
    current_temp: float | None


class ProviderError(Exception):
    """Provider 请求失败时的异常。"""

    pass


class WeatherProvider(ABC):
    """天气 Provider 抽象基类。"""

    @abstractmethod
    async def fetch_daily(self, location: str, days: int = 7) -> WeatherData:
        """获取指定地点的未来 N 天天气预报。

        Args:
            location: 城市名（如"苏州"）。
            days: 预报天数。

        Returns:
            WeatherData 聚合数据。

        Raises:
            ProviderError: 请求失败时抛出。
        """
        ...

    @abstractmethod
    async def fetch_air_quality(self, location: str) -> AirQuality | None:
        """获取指定地点的空气质量。

        Args:
            location: 城市名。

        Returns:
            AirQuality 或 None（不支持时）。

        Raises:
            ProviderError: 请求失败时抛出。
        """
        ...

    @abstractmethod
    async def can_serve(self, location: str) -> bool:
        """判断该 provider 是否能服务指定地点。

        Args:
            location: 城市名。

        Returns:
            True 表示可以服务。
        """
        ...
