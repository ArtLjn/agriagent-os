"""Router 模型测试。"""

import pytest

from app.agent.router.models import (
    DisclosureBudget,
    IntentFrame,
    RouterDecision,
    ToolCandidate,
)

pytestmark = pytest.mark.no_db


def test_router_decision_serializes_for_trace() -> None:
    decision = RouterDecision(
        frames=[
            IntentFrame(
                domain="planting",
                intent="query_active_crops",
                risk="read",
                entities=["crop_cycle"],
                candidate_tools=["get_farm_status"],
                confidence=0.86,
            )
        ],
        selected_tools=["get_farm_status"],
        context_dependencies=["crop_cycles"],
        fallback="safe_read_default",
        reason="匹配活跃作物查询",
        rejected_tools=["create_crop_cycle"],
        schema_token_estimate=620,
        policy_violations=[],
    )

    payload = decision.to_trace_payload()

    assert payload["selected_tools"] == ["get_farm_status"]
    assert payload["frames"][0]["intent"] == "query_active_crops"
    assert payload["fallback"] == "safe_read_default"
    assert payload["schema_token_estimate"] == 620


def test_tool_candidate_keeps_routing_metadata() -> None:
    candidate = ToolCandidate(
        name="create_operation_work_order",
        domain="operation",
        intents=["create_work_order"],
        risk="write_confirm",
        entities=["worker", "planting_unit"],
        trigger_examples=["今天李树去6号棚收水稻"],
        anti_examples=["我的作业单有哪些"],
        context_dependencies=["workers", "planting_units", "active_cycles"],
        candidate_group="operation_write",
        schema_token_estimate=480,
    )

    assert candidate.name == "create_operation_work_order"
    assert candidate.risk == "write_confirm"
    assert candidate.context_dependencies == [
        "workers",
        "planting_units",
        "active_cycles",
    ]


def test_disclosure_budget_defaults_match_spec() -> None:
    budget = DisclosureBudget()

    assert budget.max_tools_default == 3
    assert budget.max_tools_complex == 5
    assert budget.max_write_tools == 1
    assert budget.max_schema_tokens == 1800
