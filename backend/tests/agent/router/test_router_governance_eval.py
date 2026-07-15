"""Router governance eval：能力准确率、风险隔离和预算回归。"""

from unittest.mock import MagicMock

import pytest

from app.agent.router.catalog import SkillCatalog
from app.agent.router.models import DisclosureBudget
from app.agent.router.service import SkillRouter

pytestmark = pytest.mark.no_db


def _tool(name: str):
    tool = MagicMock()
    tool.name = name
    tool.description = ""
    return tool


def _tools(names: list[str]):
    return [_tool(name) for name in names]


@pytest.mark.parametrize(
    ("message", "expected_tool", "capability", "operation"),
    [
        ("今天买了100元化肥", "create_cost_record", "manage_cost", "create_record"),
        ("我的茬口有哪些", "manage_crop_cycle", "manage_crop_cycle", "query_cycles"),
        ("我的工人有哪些", "manage_workers", "manage_workers", "query_workers"),
        (
            "我的作业单有哪些",
            "get_operation_work_orders",
            "manage_work_orders",
            "query_work_orders",
        ),
        (
            "还欠多少人工钱",
            "manage_labor_payment",
            "manage_labor_payment",
            "query_payables",
        ),
        (
            "我的默认天气城市是什么",
            "manage_user_settings",
            "manage_settings",
            "query_settings",
        ),
        (
            "默认天气城市设置是什么",
            "manage_user_settings",
            "manage_settings",
            "query_settings",
        ),
        (
            "当前助手回复角色是什么",
            "manage_user_settings",
            "manage_settings",
            "query_settings",
        ),
        (
            "当前默认经纬度是多少",
            "manage_user_settings",
            "manage_settings",
            "query_settings",
        ),
        (
            "把默认天气城市改成苏州",
            "manage_user_settings",
            "manage_settings",
            "update_settings",
        ),
        (
            "设置默认天气城市为苏州",
            "manage_user_settings",
            "manage_settings",
            "update_settings",
        ),
        (
            "设置默认经纬度为31.2,120.6",
            "manage_user_settings",
            "manage_settings",
            "update_settings",
        ),
        (
            "把默认经纬度改成31.2,120.6",
            "manage_user_settings",
            "manage_settings",
            "update_settings",
        ),
        (
            "有哪些地块",
            "manage_planting_units",
            "manage_planting_units",
            "query_units",
        ),
        (
            "查询种植单元",
            "manage_planting_units",
            "manage_planting_units",
            "query_units",
        ),
        (
            "新增地块一号棚",
            "manage_planting_units",
            "manage_planting_units",
            "manage_units",
        ),
        (
            "把一号棚面积改成20亩",
            "manage_planting_units",
            "manage_planting_units",
            "manage_units",
        ),
        (
            "有哪些成本分类",
            "manage_cost_categories",
            "manage_cost_categories",
            "query_categories",
        ),
        (
            "查询分类",
            "manage_cost_categories",
            "manage_cost_categories",
            "query_categories",
        ),
        (
            "新增成本分类农药",
            "manage_cost_categories",
            "manage_cost_categories",
            "manage_category",
        ),
        (
            "删除成本分类农药",
            "manage_cost_categories",
            "manage_cost_categories",
            "manage_category",
        ),
    ],
)
def test_router_top1_capability_accuracy(
    message: str,
    expected_tool: str,
    capability: str,
    operation: str,
) -> None:
    decision = SkillRouter().route(message, _tools(_governance_tool_pool()))

    assert decision.selected_tools[:1] == [expected_tool]
    assert decision.selected_operations == {capability: [operation]}
    assert decision.scores["capability"][capability] >= 0.85
    assert decision.scores["operation"][operation] >= 0.85
    assert decision.fallback != "fallback_all"


