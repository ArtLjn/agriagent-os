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
    _Tool("manage_crop_cycle"),
    _Tool("manage_workers"),
    _Tool("create_operation_work_order"),
    _Tool("get_operation_work_orders"),
    _Tool("get_workers"),
    _Tool("get_cost_summary"),
    _Tool("get_debt_summary"),
    _Tool("get_labor_payables"),
    _Tool("manage_crop_templates"),
    _Tool("get_planting_units"),
    _Tool("manage_cost_categories"),
    _Tool("manage_user_settings"),
    _Tool("settle_labor_payment"),
]


def test_session5_crop_query_is_bounded() -> None:
    decision = SkillRouter().route("我家有哪些作物栽种", TOOLS)

    assert len(decision.selected_tools) <= 2
    assert set(decision.selected_tools) <= {"get_farm_status", "manage_crop_cycle"}
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


def test_implicit_farm_labor_case_reports_semantic_planning_evidence() -> None:
    decision = SkillRouter().route("李海这个月干了15天压瓜", TOOLS)

    work_order_frame = next(
        frame for frame in decision.frames if frame.intent == "create_work_order"
    )
    assert decision.selected_tools == ["create_operation_work_order"]
    assert work_order_frame.planning_evidence["worker"] == "李海"
    assert work_order_frame.planning_evidence["operation_type"] == "压瓜"
    assert work_order_frame.planning_evidence["quantity"] == 15
    assert work_order_frame.missing_fields == ["unit_price_or_default_wage"]


def test_missing_operation_case_reports_semantic_planning_clarification() -> None:
    decision = SkillRouter().route("李海这个月干了15天", TOOLS)

    assert decision.selected_tools == []
    assert decision.fallback == "clarify_farm_labor_work"
    assert decision.clarification is not None
    assert decision.frames[0].missing_fields == ["operation_type"]


def test_multi_step_case_reports_pending_creation_inputs() -> None:
    router = SkillRouter()
    decision = router.route("新来一个工人李丽工资100一天，今天去6号棚收水稻", TOOLS)

    assert [step["tool_name"] for step in router.build_pending_plan_steps(decision)] == [
        "manage_workers",
        "create_operation_work_order",
    ]


def test_read_intent_does_not_expose_write_tools() -> None:
    decision = SkillRouter().route("我的工人有哪些", TOOLS)

    assert all(
        name not in decision.selected_tools
        for name in [
            "manage_workers",
            "create_operation_work_order",
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


def test_high_risk_delete_crop_cycle_requires_clarification() -> None:
    decision = SkillRouter().route("删除这个茬口", TOOLS)

    assert decision.selected_tools == []
    assert decision.fallback == "clarify_high_risk_operation"
    assert decision.rejected_candidates[0]["name"] == "manage_crop_cycle"
    assert decision.rejected_candidates[0]["risk"] == "write_high"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("老王还欠多少人工钱", ["get_labor_payables"]),
        ("我的茬口", ["manage_crop_cycle"]),
        ("看一下3号茬口", ["manage_crop_cycle"]),
        ("有哪些作物模板", ["manage_crop_templates"]),
        ("有哪些大棚", ["get_planting_units"]),
        ("有哪些成本分类", ["manage_cost_categories"]),
        ("我的默认城市是什么", ["manage_user_settings"]),
    ],
)
def test_specific_read_queries_do_not_fall_back_to_farm_status(
    message: str,
    expected: list[str],
) -> None:
    decision = SkillRouter().route(message, TOOLS)

    assert decision.selected_tools == expected
    assert "get_farm_status" not in decision.selected_tools
