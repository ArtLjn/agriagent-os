"""业务路由召回评测测试。"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.agent.router.service import SkillRouter
from app.ops.skill_route_eval import (
    active_eval_tools,
    default_route_cases_path,
    evaluate_route_recall,
    load_route_cases,
    preview_route_recall,
)

pytestmark = pytest.mark.no_db


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "business_route_cases.yaml"


def _tool(name: str):
    tool = MagicMock()
    tool.name = name
    tool.description = name
    return tool


def test_business_route_recall_hits_expected_candidates() -> None:
    cases = load_route_cases(FIXTURE_PATH)
    tools = [
        _tool("get_farm_status"),
        _tool("manage_crop_cycle"),
        _tool("manage_planting_units"),
        _tool("manage_cost"),
        _tool("manage_workers"),
        _tool("weather"),
    ]

    report = evaluate_route_recall(cases, tools, top_k=5)

    assert report.total == 9
    assert report.recall_at_1 >= 6 / 9
    assert report.recall_at_k == 1.0
    assert report.operation_recall_at_k == 1.0
    assert report.failures == []


def test_json_route_recall_dataset_hits_expected_candidates() -> None:
    cases = load_route_cases(default_route_cases_path())

    report = evaluate_route_recall(cases, active_eval_tools(), top_k=5)

    assert report.failures == []
    assert report.operation_recall_at_k == 1.0


def test_preview_route_recall_uses_route_level_hybrid_score() -> None:
    candidates = preview_route_recall("这个月花了多少钱", active_eval_tools(), top_k=5)

    assert candidates[0].skill == "manage_cost"
    assert candidates[0].operation == "query_summary"
    assert candidates[0].score > 0
    assert candidates[0].evidence["score"] == candidates[0].score
    assert "bm25" in candidates[0].evidence["sources"]


@pytest.mark.parametrize(
    "message",
    [
        "5号棚面积多少",
        "这个茬口下面每个棚多少亩",
    ],
)
def test_planting_unit_area_queries_route_to_query_units(message: str) -> None:
    tools = [
        _tool("get_farm_status"),
        _tool("manage_crop_cycle"),
        _tool("manage_planting_units"),
    ]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == ["manage_planting_units"]
    assert decision.selected_operations == {"manage_planting_units": ["query_units"]}


@pytest.mark.parametrize(
    "message",
    [
        "现在西瓜多少亩",
        "这个茬口多少亩",
    ],
)
def test_crop_cycle_area_queries_route_to_query_cycles(message: str) -> None:
    tools = [
        _tool("get_farm_status"),
        _tool("manage_crop_cycle"),
        _tool("manage_planting_units"),
    ]

    decision = SkillRouter().route(message, tools)

    assert decision.selected_tools == ["manage_crop_cycle"]
    assert decision.selected_operations == {"manage_crop_cycle": ["query_cycles"]}


def test_retrievable_debt_read_fallback_uses_operation_level_hybrid_recall() -> None:
    tools = [
        _tool("get_farm_status"),
        _tool("manage_cost"),
        _tool("manage_crop_cycle"),
    ]

    decision = SkillRouter().route("还有没结清的钱吗", tools)

    assert decision.selected_tools == ["manage_cost"]
    assert decision.selected_operations == {"manage_cost": ["query_debt"]}
