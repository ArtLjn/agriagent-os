"""weather skill — 自定义 execute（location 兜底）。

元数据（name/description/parameters_schema）由 skill.md 定义。
本文件只保留自定义逻辑：LLM 不传 location 时复用本轮已解析的位置。
如果 Business 返回 unknown_location，则自动搜索城市并重试一次。
"""

from __future__ import annotations

from typing import Any

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext


class WeatherSkill(Skill):
    """自定义天气查询：位置兜底和未知地点自动重试。"""

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        params = dict(params)
        # 未指定地点时保留空参数，让 Business 按农场默认位置查询。
        # 用户原话不是地点，不能把“查询天气如何”直接传给天气服务。
        if not params.get("location"):
            resolved = _resolve_location_from_history(ctx.turn)
            if resolved:
                params = {**params, "location": resolved}
        if params:
            _patch_action_args(ctx.turn, self.name, params)
        result = await ctx.call_mcp_tool(
            self.mcp_tool,
            params,
            risk_level="read",
        )
        if isinstance(result, dict) and result.get("error") == "unknown_location":
            result = await _retry_unknown_location(result, params, ctx)
        return _as_skill_result(result)


async def _retry_unknown_location(
    first_result: dict[str, Any], params: dict[str, Any], ctx: SkillContext
) -> dict[str, Any]:
    """按 Skill 约定搜索城市并用首个完整地点重试天气查询。"""
    keyword = str(params.get("location") or ctx.turn.user_input or "").strip()
    search_params = {"keyword": keyword}
    search_result = await ctx.call_mcp_tool(
        "search_cities",
        search_params,
        risk_level="read",
    )
    if isinstance(search_result, dict) and search_result.get("error"):
        return search_result

    cities = search_result.get("cities", []) if isinstance(search_result, dict) else []
    full_name = next(
        (
            str(city.get("full_name"))
            for city in cities
            if isinstance(city, dict) and city.get("full_name")
        ),
        "",
    )
    if not full_name:
        return {
            **first_result,
            "error": "unknown_location",
            "message": f"无法找到「{keyword}」对应的支持城市。",
        }

    retry_params = {**params, "location": full_name}
    _patch_action_args(ctx.turn, "get_weather", retry_params)
    return await ctx.call_mcp_tool(
        "get_weather",
        retry_params,
        risk_level="read",
    )


def _as_skill_result(result: Any) -> SkillResult:
    """遵循通用 MCP Skill 约定，将 Business 错误暴露给 Agent。"""
    if isinstance(result, dict) and result.get("error"):
        return SkillResult(
            data=result,
            error=str(result.get("message") or result.get("error")),
        )
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
