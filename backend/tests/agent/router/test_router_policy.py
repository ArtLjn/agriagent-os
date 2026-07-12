"""Router policy 测试。"""

import pytest

from app.agent.router.models import DisclosureBudget, IntentFrame, ToolCandidate
from app.agent.router.policy import RouterPolicy

pytestmark = pytest.mark.no_db


def _candidate(
    name: str,
    risk: str,
    tokens: int = 200,
    *,
    enabled: bool = True,
    capability: str | None = None,
    operation: str | None = None,
) -> ToolCandidate:
    return ToolCandidate(
        name=name,
        domain="test",
        intents=[name],
        risk=risk,
        schema_token_estimate=tokens,
        enabled=enabled,
        capability=capability,
        operation=operation,
        legacy_alias=name,
    )


def test_policy_allows_only_one_write_tool() -> None:
    decision = RouterPolicy().apply(
        message="新增工人并创建作业单",
        frames=[
            IntentFrame(
                domain="operation",
                intent="multi_write",
                risk="write_confirm",
                candidate_tools=["manage_workers", "create_operation_work_order"],
            )
        ],
        candidates=[
            _candidate("manage_workers", "write_confirm"),
            _candidate("create_operation_work_order", "write_confirm"),
        ],
    )

    assert len(decision.selected_tools) == 1
    assert decision.policy_violations == ["write_tool_budget_exceeded"]
    assert decision.rejected_candidates[0]["reason"] == "write_tool_budget_exceeded"


def test_policy_trims_schema_token_budget() -> None:
    decision = RouterPolicy(
        DisclosureBudget(max_tools_default=3, max_schema_tokens=500)
    ).apply(
        message="看看天气成本和作业单",
        frames=[
            IntentFrame(
                domain="farm",
                intent="complex_read",
                risk="read",
                candidate_tools=["a", "b", "c"],
            )
        ],
        candidates=[
            _candidate("a", "read", tokens=300),
            _candidate("b", "read", tokens=300),
            _candidate("c", "read", tokens=300),
        ],
    )

    assert decision.selected_tools == ["a"]
    assert decision.schema_token_estimate == 300
    assert "schema_token_budget_exceeded" in decision.policy_violations
    assert decision.rejected_candidates[0]["reason"] == "schema_token_budget_exceeded"


def test_policy_counts_write_tool_only_after_selection() -> None:
    decision = RouterPolicy(
        DisclosureBudget(max_tools_default=3, max_schema_tokens=500)
    ).apply(
        message="新增工人并创建作业单",
        frames=[
            IntentFrame(
                domain="operation",
                intent="multi_write",
                risk="write_confirm",
                candidate_tools=["large_write", "small_write"],
            )
        ],
        candidates=[
            _candidate("large_write", "write_confirm", tokens=600),
            _candidate("small_write", "write_confirm", tokens=200),
        ],
    )

    assert decision.selected_tools == ["small_write"]
    assert decision.rejected_tools == ["large_write"]
    assert decision.policy_violations == ["schema_token_budget_exceeded"]


def test_policy_skips_disabled_candidates() -> None:
    decision = RouterPolicy().apply(
        message="查询禁用工具",
        frames=[
            IntentFrame(
                domain="test",
                intent="query_disabled",
                risk="read",
                candidate_tools=["disabled_read"],
            )
        ],
        candidates=[
            ToolCandidate(
                name="disabled_read",
                domain="test",
                intents=["query_disabled"],
                risk="read",
                schema_token_estimate=100,
                enabled=False,
            )
        ],
    )

    assert decision.selected_tools == []
    assert decision.rejected_tools == ["disabled_read"]
    assert decision.rejected_candidates == [
        {
            "name": "disabled_read",
            "reason": "disabled",
            "domain": "test",
            "capability": None,
            "operation": None,
            "risk": "read",
            "enabled": False,
            "legacy_alias": None,
        }
    ]
    assert "disabled_candidate_rejected" in decision.policy_violations


def test_policy_rejects_write_operation_for_read_frame() -> None:
    decision = RouterPolicy().apply(
        message="看看作业单",
        frames=[
            IntentFrame(
                domain="operation",
                intent="query_work_orders",
                risk="read",
                candidate_tools=["create_operation_work_order"],
            )
        ],
        candidates=[
            _candidate("create_operation_work_order", "write_confirm"),
        ],
    )

    assert decision.selected_tools == []
    assert decision.rejected_tools == ["create_operation_work_order"]
    assert decision.rejected_candidates[0]["reason"] == "read_intent_write_operation"
    assert "read_write_risk_mismatch" in decision.policy_violations


def test_policy_requires_clarification_for_high_risk_operation() -> None:
    decision = RouterPolicy().apply(
        message="删除这个茬口",
        frames=[
            IntentFrame(
                domain="crop",
                intent="delete_cycle",
                risk="write_high",
                candidate_tools=["delete_crop_cycle"],
            )
        ],
        candidates=[
            _candidate(
                "delete_crop_cycle",
                "write_high",
                capability="manage_crop_cycle",
                operation="delete_cycle",
            ),
        ],
    )

    assert decision.selected_tools == []
    assert decision.fallback == "clarify_high_risk_operation"
    assert decision.fallback_reason == "high_risk_operation"
    assert decision.clarification is not None
    assert decision.rejected_candidates[0]["reason"] == "high_risk_clarify"


def test_policy_records_selected_operations_for_legacy_tools() -> None:
    decision = RouterPolicy().apply(
        message="查询未付人工",
        frames=[
            IntentFrame(
                domain="labor",
                intent="query_labor_payables",
                risk="read",
                candidate_tools=["get_labor_payables"],
            )
        ],
        candidates=[
            _candidate(
                "get_labor_payables",
                "read",
                capability="manage_labor_payment",
                operation="query_payables",
            ),
        ],
    )

    assert decision.selected_tools == ["get_labor_payables"]
    assert decision.selected_operations == {"manage_labor_payment": ["query_payables"]}


def test_policy_shortlists_model_choice_read_pool_without_fallback_all() -> None:
    candidates = [_candidate(f"read_{index}", "read") for index in range(4)]

    decision = RouterPolicy(DisclosureBudget(max_tools_default=2)).apply(
        message="看一下经营数据",
        frames=[],
        candidates=candidates + [_candidate("write_one", "write_confirm")],
    )

    assert decision.selected_tools == ["read_0", "read_1"]
    assert decision.fallback == "model_choice_read_default"
    assert decision.fallback != "fallback_all"
    assert "write_one" not in decision.selected_tools
