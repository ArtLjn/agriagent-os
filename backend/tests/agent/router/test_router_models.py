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
                capability="manage_crop_cycle",
                operation="query_cycles",
                operation_hint="query_cycles",
                entities=["crop_cycle"],
                candidate_tools=["get_farm_status"],
                confidence=0.86,
                score=0.92,
                evidence={"domain_scores": {"crop": 0.9}},
                planning_evidence={"query_entity": "crop_cycle"},
                missing_fields=["farm_id"],
            )
        ],
        selected_tools=["get_farm_status"],
        selected_operations={"get_farm_status": ["query_status"]},
        context_dependencies=["crop_cycles"],
        fallback="safe_read_default",
        fallback_reason="test_reason",
        reason="匹配活跃作物查询",
        rejected_tools=["create_crop_cycle"],
        rejected_candidates=[
            {
                "name": "create_crop_cycle",
                "reason": "read_intent_write_operation",
            }
        ],
        schema_token_estimate=620,
        policy_violations=[],
        scores={"domain": {"crop": 0.9}},
        evidence={"selected_candidates": [{"name": "get_farm_status"}]},
    )

    payload = decision.to_trace_payload()

    assert payload["selected_tools"] == ["get_farm_status"]
    assert payload["frames"][0]["intent"] == "query_active_crops"
    assert payload["frames"][0]["capability"] == "manage_crop_cycle"
    assert payload["frames"][0]["operation_hint"] == "query_cycles"
    assert payload["frames"][0]["score"] == 0.92
    assert payload["frames"][0]["evidence"]["domain_scores"] == {"crop": 0.9}
    assert payload["frames"][0]["planning_evidence"] == {"query_entity": "crop_cycle"}
    assert payload["frames"][0]["missing_fields"] == ["farm_id"]
    assert payload["fallback"] == "safe_read_default"
    assert payload["fallback_reason"] == "test_reason"
    assert payload["selected_operations"] == {"get_farm_status": ["query_status"]}
    assert payload["rejected_candidates"][0]["reason"] == (
        "read_intent_write_operation"
    )
    assert payload["scores"] == {"domain": {"crop": 0.9}}
    assert payload["schema_token_estimate"] == 620


def test_tool_candidate_keeps_routing_metadata() -> None:
    candidate = ToolCandidate(
        name="create_operation_work_order",
        domain="operation",
        intents=["create_work_order"],
        risk="write_confirm",
        capability="manage_work_orders",
        operation="create_work_order",
        legacy_alias="create_operation_work_order",
        operation_risk="write_confirm",
        entities=["worker", "planting_unit"],
        trigger_examples=["今天李树去6号棚收水稻"],
        anti_examples=["我的作业单有哪些"],
        context_dependencies=["workers", "planting_units", "active_cycles"],
        candidate_group="operation_write",
        schema_token_estimate=480,
        score=1.0,
        evidence={"source": "skill_registry"},
    )

    assert candidate.name == "create_operation_work_order"
    assert candidate.risk == "write_confirm"
    assert candidate.capability == "manage_work_orders"
    assert candidate.operation == "create_work_order"
    assert candidate.legacy_alias == "create_operation_work_order"
    assert candidate.operation_risk == "write_confirm"
    assert candidate.score == 1.0
    assert candidate.evidence["source"] == "skill_registry"
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
