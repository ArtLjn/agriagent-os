"""farm-status skill: 通过 MCP 调用 business.get_farm_status。"""
from __future__ import annotations

from typing import Any

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext


class FarmStatusSkill(Skill):
    """查询农场整体状态。"""

    kind = "mcp"
    mcp_tool = "get_farm_status"

    @property
    def name(self) -> str:
        return "get_farm_status"

    @property
    def description(self) -> str:
        return (
            "查询农场当前整体状态：活跃茬口、最近 7 天农事、今日天气。"
            "用户问'农场怎么样'、'整体情况'时使用。"
        )

    @property
    def risk_level(self) -> str:
        return "read"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        result = await ctx.business_client.call_tool(self.mcp_tool, params or {})
        return SkillResult(data=result)


skill = FarmStatusSkill()
