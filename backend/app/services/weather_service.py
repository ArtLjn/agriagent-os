"""天气服务模块，双 Provider 架构（和风天气 + Open-Meteo）。"""

import logging

from app.services.weather.strategy import get_weather_strategy

logger = logging.getLogger(__name__)


async def fetch_weather(
    location: str = "",
    days: int = 7,
    lat: float | None = None,
    lon: float | None = None,
) -> dict:
    """获取指定地点的未来 N 天天气预报。

    Args:
        location: 城市名（如"苏州"）。
        days: 预报天数（默认 7 天）。
        lat: 纬度（优先使用坐标）。
        lon: 经度（优先使用坐标）。

    Returns:
        包含 daily 预报数据和 location 信息的字典（兼容旧格式）。

    Raises:
        RuntimeError: 请求失败时抛出。
    """
    strategy = get_weather_strategy()
    try:
        data = await strategy.fetch(location, days, lat, lon)
    except Exception as exc:
        raise RuntimeError(f"天气数据获取失败: {exc}") from exc

    # 转换为旧格式兼容
    return _to_legacy_format(data)


def _to_legacy_format(data) -> dict:
    """将新 WeatherData 转换为旧格式（兼容现有前端/Skill）。"""
    daily_times = []
    temp_max = []
    temp_min = []
    precip_sum = []
    precip_hours = []
    wind_speed_max = []
    uv_index_max = []
    humidity_mean = []
    apparent_temp_max = []
    apparent_temp_min = []

    for day in data.daily:
        daily_times.append(day.date)
        temp_max.append(day.temp_max)
        temp_min.append(day.temp_min)
        precip_sum.append(day.precipitation)
        wind_speed_max.append(day.wind_speed)
        # Open-Meteo 无数据时填默认值
        precip_hours.append(0 if day.precipitation > 0 else 0)
        uv_index_max.append(0)
        humidity_mean.append(60)
        apparent_temp_max.append(day.temp_max)
        apparent_temp_min.append(day.temp_min)

    warnings = []
    for alert in data.alerts:
        warnings.append(f"{alert.title}: {alert.description}")

    result = {
        "location": data.location,
        "provider": data.provider,
        "daily": {
            "time": daily_times,
            "temperature_2m_max": temp_max,
            "temperature_2m_min": temp_min,
            "precipitation_sum": precip_sum,
            "precipitation_hours": precip_hours,
            "windspeed_10m_max": wind_speed_max,
            "uv_index_max": uv_index_max,
            "relative_humidity_2m_mean": humidity_mean,
            "apparent_temperature_max": apparent_temp_max,
            "apparent_temperature_min": apparent_temp_min,
        },
        "hourly": {
            "time": [],
            "temperature_2m": [],
            "precipitation": [],
            "precipitation_probability": [],
        },
        "current_weather": {"temperature": data.current_temp},
        "warnings": warnings,
    }
    return result


def check_weather_warnings(weather_data: dict) -> list[str]:
    """检查天气数据中的灾害预警。

    优先返回 AlertScraper 获取的官方 warnings 字段；当输入是旧版
    Open-Meteo daily 结构且没有 warnings 时，按阈值生成基础农事预警。

    Args:
        weather_data: 天气数据字典。

    Returns:
        预警信息列表。
    """
    warnings = weather_data.get("warnings")
    if warnings:
        return warnings

    daily = weather_data.get("daily", {})
    times = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    precipitations = daily.get("precipitation_sum", [])
    winds = daily.get("windspeed_10m_max", [])

    inferred: list[str] = []
    for index, day in enumerate(times):
        max_temp = max_temps[index] if index < len(max_temps) else None
        min_temp = min_temps[index] if index < len(min_temps) else None
        precipitation = (
            precipitations[index] if index < len(precipitations) else None
        )
        wind = winds[index] if index < len(winds) else None

        if max_temp is not None and max_temp >= 35:
            inferred.append(f"{day} 高温预警：最高温 {max_temp}℃")
        if min_temp is not None and min_temp <= 0:
            inferred.append(f"{day} 霜冻预警：最低温 {min_temp}℃")
        if precipitation is not None and precipitation >= 50:
            inferred.append(f"{day} 大雨预警：降水量 {precipitation}mm")
        if wind is not None and wind >= 17:
            inferred.append(f"{day} 大风预警：最大风速 {wind}m/s")

    return inferred


__all__ = ["fetch_weather", "check_weather_warnings"]
