"""Skill Router 回归测试。"""

import pytest

from app.agent.router.service import SkillRouter

pytestmark = pytest.mark.no_db


class _Tool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = name


TOOLS = [
    _Tool("get_farm_status"),
    _Tool("get_crop_cycle_info"),
    _Tool("create_crop_cycle"),
    _Tool("manage_workers"),
    _Tool("create_operation_work_order"),
    _Tool("get_operation_work_orders"),
    _Tool("get_workers"),
    _Tool("get_cost_summary"),
    _Tool("get_debt_summary"),
    _Tool("settle_labor_payment"),
    _Tool("delete_crop_cycle"),
]


def test_session5_crop_query_is_bounded() -> None:
    decision = SkillRouter().route("我家有哪些作物栽种", TOOLS)

    assert len(decision.selected_tools) <= 2
    assert set(decision.selected_tools) <= {"get_farm_status", "get_crop_cycle_info"}
    assert decision.schema_token_estimate <= 1800


def test_session4_worker_and_harvest_has_step_recall() -> None:
    decision = SkillRouter().route(
        "我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了",
        TOOLS,
    )

    intents = [frame.intent for frame in decision.frames]
    assert "create_worker" in intents
    assert "create_work_order" in intents
    assert len(decision.selected_tools) == 1


def test_read_intent_does_not_expose_write_tools() -> None:
    decision = SkillRouter().route("我的工人有哪些", TOOLS)

    assert all(
        name not in decision.selected_tools
        for name in [
            "manage_workers",
            "create_operation_work_order",
            "delete_crop_cycle",
        ]
    )


def test_balance_query_selects_cost_summary_tool() -> None:
    decision = SkillRouter().route("我的余额", TOOLS)

    assert decision.selected_tools == ["get_cost_summary"]
    assert decision.frames[0].intent == "query_cost_summary"


def test_worker_query_selects_worker_read_tool() -> None:
    decision = SkillRouter().route("我的工人", TOOLS)

    assert decision.selected_tools == ["get_workers"]
    assert decision.frames[0].intent == "query_workers"


def test_high_risk_delete_not_exposed_for_unknown_text() -> None:
    decision = SkillRouter().route("随便聊聊", TOOLS)

    assert "delete_crop_cycle" not in decision.selected_tools
