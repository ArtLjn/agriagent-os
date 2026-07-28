"""Skill Router 生命周期日志测试。"""

import logging
from unittest.mock import MagicMock

import pytest

from app.agent.router.service import SkillRouter

pytestmark = pytest.mark.no_db


def _tool(name: str, description: str = ""):
    tool = MagicMock()
    tool.name = name
    tool.description = description
    return tool


def test_skill_router_logs_route_lifecycle(caplog) -> None:
    tools = [_tool("get_farm_status"), _tool("manage_cost")]

    with caplog.at_level(logging.INFO, logger="app.agent.router.service"):
        decision = SkillRouter().route("我有哪些欠款", tools)

    messages = [record.getMessage() for record in caplog.records]
    assert decision.selected_tools == ["manage_cost"]
    assert any("event=skill_router_started" in message for message in messages)
    assert any(
        "event=skill_router_completed" in message
        and "status=success" in message
        and "selected_tools=manage_cost" in message
        and "selected_operations=" in message
        for message in messages
    )
    completed = next(
        message for message in messages if "event=skill_router_completed" in message
    )
    assert "candidate_explanations=" not in completed
    assert "recall=" not in completed
    trace_message = next(
        message
        for message in messages
        if "event=skill_router_trace\nSkill Router Trace" in message
    )
    assert "event=skill_router_trace\nSkill Router Trace" in trace_message
    assert "recall: skipped" in trace_message
    assert "external_rag_call: no" in trace_message
    assert "embedding_call: no" in trace_message
    assert "bm25=no vector=no" not in trace_message
    assert "candidate_scores:" in trace_message
    assert "manage_cost.query_debt" in trace_message
