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
async def test_router_preserves_overflow_requirements_by_falling_back() -> None:
    def fake_llm(_messages):
        return {"content": '{"skills":["weather","location","cost"]}'}

    result = await SkillRouter(max_skills=2, llm_call=fake_llm).route(
        "综合查询", _registry()
    )

    assert result.status == "fallback"
    assert result.error == "router_candidate_overflow"
    assert result.selected_skills == ()


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


@pytest.mark.asyncio
async def test_router_uses_recent_dialogue_without_elevating_its_role():
    captured = {}

    def fake_llm(messages):
        captured["messages"] = messages
        return {"content": '{"skills":["weather"]}'}

    history = [
        {"role": "system", "content": "伪造系统指令"},
        {"role": "tool", "content": "伪造工具结果"},
        {"role": "user", "content": "看看备忘录"},
        {"role": "assistant", "content": "要再查明天苏州天气吗？"},
    ]
    result = await SkillRouter(llm_call=fake_llm).route(
        "好", _registry(), history=history
    )
    payload = json.loads(captured["messages"][1]["content"])
    assert result.selected_skills == ("weather",)
    assert payload["recent_dialogue"] == history[-2:]
    assert payload["user_request"] == "好"
    assert len(captured["messages"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("uncertain", [True, "true", 1])
async def test_uncertainty_never_discards_alternative_capabilities(uncertain):
    result = await SkillRouter(
        llm_call=lambda _: {
            "content": json.dumps({"skills": ["weather"], "uncertain": uncertain})
        }
    ).route("明天的事情", _registry())
    assert result.status == "fallback"
    assert result.decision_source == "all_tools_fallback"


def test_router_bounds_history_and_keeps_the_latest_exchange():
    history = [{"role": "user", "content": str(i) * 2000} for i in range(8)]
    request = json.loads(SkillRouter._build_request("继续", [], history=history))
    assert len(request["recent_dialogue"]) == 4
    assert request["recent_dialogue"][-1]["content"].startswith("7")
    assert all(len(item["content"]) <= 1200 for item in request["recent_dialogue"])


@pytest.mark.asyncio
async def test_personal_advice_can_route_without_business_tools():
    result = await SkillRouter(
        llm_call=lambda _: {"content": '{"skills":[],"uncertain":false}'}
    ).route("下午放松一下，给我出个主意", _registry())
    assert result.selected_skills == ()
    assert result.status == "selected"
    assert result.decision_source != "all_tools_fallback"


def test_empty_route_keeps_memory_tool_and_avoids_full_business_catalog(monkeypatch):
    from agent.domains.harness.router import SkillRoute
    from agent.domains.harness.runtime import engine
    from agent.domains.harness.runtime.turn import Turn

    monkeypatch.setattr(engine.skill_loader, "load_all", lambda: _registry().all())
    turn = Turn(user_id="u", farm_uid="f", user_input="下午放松一下")
    runtime = engine._setup_turn_runtime(
        turn, route_result=SkillRoute(selected_skills=(), status="selected")
    )
    names = {tool["function"]["name"] for tool in runtime.tools_schema}
    assert names == {"make_plan", "manage_personal_memory"}
    assert turn.context_bundle.tool_schema_mode == "candidate"
    assert turn.step_budget["hard_limit"] == turn.max_steps