def test_router_top3_recall_for_uncategorized_business_read_stays_read_only() -> None:
    budget = DisclosureBudget()
    tools = _tools(_governance_tool_pool())

    decision = SkillRouter().route("我要看一下经营数据", tools)
    selected_candidates = _selected_candidates(decision.selected_tools, tools)

    assert 0 < len(decision.selected_tools) <= budget.max_tools_default
    assert decision.fallback == "model_choice_read_default"
    assert decision.fallback != "fallback_all"
    assert all(candidate.risk == "read" for candidate in selected_candidates)
    assert "create_cost_record" not in decision.selected_tools


def test_router_top3_recall_for_farm_overview_includes_core_read_context() -> None:
    tools = _tools(
        [
            "weather",
            "get_farm_status",
            "manage_crop_cycle",
        ]
    )

    decision = SkillRouter().route("农场整体状态怎么样", tools)

    assert decision.selected_tools == [
        "weather",
        "get_farm_status",
        "manage_crop_cycle",
    ]
    assert decision.fallback != "fallback_all"


@pytest.mark.parametrize(
    ("message", "read_tool", "write_tools"),
    [
        (
            "我的作业单有哪些",
            "get_operation_work_orders",
            ["create_operation_work_order"],
        ),
        (
            "我的茬口有哪些",
            "manage_crop_cycle",
            [],
        ),
        (
            "工人列表",
            "manage_workers",
            [],
        ),
        (
            "地块列表",
            "manage_planting_units",
            [],
        ),
        (
            "成本分类列表",
            "manage_cost_categories",
            [],
        ),
    ],
)
def test_read_intent_does_not_expose_write_operations(
    message: str,
    read_tool: str,
    write_tools: list[str],
) -> None:
    decision = SkillRouter().route(message, _tools([read_tool, *write_tools]))

    assert decision.selected_tools == [read_tool]
    for write_tool in write_tools:
        assert write_tool not in decision.selected_tools
    assert decision.fallback != "fallback_all"


def test_high_risk_delete_crop_cycle_requires_clarification() -> None:
    decision = SkillRouter().route("删除这个茬口", _tools(["manage_crop_cycle"]))

    assert decision.selected_tools == []
    assert decision.fallback == "clarify_high_risk_operation"
    assert decision.fallback_reason == "high_risk_operation"
    assert decision.rejected_candidates[0]["name"] == "manage_crop_cycle"
    assert decision.rejected_candidates[0]["reason"] == "high_risk_clarify"
    assert decision.rejected_candidates[0]["risk"] == "write_high"


def test_write_tool_budget_selects_at_most_one_write_tool() -> None:
    decision = SkillRouter().route(
        "新来一个工人李丽工资100一天，今天去6号棚收水稻",
        _tools(["manage_workers", "create_operation_work_order"]),
    )

    assert len(decision.selected_tools) <= DisclosureBudget().max_write_tools
    assert decision.selected_tools == ["manage_workers"]
    assert decision.fallback != "fallback_all"


@pytest.mark.parametrize(
    "message",
    [
        "新增工人张三",
        "添加一个工人李四",
        "把张三的电话改成13800000000",
        "删除工人张三",
    ],
)
def test_worker_management_write_intent_uses_manage_workers_operation(
    message: str,
) -> None:
    decision = SkillRouter().route(message, _tools(_governance_tool_pool()))

    assert decision.selected_tools[:1] == ["manage_workers"]
    assert decision.selected_operations == {"manage_workers": ["manage_worker"]}
    assert decision.frames[0].risk == "write_confirm"
    assert decision.frames[0].requires_confirmation is True


def _selected_candidates(selected_tools: list[str], tools: list) -> list:
    catalog = SkillCatalog.from_tools(tools)
    return [
        candidate
        for name in selected_tools
        if (candidate := catalog.get(name)) is not None
    ]


def _governance_tool_pool() -> list[str]:
    return [
        "get_cost_summary",
        "get_debt_summary",
        "get_cost_analytics",
        "create_cost_record",
        "manage_crop_cycle",
        "manage_workers",
        "get_operation_work_orders",
        "create_operation_work_order",
        "manage_labor_payment",
        "get_farm_status",
        "weather",
        "manage_user_settings",
        "manage_planting_units",
        "manage_cost_categories",
    ]
