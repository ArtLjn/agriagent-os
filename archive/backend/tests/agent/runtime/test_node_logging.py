"""Agent runtime 节点日志测试。"""

import logging

import pytest

from app.agent.runtime.nodes import _bind_llm_for_tools

pytestmark = pytest.mark.no_db


def test_no_tool_binding_after_tool_results_logs_finalization_stage(caplog) -> None:
    raw_llm = object()

    with caplog.at_level(logging.INFO, logger="app.agent.runtime.nodes"):
        result = _bind_llm_for_tools(
            raw_llm,
            [],
            has_tool_results=True,
        )

    assert result is raw_llm
    messages = [record.getMessage() for record in caplog.records]
    assert any("进入最终回复生成阶段" in message for message in messages)
    assert all("闲聊模式" not in message for message in messages)
