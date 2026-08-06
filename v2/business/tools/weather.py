"""Weather MCP tools.

Maps to archive/backend/app/skills/weather skill.

身份注入：location 为空时用 X-Farm-Id 对应农场的默认位置。
"""
from __future__ import annotations

from business.mcp_app import mcp
from business.services import weather_service
from business.tools._headers import get_farm_id_from_headers


@mcp.tool
def get_weather(location: str = "", days: int = 3) -> dict:
    """Get weather forecast for a location.

    Read-only. Returns 3-day forecast by default. If location is unknown,
    returns an 'error' field with a clarifying message — agent should ask
    user to be more specific.

    Args:
      location: City name like "苏州", "北京", or empty to use farm default.
      days: Forecast days (1-7, default 3).

    Examples:
      - "明天苏州什么天气"
      - "最近有雨吗"
      - "宁德的天气"
    """
    if location:
        return weather_service.fetch_weather(location=location, days=days)

    # location 为空时，用 X-Farm-Id 对应农场的默认位置
    from business.services import farm_service

    farm_id = get_farm_id_from_headers()
    farm = farm_service.build_summary(farm_id)
    location = farm.get("location", "苏州")
    return weather_service.fetch_weather(location=location, days=days)
