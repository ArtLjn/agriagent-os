"""Router policy 选择状态辅助逻辑测试。"""

import pytest

from app.agent.router.models import DisclosureBudget, IntentFrame, ToolCandidate
from app.agent.router.policy_selection import (
    SelectionState,
    candidate_frame_map,
    collect_candidate_names,
    dedupe_context_dependencies,
    reject_candidate,
    schema_budget_exceeded,
    select_candidate,
    trim_candidates_by_budget,
    with_violation,
    write_budget_exceeded,
)

pytestmark = pytest.mark.no_db


def _candidate(
    name: str,
    risk: str,
    tokens: int = 200,
    *,
    dependencies: list[str] | None = None,
) -> ToolCandidate:
    return ToolCandidate(
        name=name,
        domain="test",
        intents=[name],
        risk=risk,
        schema_token_estimate=tokens,
        context_dependencies=dependencies or [],
    )


def test_selection_state_tracks_budget_inputs_after_select_and_reject() -> None:
    budget = DisclosureBudget(max_write_tools=1, max_schema_tokens=500)
    state = SelectionState()
    selected = _candidate("create_order", "write_confirm", tokens=300)
    oversized = _candidate("create_payment", "write_confirm", tokens=250)

    select_candidate(state, selected)
    reject_candidate(
        state,
        oversized.name,
        "schema_token_budget_exceeded",
        oversized,
        violation="schema_token_budget_exceeded",
    )

    assert state.selected == [selected]
    assert state.write_count == 1
    assert state.schema_token_estimate == 300
    assert state.rejected_tools == ["create_payment"]
    assert state.rejected_candidates[0]["reason"] == "schema_token_budget_exceeded"
    assert state.policy_violations == ["schema_token_budget_exceeded"]
    assert write_budget_exceeded(oversized, state, budget)
    assert schema_budget_exceeded(oversized, state, budget)


def test_selection_helpers_keep_first_seen_order_for_candidates_and_context() -> None:
    frames = [
        IntentFrame(
            domain="farm",
            intent="query_status",
            risk="read",
            candidate_tools=["farm_status", "weather"],
            depends_on=["active_cycles"],
        ),
        IntentFrame(
            domain="farm",
            intent="query_weather",
            risk="read",
            candidate_tools=["weather", "farm_status"],
            depends_on=["weather"],
        ),
    ]
    selected = [
        _candidate("farm_status", "read", dependencies=["active_cycles", "plots"]),
        _candidate("weather", "read", dependencies=["weather", "plots"]),
    ]

    assert collect_candidate_names(frames) == ["farm_status", "weather"]
    assert candidate_frame_map(frames)["weather"].intent == "query_status"
    assert dedupe_context_dependencies(selected, frames) == [
        "active_cycles",
        "plots",
        "weather",
    ]


def test_trim_candidates_by_budget_stops_before_tool_or_schema_budget() -> None:
    budget = DisclosureBudget(max_schema_tokens=500)
    candidates = [
        _candidate("a", "read", tokens=200),
        _candidate("b", "read", tokens=250),
        _candidate("c", "read", tokens=100),
    ]

    assert trim_candidates_by_budget(candidates, budget, max_tools=2) == candidates[:2]
    assert trim_candidates_by_budget(candidates, budget, max_tools=3) == candidates[:2]


def test_with_violation_dedupes_without_mutating_original() -> None:
    original = ["schema_token_budget_exceeded"]

    updated = with_violation(original, "schema_token_budget_exceeded")

    assert updated == ["schema_token_budget_exceeded"]
    assert updated is not original
