"""天气服务模块，使用 Open-Meteo 免费 API 获取天气预报与预警。"""

import httpx

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather(lat: float, lon: float, days: int = 7) -> dict:
    """获取指定坐标的未来 N 天天气预报。

    Args:
        lat: 纬度。
        lon: 经度。
        days: 预报天数（默认 7 天）。

    Returns:
        包含 daily 预报数据和 location 信息的字典。

    Raises:
        RuntimeError: 网络请求失败时抛出。
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "windspeed_10m_max",
        ],
        "timezone": "auto",
        "forecast_days": days,
    }
    try:
        response = httpx.get(OPEN_METEO_URL, params=params, timeout=10)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"天气 API 请求失败: {exc}") from exc

    data = response.json()
    data["location"] = {"latitude": lat, "longitude": lon}
    return data


def check_weather_warnings(weather_data: dict) -> list[str]:
    """检查天气数据中的灾害预警。

    预警规则：
    - 高温：日最高温 >= 35°C
    - 霜冻：日最低温 <= 0°C
    - 大雨：日降水量 >= 50mm
    - 大风：日最大风速 >= 17 m/s（7 级风）

    Args:
        weather_data: Open-Meteo 返回的天气数据字典。

    Returns:
        预警信息列表，每项格式为 "YYYY-MM-DD: 预警类型（数值）"。
    """
    warnings: list[str] = []
    daily = weather_data.get("daily", {})
    times = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    precipitations = daily.get("precipitation_sum", [])
    wind_speeds = daily.get("windspeed_10m_max", [])

    for i, day in enumerate(times):
        max_temp = max_temps[i] if i < len(max_temps) else None
        min_temp = min_temps[i] if i < len(min_temps) else None
        precip = precipitations[i] if i < len(precipitations) else None
        wind = wind_speeds[i] if i < len(wind_speeds) else None

        if max_temp is not None and max_temp >= 35:
            warnings.append(f"{day}: 高温预警（{max_temp}°C）")
        if min_temp is not None and min_temp <= 0:
            warnings.append(f"{day}: 霜冻预警（{min_temp}°C）")
        if precip is not None and precip >= 50:
            warnings.append(f"{day}: 大雨预警（{precip}mm）")
        if wind is not None and wind >= 17:
            warnings.append(f"{day}: 大风预警（{wind}m/s）")

    return warnings


__all__ = ["fetch_weather", "check_weather_warnings"]
