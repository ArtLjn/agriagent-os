"""location skill: 通过 MCP 调用 business.search_cities。

让 LLM 在调 get_weather 前能主动查询支持的城市列表和坐标，
解决"LLM 不知道 regions.json 支持哪些城市"的盲点。
"""
from __future__ import annotations

from typing import Any

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext


class SearchCitiesSkill(Skill):
    """查询支持的城市/区县列表（含坐标）。"""

    kind = "mcp"
    mcp_tool = "search_cities"

    @property
    def name(self) -> str:
        return "search_cities"

    @property
    def description(self) -> str:
        return (
            "查询系统支持的城市/区县列表（含坐标）。"
            "调 get_weather 前如果不确定城市名是否支持，或 get_weather 返回 "
            "error=unknown_location 时，用此工具查找正确的城市全名。"
            "支持城市名（苏州）、区县名（东城区）、全名（北京市东城区）模糊匹配。"
        )

    @property
    def risk_level(self) -> str:
        return "read"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": (
                        "搜索关键词，如'苏州'、'东城'、'北京市东城区'。"
                        "必传，从用户消息中提取城市名作为 keyword。"
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "最多返回条数（1-50，默认 10）。",
                },
            },
            "required": [],
        }

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        # 兜底：LLM 偶尔不传 keyword（qwen3.6-flash 工具调用质量问题），
        # 此时用用户原消息作为 keyword 让 location_service 模糊匹配。
        # location_service 会忽略无关词，只匹配到城市名。
        if not params.get("keyword"):
            params = {**params, "keyword": ctx.turn.user_input}
        if params:
            _patch_action_args(ctx.turn, self.name, params)
        result = await ctx.business_client.call_tool(self.mcp_tool, params)
        return SkillResult(data=result)


def _patch_action_args(turn, tool_name: str, actual_params: dict[str, Any]) -> None:
    """回写最近一个 action 事件的 arguments，让 UI 展示真实传给 business 的参数。"""
    for event in reversed(turn.events):
        if event.get("type") != "action":
            continue
        data = event.get("data") or {}
        if data.get("tool_name") == tool_name:
            data["arguments"] = actual_params
            return


skill = SearchCitiesSkill()
