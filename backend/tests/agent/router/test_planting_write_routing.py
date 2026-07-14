"""种植写操作路由回归测试。"""

from unittest.mock import MagicMock

import pytest

from app.agent.router.catalog import SkillCatalog
from app.agent.router.service import SkillRouter

pytestmark = pytest.mark.no_db


def _tool(name: str, description: str = ""):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    return tool


def test_catalog_enriches_manage_crop_cycle_metadata() -> None:
    catalog = SkillCatalog.from_tools([_tool("manage_crop_cycle")])

    candidate = catalog.get("manage_crop_cycle")

    assert candidate is not None
    assert candidate.domain == "crop"
    assert candidate.capability == "manage_crop_cycle"
    assert candidate.operation is None
    assert candidate.risk == "read"
    assert "create_cycle" in candidate.intents
    assert "crop_templates" in candidate.context_dependencies


def test_create_crop_template_intent_routes_to_write_tool() -> None:
    tools = [
        _tool("manage_crop_templates"),
        _tool("get_farm_status"),
    ]

    decision = SkillRouter().route("帮我创建黑布林种植模板", tools)

    assert decision.selected_tools == ["manage_crop_templates"]
    assert decision.frames[0].intent == "create_crop_template"
    assert decision.frames[0].risk == "write_confirm"


@pytest.mark.parametrize("message", ["我想种黑布林的", "我想种个30亩", "准备种黑布林"])
def test_planting_planning_intent_keeps_read_tools(message: str) -> None:
    tools = [
        _tool("get_farm_status"),
        _tool("manage_crop_cycle"),
        _tool("manage_crop_templates"),
    ]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools != ["manage_crop_cycle"]
    assert "manage_crop_templates" not in decision.selected_tools
    assert decision.frames[0].risk == "read"
    assert decision.fallback == "model_choice_read_default"


def test_explicit_create_crop_cycle_intent_routes_to_write_tool() -> None:
    tools = [
        _tool("get_farm_status"),
        _tool("manage_crop_cycle"),
        _tool("manage_crop_templates"),
    ]

    decision = SkillRouter().route("帮我建个黑布林茬口30亩", tools)

    assert decision.selected_tools == ["manage_crop_cycle"]
    assert decision.frames[0].intent == "create_crop_cycle"
    assert decision.frames[0].risk == "write_confirm"


@pytest.mark.parametrize("message", ["黑布林怎么种", "怎么种小麦", "种小麦要注意什么"])
def test_planting_advice_keeps_read_tool(message: str) -> None:
    tools = [_tool("get_farm_status"), _tool("manage_crop_cycle")]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == ["get_farm_status"]
    assert "manage_crop_cycle" not in decision.selected_tools
    assert decision.frames[0].intent == "query_planting_advice"


@pytest.mark.parametrize("message", ["有哪些作物模板", "模板列表"])
def test_planting_read_queries_do_not_expose_write_tools(message: str) -> None:
    tools = [
        _tool("manage_crop_templates"),
        _tool("manage_crop_cycle"),
    ]

    decision = SkillRouter().route(message, tools)

    assert "manage_crop_templates" in decision.selected_tools


def test_crop_cycle_read_query_does_not_expose_template_tool() -> None:
    tools = [
        _tool("manage_crop_templates"),
        _tool("manage_crop_cycle"),
    ]

    decision = SkillRouter().route("我的茬口", tools)

    assert decision.selected_tools == ["manage_crop_cycle"]


def test_create_crop_template_with_read_entity_still_routes_to_write_tool() -> None:
    tools = [_tool("manage_crop_templates")]

    decision = SkillRouter().route("帮我创建黑布林作物模板", tools)

    assert decision.selected_tools == ["manage_crop_templates"]
    assert all(frame.intent != "query_crop_templates" for frame in decision.frames)
