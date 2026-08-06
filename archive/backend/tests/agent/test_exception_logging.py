"""Agent 静默异常日志与 lint 回归测试。"""

import importlib.util
import logging
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from app.agent.runtime import final_response, node_helpers
from app.context.core.models import ContextBundle

pytestmark = pytest.mark.no_db


class _FailingCollector:
    def record(self, **_kwargs):
        raise RuntimeError("trace 写入失败")


class _PromptBudget:
    total_tokens = 1
    compression_events: list = []

    def summary(self) -> dict:
        return {"total_tokens": 1}


def _load_lint_module():
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "lint_no_silent_exception.py"
    )
    spec = importlib.util.spec_from_file_location(
        "lint_no_silent_exception", script_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _assert_silent_exception_record(record, *, event: str, level: int) -> None:
    assert record.levelno == level
    assert record.agent_event == event
    assert record.error_type == "RuntimeError"
    assert record.error_message == "trace 写入失败"
    assert record.agent_context["module"]
    assert record.agent_context["function"]
    assert record.agent_context["agent_event"] == event
    assert record.exc_info


def test_trace_helper_failure_logs_debug(caplog) -> None:
    with caplog.at_level(logging.DEBUG, logger="app.agent.runtime.node_helpers"):
        node_helpers._record_tool_call_forced_trace(
            collector=_FailingCollector(),
            user_msg="你好",
            selected_names=["query_farm"],
            tool_choice="auto",
        )

    _assert_silent_exception_record(
        caplog.records[-1],
        event="node_helpers.record_tool_call_forced_trace",
        level=logging.DEBUG,
    )


def test_final_context_trace_failure_logs_warning(caplog) -> None:
    request = final_response.FinalResponseRequest(
        system_prompt="系统提示",
        user_query="问题",
        tool_results=[],
    )

    with caplog.at_level(logging.WARNING, logger="app.agent.runtime.final_response"):
        final_response._record_final_context_trace(_FailingCollector(), request)

    _assert_silent_exception_record(
        caplog.records[-1],
        event="final_response.record_final_context_trace",
        level=logging.WARNING,
    )


def test_final_llm_context_trace_failure_logs_warning(caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="app.agent.runtime.node_helpers"):
        node_helpers._record_final_llm_context_trace(
            collector=_FailingCollector(),
            system_text="系统提示",
            messages=[AIMessage(content="回复")],
            context_bundle=ContextBundle(blocks=[], token_budget=0, token_estimate=0),
            final_budget=_PromptBudget(),
        )

    _assert_silent_exception_record(
        caplog.records[-1],
        event="node_helpers.record_final_llm_context_trace",
        level=logging.WARNING,
    )


def test_lint_detects_generic_except_return_without_log(tmp_path) -> None:
    lint_module = _load_lint_module()
    source = tmp_path / "bad.py"
    source.write_text(
        """
def bad():
    try:
        raise RuntimeError("x")
    except Exception:
        return None
""",
        encoding="utf-8",
    )

    violations = lint_module.find_violations([source])

    assert len(violations) == 1
    assert violations[0].line == 5


def test_lint_allows_logged_generic_except(tmp_path) -> None:
    lint_module = _load_lint_module()
    source = tmp_path / "good.py"
    source.write_text(
        """
import logging
logger = logging.getLogger(__name__)

def good():
    try:
        raise RuntimeError("x")
    except Exception as exc:
        logger.warning("失败", exc_info=True)
        return None
""",
        encoding="utf-8",
    )

    assert lint_module.find_violations([source]) == []
