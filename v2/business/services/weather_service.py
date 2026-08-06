"""Weather service.

Provider 优先级：
  1. QWeather（和风天气）—— 配置 config.yaml secrets.qweather_api_key 时启用
  2. Open-Meteo —— 无需 API key，作为 fallback

参考 archive/backend/app/domains/weather/providers/qweather.py。
和风 API 用法：
  - Geo API:  /v2/city/lookup?location=<city>&key=<key>
  - Weather:  /v7/weather/3d?location=<location_id>&key=<key>
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from business.config import settings

logger = logging.getLogger(__name__)

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_QWEATHER_BASE = "https://p32k5pxvta.re.qweatherapi.com/v7"
_QWEATHER_GEO = "https://p32k5pxvta.re.qweatherapi.com/v2/city/lookup"

# WMO weather code → 中文描述（Open-Meteo 用）
_WMO_DESC = {
    0: "晴",
    1: "晴间多云",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "冻雾",
    51: "毛毛雨",
    53: "毛毛雨",
    55: "毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "霰",
    80: "阵雨",
    81: "中阵雨",
    82: "强阵雨",
    85: "阵雪",
    86: "强阵雪",
    95: "雷暴",
    96: "雷暴伴冰雹",
    99: "强雷暴伴冰雹",
}


def _qweather_key() -> str:
    """从 config.yaml secrets 读和风天气 API Key（env 可覆盖）。"""
    return settings.secrets.qweather_api_key.strip()


# ─────────────────────────────────────────────────────────────
# QWeather provider
# ─────────────────────────────────────────────────────────────


async def _qweather_lookup_city(client: httpx.AsyncClient, city: str) -> str | None:
    """通过 Geo API 查询城市 location id。"""
    r = await client.get(
        _QWEATHER_GEO,
        params={"location": city, "key": _qweather_key()},
        timeout=10.0,
    )
    r.raise_for_status()
    data = r.json()
    locations = data.get("location") or []
    if not locations:
        return None
    return locations[0].get("id")


async def _fetch_qweather_by_coords(
    client: httpx.AsyncClient, lat: float, lon: float, days: int
) -> dict[str, Any]:
    """用经纬度调用和风天气（跳过 Geo API，QWeather 支持 location=lon,lat）。"""
    endpoint = "7d" if days > 3 else "3d"
    r = await client.get(
        f"{_QWEATHER_BASE}/weather/{endpoint}",
        params={"location": f"{lon},{lat}", "key": _qweather_key()},
        timeout=10.0,
    )
    r.raise_for_status()
    return r.json()


async def _fetch_qweather_now(
    client: httpx.AsyncClient, lat: float, lon: float
) -> float | None:
    """获取实时温度（QWeather now 接口）。"""
    try:
        r = await client.get(
            f"{_QWEATHER_BASE}/weather/now",
            params={"location": f"{lon},{lat}", "key": _qweather_key()},
            timeout=5.0,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") == "200":
            now = data.get("now", {})
            return float(now.get("temp", 0))
    except Exception:
        logger.warning("qweather now fetch failed")
    return None


def _summarize_qweather(
    raw: dict, location: str, current_temp: float | None = None
) -> dict:
    """Trim QWeather response to fields agent cares about.

    QWeather v7 /weather/3d 返回 daily 为 list of dict，
    每个元素含 fxDate/tempMax/tempMin/textDay/precip/windSpeedDay 等。
    """
    daily_list = raw.get("daily") or []
    summary = {
        "location": location,
        "provider": "qweather",
        "current_temp": current_temp,
        "daily": [
            {
                "date": day.get("fxDate", ""),
                "max_c": float(day.get("tempMax", 0)),
                "min_c": float(day.get("tempMin", 0)),
                "precip_mm": float(day.get("precip", 0) or 0),
                "wind_mps": float(day.get("windSpeedDay", 0) or 0),
                "code": None,
                "desc": day.get("textDay", ""),
            }
            for day in daily_list[:3]
        ],
    }
    return summary


# ─────────────────────────────────────────────────────────────
# Open-Meteo provider (fallback)
# ─────────────────────────────────────────────────────────────


async def _fetch_open_meteo(
    lat: float, lon: float, days: int = 3
) -> dict[str, Any]:
    """Call Open-Meteo and return raw daily/hourly payload."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "auto",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,"
        "windspeed_10m_max,weathercode",
        "forecast_days": max(1, min(days, 7)),
        "current": "temperature_2m",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(_OPEN_METEO_URL, params=params)
        r.raise_for_status()
        return r.json()


