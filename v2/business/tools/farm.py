"""Farm MCP tools.

Maps to archive/backend/app/skills/farm-status skill: business logic now
lives in business/services/farm_service.py, exposed as MCP tool here.
"""
from business.mcp_app import mcp
from business.services import farm_service


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
    return farm_service.build_summary()
