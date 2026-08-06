"""Weather MCP tools.

Maps to archive/backend/app/skills/weather skill.
"""
from business.mcp_app import mcp
from business.services import weather_service


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
    # If user did not provide location, fall back to farm's default (farm_id=1 MVP).
    if not location:
        from business.services import farm_service

        farm = farm_service.build_summary()
        location = farm.get("location", "苏州")
        return weather_service.fetch_weather(location=location, days=days)

    return weather_service.fetch_weather(location=location, days=days)
