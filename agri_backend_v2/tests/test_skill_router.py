"""LLM Skill Router 与 Registry 能力投影契约测试。"""

from __future__ import annotations

import json

import pytest

from agent.domains.harness.router import SkillRouter
from agent.domains.harness.tools.base import Skill
from agent.domains.harness.tools.registry import SkillRegistry


class _RouterSkill(Skill):
    def __init__(self, name: str, description: str, capabilities: list[str]) -> None:
        self._meta = {
            "name": name,
            "description": description,
            "capabilities": capabilities,
            "context": {"dependencies": ["session_summary"]},
            "parameters": {"type": "object", "properties": {}, "required": []},
        }


def _registry() -> SkillRegistry:
    return SkillRegistry.from_skills(
        [
            _RouterSkill("weather", "查询天气", ["天气", "预报"]),
            _RouterSkill("location", "解析城市", ["城市", "位置"]),
            _RouterSkill("cost", "管理账务", ["记账", "成本"]),
        ]
    )


@pytest.mark.asyncio
async def test_router_sends_metadata_without_tool_schema() -> None:
    captured: dict[str, object] = {}

    def fake_llm(messages):
        captured["messages"] = messages
        return {"content": '{"skills":["weather","location"]}'}

    result = await SkillRouter(llm_call=fake_llm).route("苏州明天天气", _registry())

    assert result.selected_skills == ("weather", "location")
    assert result.status == "selected"
    request = json.loads(captured["messages"][1]["content"])
    assert request["user_request"] == "苏州明天天气"
    assert all("parameters" not in item for item in request["skills"])
    assert request["skills"][0]["context_dependencies"] == ["session_summary"]


@pytest.mark.asyncio
async def test_router_rejects_unknown_skill_and_falls_back() -> None:
    def fake_llm(_messages):
        return {"content": '{"skills":["not_registered"]}'}

    result = await SkillRouter(llm_call=fake_llm).route("查天气", _registry())

    assert result.selected_skills == ()
    assert result.status == "fallback"
    assert result.decision_source == "all_tools_fallback"
    assert result.error == "router_failed:ValueError"


@pytest.mark.asyncio
async def test_router_limits_selected_skills() -> None:
    def fake_llm(_messages):
        return {"content": '{"skills":["weather","location","cost"]}'}

    result = await SkillRouter(max_skills=2, llm_call=fake_llm).route(
        "综合查询", _registry()
    )

    assert result.selected_skills == ("weather", "location")


@pytest.mark.asyncio
async def test_router_accepts_replaceable_backend() -> None:
    class _Backend:
        async def choose(self, user_input, catalog):
            assert user_input == "查天气"
            assert [item["name"] for item in catalog] == [
                "cost",
                "location",
                "weather",
            ]
            return {"content": '{"skills":["weather"]}'}

    result = await SkillRouter(backend=_Backend()).route("查天气", _registry())

    assert result.selected_skills == ("weather",)


def test_registry_exposes_router_catalog_separately_from_tools() -> None:
    registry = _registry()

    catalog = registry.router_catalog()
    tools = registry.tools_for_router_skills(("weather",))
    dependencies = registry.context_dependencies_for_router_skills(("weather",))

    assert [item["name"] for item in catalog] == ["cost", "location", "weather"]
    assert "parameters" not in catalog[2]
    assert [tool["function"]["name"] for tool in tools] == ["weather"]
    assert dependencies == ("session_summary",)
