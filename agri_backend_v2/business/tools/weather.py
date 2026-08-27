"""Weather MCP tools.

Maps to archive/backend/app/skills/weather skill.

身份注入：location 为空时用 X-Farm-Id 对应农场的默认位置。
"""

from __future__ import annotations

from business.mcp_app import mcp
from business.services import weather_service
from business.tools._headers import get_farm_id_from_headers, get_principal
from shared.roles import Permission


@mcp.tool
def get_weather(location: str = "", days: int = 3) -> dict:
    """查询天气预报、官方预警和基于阈值推导的农事风险。

    预警源不可用时不会阻断天气预报，但响应会保留 warnings 字段。

    Args:
      location: 城市或区县名，如“苏州”“北京”；为空时使用农场默认位置。
      days: 预报天数（1-7，默认 3）。

    Examples:
      - “明天苏州什么天气”
      - “最近有雨吗”
      - “宁德有没有灾害预警”
    """
    # 明确城市时也要校验 MCP 和天气读取权限，不能让 location 分支跳过鉴权。
    get_principal(Permission.FARM_READ)
    if location:
        return weather_service.fetch_weather(location=location, days=days)

    # location 为空时，用 X-Farm-Id 对应农场的默认位置
    from business.services import farm_service

    farm_id = get_farm_id_from_headers()
    farm = farm_service.build_summary(farm_id)
    location = farm.get("location") or "苏州"
    return weather_service.fetch_weather(location=location, days=days)
