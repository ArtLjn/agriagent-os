"""Farm MCP tools.

Maps to archive/backend/app/skills/farm-status skill: business logic now
lives in business/services/farm_service.py, exposed as MCP tool here.

身份注入：agent 通过 BusinessClient headers 传入 X-Farm-Id，
本工具从 HTTP 请求头读取后传给 service 层做农场隔离。
"""
from __future__ import annotations

from business.mcp_app import mcp
from business.services import farm_service
from business.tools._headers import get_farm_id_from_headers


@mcp.tool
def get_farm_status() -> dict:
    """Get current farm summary: active crop cycles, recent logs, weather today.

    Read-only. Use when user asks about overall farm state, current planting,
    or needs context overview before drilling into specifics.

    Examples:
      - "我的农场现在怎么样"
      - "农场整体情况"
      - "当前茬口状态"
    """
    farm_id = get_farm_id_from_headers()
    return farm_service.build_summary(farm_id)
