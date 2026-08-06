"""Location MCP tools.

提供城市坐标查询能力，让 LLM 在调 get_weather 前先确认城市的精确名称和坐标。
解决"LLM 不知道 regions.json 支持哪些城市"的盲点。
"""
from business.mcp_app import mcp
from business.services import location_service


@mcp.tool
def search_cities(keyword: str = "", limit: int = 10) -> dict:
    """Search supported cities/districts by keyword.

    Use this to resolve a city name to coordinates before calling get_weather.
    Matches against 3366 regions (province/city/district names + aliases).

    Args:
        keyword: Search term. Supports city ("苏州"), district ("东城区"),
                 full name ("北京市东城区"), or alias.
                 Empty returns popular cities as examples.
        limit: Max results to return (1-50, default 10).

    Returns:
        {"keyword": "...", "count": N, "cities": [{name, full_name, province,
        city, adcode, lat, lon}, ...]} sorted by match score.

    Examples:
        search_cities("苏州")  → [苏州市, 苏州工业园区, 虎丘区, ...]
        search_cities("东城")  → [东城区, ...]
        search_cities("北京市") → [东城区, 西城区, ...]

    When to use:
        - Before get_weather if user's location might be ambiguous
        - After get_weather returns error=unknown_location
        - To discover what regions the system supports
    """
    if not keyword:
        # LLM 偶尔会传空 keyword，返回热门城市作为示例引导
        return {
            "keyword": "",
            "count": 0,
            "cities": [],
            "hint": (
                "keyword is required. Pass the city name from user's message, "
                "e.g. search_cities(keyword='苏州')."
            ),
        }
    results = location_service.search_cities(keyword, limit=limit)
    return {
        "keyword": keyword,
        "count": len(results),
        "cities": results,
    }
