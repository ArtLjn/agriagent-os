"""Router policy 测试。"""

import pytest

from app.agent.router.models import DisclosureBudget, IntentFrame, ToolCandidate
from app.agent.router.policy import RouterPolicy

pytestmark = pytest.mark.no_db


def _candidate(name: str, risk: str, tokens: int = 200) -> ToolCandidate:
    return ToolCandidate(
        name=name,
        domain="test",
        intents=[name],
        risk=risk,
        schema_token_estimate=tokens,
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
