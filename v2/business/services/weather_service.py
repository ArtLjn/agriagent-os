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
_CMA_ALARM_URL = "https://weather.cma.cn/api/map/alarm"
_CMA_HEADERS = {
    "Referer": "https://weather.cma.cn/",
    "User-Agent": "Mozilla/5.0 (compatible; FarmManagerWeather/2.0)",
}

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
    raw: dict,
    location: str,
    current_temp: float | None = None,
    days: int = 3,
) -> dict:
    """Trim QWeather response to fields agent cares about.

    QWeather v7 /weather/3d 返回 daily 为 list of dict，
    每个元素含 fxDate/tempMax/tempMin/textDay/precip/windSpeedDay 等。
    """
    daily_list = raw.get("daily") or []
    forecast_days = max(1, min(days, 7))
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
            for day in daily_list[:forecast_days]
        ],
    }
    return summary


# ─────────────────────────────────────────────────────────────
# Open-Meteo provider (fallback)
# ─────────────────────────────────────────────────────────────


async def _fetch_open_meteo(lat: float, lon: float, days: int = 3) -> dict[str, Any]:
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


def _summarize_open_meteo(raw: dict, location: str, days: int = 3) -> dict:
    """Trim raw API payload to fields agent cares about."""
    daily_raw = raw.get("daily", {})
    times = daily_raw.get("time", [])
    forecast_days = max(1, min(days, 7))
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
            for i in range(min(len(times), forecast_days))
        ],
    }
    return summary


def _alert_terms_for(location: str) -> set[str]:
    """生成预警匹配词，兼容地级市、区县标题和正文提及。"""
    cleaned = (location or "").strip()
    if not cleaned or cleaned in {"当前地块", "地块"}:
        return set()

    from business.services import location_service

    matches = location_service.search_cities(cleaned, limit=1)
    terms: set[str] = set()
    if matches:
        region = matches[0]
        for key in ("city", "name", "full_name"):
            value = str(region.get(key) or "").strip()
            if value:
                terms.add(value)
                terms.add(_strip_city_suffix(value))
    else:
        terms.add(cleaned)
        terms.add(_strip_city_suffix(cleaned))

    return {term for term in terms if len(term) >= 2}


def _strip_city_suffix(value: str) -> str:
    """移除城市名称后缀，适配气象局预警标题中的城市写法。"""
    for suffix in ("自治区", "自治州", "地区", "盟", "市"):
        if value.endswith(suffix) and len(value) > len(suffix):
            return value[: -len(suffix)]
    return value


def _parse_official_alerts(payload: dict[str, Any], city: str | set[str]) -> list[str]:
    """解析中国气象局预警响应，匹配标题、名称和正文中的地点。"""
    if payload.get("code") not in (0, "0"):
        logger.warning(
            "official weather alert API returned code=%s", payload.get("code")
        )
        return []

    terms = {city} if isinstance(city, str) else city
    alerts: list[str] = []
    seen: set[str] = set()
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        headline = str(item.get("headline") or "").strip()
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        searchable = " ".join((headline, title, description))
        if terms:
            if not any(term in searchable for term in terms):
                continue
        message = headline or title
        if description:
            message = f"{message}: {description}" if message else description
        if message and message not in seen:
            seen.add(message)
            alerts.append(message)
    return alerts


async def _fetch_official_alerts(location: str) -> list[str]:
    """获取官方气象预警；预警源不可用时不影响天气预报主链路。"""
    terms = _alert_terms_for(location)
    if not terms:
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(_CMA_ALARM_URL, headers=_CMA_HEADERS)
            response.raise_for_status()
            return _parse_official_alerts(response.json(), terms)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("official weather alert fetch failed: %s", exc)
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("unexpected official weather alert error: %s", exc)
        return []


async def _await_official_alerts(task: asyncio.Task[list[str]]) -> list[str]:
    """安全收敛并行预警任务，避免预报失败时留下未处理异常。"""
    try:
        return await task
    except Exception as exc:  # noqa: BLE001
        logger.warning("official weather alert task failed: %s", exc)
        return []


def _number(value: Any) -> float | None:
    """将天气供应商字段安全转换为数值。"""
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _infer_weather_warnings(daily: list[dict[str, Any]]) -> list[str]:
    """按旧版农事阈值生成预警，弥补 Open-Meteo 没有官方预警字段。"""
    warnings: list[str] = []
    for day in daily:
        date = str(day.get("date") or "未知日期")
        max_temp = _number(day.get("max_c"))
        min_temp = _number(day.get("min_c"))
        precipitation = _number(day.get("precip_mm"))
        wind = _number(day.get("wind_mps"))

        if max_temp is not None and max_temp >= 35:
            warnings.append(f"{date} 高温预警：最高温 {max_temp:g}℃")
        if min_temp is not None and min_temp <= 0:
            warnings.append(f"{date} 霜冻预警：最低温 {min_temp:g}℃")
        if precipitation is not None and precipitation >= 50:
            warnings.append(f"{date} 大雨预警：降水量 {precipitation:g}mm")
        if wind is not None and wind >= 17:
            warnings.append(f"{date} 大风预警：最大风速 {wind:g}m/s")
    return warnings


def _to_client_days(daily: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """保留 Agent 友好的 daily，同时提供前端现有契约使用的 days。"""
    return [
        {
            "date": day.get("date", ""),
            "max_temp": day.get("max_c", 0),
            "min_temp": day.get("min_c", 0),
            "precipitation": day.get("precip_mm", 0),
            "weather_code": day.get("code"),
            "weather_text": day.get("desc"),
            "wind_speed": day.get("wind_mps", 0),
        }
        for day in daily
    ]


def _complete_summary(summary: dict[str, Any], official_alerts: list[str]) -> dict:
    """统一补充预警和跨 Agent/前端使用的响应字段。"""
    daily = summary.get("daily") or []
    inferred = _infer_weather_warnings(daily)
    warnings = list(dict.fromkeys([*official_alerts, *inferred]))
    summary["warnings"] = warnings
    summary["days"] = _to_client_days(daily)
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

    # 预警是增强信息，和主天气请求并行；失败时仍保留预报结果。
    official_alerts_task = asyncio.create_task(_fetch_official_alerts(location))

    # ── 2. Try QWeather (直接用经纬度，跳过 Geo API) ─────────────
    if _qweather_key():
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                raw = await _fetch_qweather_by_coords(client, lat, lon, days)
                current_temp = await _fetch_qweather_now(client, lat, lon)
                summary = _summarize_qweather(raw, location, current_temp, days)
                return _complete_summary(
                    summary, await _await_official_alerts(official_alerts_task)
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("qweather fetch failed, fallback to open-meteo: %s", exc)

    # ── 3. Fallback: Open-Meteo ────────────────────────────────
    try:
        raw = await _fetch_open_meteo(lat, lon, days)
        summary = _summarize_open_meteo(raw, location, days)
        return _complete_summary(
            summary, await _await_official_alerts(official_alerts_task)
        )
    except httpx.HTTPError as exc:
        await _await_official_alerts(official_alerts_task)
        logger.warning("open-meteo fetch failed: %s", exc)
        return {"error": "fetch_failed", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        await _await_official_alerts(official_alerts_task)
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
