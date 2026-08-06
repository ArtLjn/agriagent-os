"""weather skill: 通过 MCP 调用 business.get_weather。"""
from __future__ import annotations

from typing import Any

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext


class WeatherSkill(Skill):
    """查询天气预报。"""

    kind = "mcp"
    mcp_tool = "get_weather"

    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return (
            "查询指定位置的天气预报（最多 7 天）。"
            "location 留空则用农场默认位置。"
            "如返回 error=unknown_location，请调用 search_cities 工具"
            "查找支持的城市，再用 full_name 重新调用本工具。"
        )

    @property
    def risk_level(self) -> str:
        return "read"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "城市名，如'苏州'、'北京'。留空用农场默认。",
                },
                "days": {
                    "type": "integer",
                    "description": "预报天数 1-7，默认 3",
                },
            },
            "required": [],
        }

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        # 兜底：LLM 偶尔不传 location（qwen3.6-flash 工具调用质量问题）。
        # 优先级：
        #   1. 本 turn 内先调过 search_cities → 取其第一条 full_name
        #   2. 仍未解析 → 用 user_input 整段作为 location，让 weather_service 模糊匹配
        if not params.get("location"):
            resolved = _resolve_location_from_history(ctx.turn)
            if resolved:
                params = {**params, "location": resolved}
            elif ctx.turn.user_input:
                # 让 weather_service 的 _city_coords 做反向包含匹配
                params = {**params, "location": ctx.turn.user_input}
        if params:
            _patch_action_args(ctx.turn, self.name, params)
        result = await ctx.business_client.call_tool(self.mcp_tool, params)
        return SkillResult(data=result)


def _resolve_location_from_history(turn) -> str | None:
    """从 turn.events 找最近一次 search_cities 的结果，取第一条 full_name。

    LLM 调用顺序通常是 search_cities → get_weather，所以从 events 末尾反向找。
    """
    for event in reversed(turn.events):
        if event.get("type") != "observation":
            continue
        data = event.get("data") or {}
        if data.get("tool_name") != "search_cities":
            continue
        result = data.get("result") or {}
        cities = result.get("cities") or []
        if cities:
            full_name = cities[0].get("full_name")
            if full_name:
                return full_name
    return None


def _patch_action_args(turn, tool_name: str, actual_params: dict[str, Any]) -> None:
    """回写最近一个 action 事件的 arguments，让 UI 展示真实传给 business 的参数。

    LLM 常传空参数 {}，skill 兜底替换后 action 事件还是旧值。
    在 skill execute 调用 business 前调用本函数修正。
    """
    for event in reversed(turn.events):
        if event.get("type") != "action":
            continue
        data = event.get("data") or {}
        if data.get("tool_name") == tool_name:
            data["arguments"] = actual_params
            return


skill = WeatherSkill()
