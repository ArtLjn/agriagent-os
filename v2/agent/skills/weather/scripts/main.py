"""weather skill — 自定义 execute（用户默认位置和 location 兜底）。

元数据（name/description/parameters_schema）由 skill.md 定义。
本文件负责在 LLM 不传 location 时解析当前用户的默认位置，避免 MCP
误用农场位置；如果 Business 返回 unknown_location，则自动搜索城市并重试一次。
"""

from __future__ import annotations

import re
from typing import Any

from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext


class WeatherSkill(Skill):
    """自定义天气查询：位置兜底和未知地点自动重试。"""

    async def execute(self, params: dict[str, Any], ctx: SkillContext) -> SkillResult:
        params = dict(params)
        # 用户明确指定地点时必须保持原值；只有未指定地点才解析默认位置。
        if not params.get("location"):
            resolved = _resolve_location_from_history(ctx.turn)
            if not resolved:
                resolved = await _resolve_location_from_user_input(ctx)
            if not resolved:
                resolved = await _resolve_user_default_location(ctx)
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


async def _resolve_user_default_location(ctx: SkillContext) -> str | None:
    """读取当前用户默认城市，失败时保留 Business 的兼容兜底。"""
    result = await ctx.call_mcp_tool(
        "manage_user_settings",
        {"operation": "query"},
        risk_level="read",
    )
    if not isinstance(result, dict) or result.get("error"):
        return None
    settings = result.get("settings")
    if not isinstance(settings, dict):
        return None
    default_city = settings.get("default_city")
    return str(default_city).strip() if default_city else None


async def _resolve_location_from_user_input(ctx: SkillContext) -> str | None:
    """补偿模型漏传 location 的情况，优先从用户原话解析明确城市。"""
    keyword = _extract_location_candidate(ctx.turn.user_input)
    if not keyword:
        return None
    result = await ctx.call_mcp_tool(
        "search_cities",
        {"keyword": keyword, "limit": 10},
        risk_level="read",
    )
    if not isinstance(result, dict) or result.get("error"):
        return None
    cities = result.get("cities") or []
    full_name = next(
        (
            str(city.get("full_name"))
            for city in cities
            if isinstance(city, dict) and city.get("full_name")
        ),
        "",
    )
    return full_name or None


def _extract_location_candidate(user_input: str) -> str:
    """去掉常见天气意图词，保留可交给 location Skill 的地点词。"""
    candidate = str(user_input or "").strip()
    noise = (
        "帮我查一下",
        "帮我看看",
        "我想知道",
        "告诉我",
        "查询",
        "查一下",
        "查查",
        "请问",
        "看一下",
        "天气预报",
        "天气",
        "预报",
        "气温",
        "温度",
        "预警",
        "未来几天",
        "最近",
        "今天",
        "明天",
        "后天",
        "这周",
        "本周",
        "下周",
        "农场这边",
        "农场",
        "这边",
        "怎么样",
        "如何",
        "怎样",
        "什么",
        "有没有",
        "会不会",
        "是否",
        "下雨",
        "有雨",
        "降雨",
        "大风",
        "高温",
        "多少",
        "是多少",
        "情况",
        "吗",
        "呢",
        "的",
    )
    for item in sorted(noise, key=len, reverse=True):
        candidate = candidate.replace(item, "")
    return re.sub(r"[\s，。！？、,.!?？:：；;（）()]+", "", candidate)


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
