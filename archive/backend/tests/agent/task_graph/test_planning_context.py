"""Task Graph 薄上下文构建测试。"""

import pytest

from app.agent.task_graph.planning_context_builder import build_planning_context
from app.agent.task_graph.raw_context_builder import build_raw_context
from app.agent.task_graph.slot_extractor import extract_planting_plan_slots

pytestmark = pytest.mark.no_db


def test_raw_context_keeps_only_request_refs_and_metadata() -> None:
    raw_context = build_raw_context(
        user_input="我在太仓新租了30亩地 每块地1.5亩 帮我规划下茬口，秋季草莓",
        request_id="req-1",
        session_id="sess-1",
        user_id="user-1",
        metadata={"channel": "test"},
    )

    assert raw_context.request_id == "req-1"
    assert raw_context.session_id == "sess-1"
    assert raw_context.user_id == "user-1"
    assert raw_context.memory_refs == []
    assert raw_context.db_refs == []
    assert raw_context.trace_metadata["channel"] == "test"
    assert raw_context.trace_metadata["user_input"] == (
        "我在太仓新租了30亩地 每块地1.5亩 帮我规划下茬口，秋季草莓"
    )


def test_planning_context_builds_summary_facts_and_failed_graph_ref() -> None:
    raw_context = build_raw_context(
        user_input="太仓30亩秋季草莓规划",
        request_id="req-1",
        last_failed_task_graph_id="graph-old",
    )
    slots = extract_planting_plan_slots("太仓30亩秋季草莓规划")

    planning_context = build_planning_context(
        user_input="太仓30亩秋季草莓规划",
        raw_context=raw_context,
        task_type="planting_plan",
        slots=slots,
    )

    assert planning_context.context_summary["task_type"] == "planting_plan"
    assert planning_context.facts["crop"].value == "草莓"
    assert planning_context.recent_task_refs == ["graph-old"]
    assert "no_direct_write" in planning_context.risk_policy