def _summarize_open_meteo(raw: dict, location: str) -> dict:
    """Trim raw API payload to fields agent cares about."""
    daily_raw = raw.get("daily", {})
    times = daily_raw.get("time", [])
    summary = {
        "location": location,
        "provider": "open-meteo",
        "current_temp": raw.get("current_weather", {}).get("temperature")
        or raw.get("current", {}).get("temperature_2m"),
        "daily": [
            {
                "date": times[i],
                "max_c": daily_raw["temperature_2m_max"][i],
                "min_c": daily_raw["temperature_2m_min"][i],
                "precip_mm": daily_raw["precipitation_sum"][i],
                "wind_mps": daily_raw["windspeed_10m_max"][i],
                "code": daily_raw["weathercode"][i],
                "desc": _WMO_DESC.get(daily_raw["weathercode"][i], "未知"),
            }
            for i in range(min(len(times), 3))
        ],
    }
    return summary


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────


def _city_coords(city: str) -> tuple[float, float] | None:
    """Lookup coordinates from location_service (backed by regions.json).

    委托给 location_service.find_coords，避免 weather_service 直接持有 regions.json
    缓存和匹配逻辑。location_service 提供 search_cities MCP 工具给 LLM 主动查询，
    这里只取最佳匹配的坐标。
    """
    from business.services import location_service

    coords = location_service.find_coords(city)
    if coords is not None:
        return coords

    # config.yaml 默认农场位置（徐州）作为最后兜底
    if city in ("徐州", "徐州市"):
        return settings.weather.latitude, settings.weather.longitude
    return None


async def _fetch_weather_async(
    location: str,
    lat: float | None,
    lon: float | None,
    days: int,
) -> dict:
    """异步获取天气，优先 QWeather，失败降级 Open-Meteo。

    QWeather Geo API (/v2/city/lookup) 不可用（404），
    因此直接用 lat/lon 查 QWeather 天气接口（QWeather 支持经纬度查询）。
    """
    # ── 1. 解析坐标 ────────────────────────────────────────────
    if lat is None or lon is None:
        coords = _city_coords(location)
        if coords is None:
            return {
                "error": "unknown_location",
                "message": (
                    f"无法解析「{location}」的坐标。"
                    "请调用 search_cities 工具查询支持的城市列表，"
                    "再用返回的 full_name 重新调用 get_weather。"
                ),
                "hint": "call search_cities first",
            }
        lat, lon = coords
        # 用匹配到的城市全名覆盖原始 location（可能是自然语言如"明天苏州天气"）
        from business.services import location_service

        matched = location_service.search_cities(location, limit=1)
        if matched:
            location = matched[0].get("full_name") or location

    # ── 2. Try QWeather (直接用经纬度，跳过 Geo API) ─────────────
    if _qweather_key():
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                raw = await _fetch_qweather_by_coords(client, lat, lon, days)
                current_temp = await _fetch_qweather_now(client, lat, lon)
                return _summarize_qweather(raw, location, current_temp)
        except Exception as exc:  # noqa: BLE001
            logger.warning("qweather fetch failed, fallback to open-meteo: %s", exc)

    # ── 3. Fallback: Open-Meteo ────────────────────────────────
    try:
        raw = await _fetch_open_meteo(lat, lon, days)
        return _summarize_open_meteo(raw, location)
    except httpx.HTTPError as exc:
        logger.warning("open-meteo fetch failed: %s", exc)
        return {"error": "fetch_failed", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("unexpected weather error")
        return {"error": "internal", "message": str(exc)}


def fetch_weather(
    location: str,
    lat: float | None = None,
    lon: float | None = None,
    days: int = 3,
) -> dict:
    """Synchronous wrapper used by tools (FastMCP tools can be sync).

    Provider 优先级：QWeather（若配 QWEATHER_API_KEY）→ Open-Meteo。
    默认坐标取自 archive config weather.latitude/longitude（徐州 34.26/117.18）。
    Returns dict with location/current_temp/daily[] on success,
    or {'error': '...'} on failure (never raises).
    """
    return asyncio.run(_fetch_weather_async(location, lat, lon, days))
