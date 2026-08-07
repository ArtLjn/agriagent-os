"""weather skill — 自定义 execute（location 兜底）。

元数据（name/description/parameters_schema）由 skill.md 定义。
本文件只保留自定义逻辑：LLM 不传 location 时从历史/用户输入兜底。
"""

from __future__ import annotations

from typing import Any

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext


class WeatherSkill(Skill):
    """自定义 execute：location 兜底解析。"""

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        # 兜底：LLM 偶尔不传 location（qwen3.6-flash 工具调用质量问题）。
        if not params.get("location"):
            resolved = _resolve_location_from_history(ctx.turn)
            if resolved:
                params = {**params, "location": resolved}
            elif ctx.turn.user_input:
                params = {**params, "location": ctx.turn.user_input}
        if params:
            _patch_action_args(ctx.turn, self.name, params)
        result = await ctx.business_client.call_tool(self.mcp_tool, params)
        return SkillResult(data=result)


def _resolve_location_from_history(turn) -> str | None:
    """从 turn.events 找最近一次 search_cities 的结果，取第一条 full_name。"""
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
    """回写最近一个 action 事件的 arguments，让 UI 展示真实参数。"""
    for event in reversed(turn.events):
        if event.get("type") != "action":
            continue
        data = event.get("data") or {}
        if data.get("tool_name") == tool_name:
            data["arguments"] = actual_params
            return


skill = WeatherSkill()
