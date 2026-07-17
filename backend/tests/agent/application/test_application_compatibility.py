"""Application 旧路径兼容测试。"""

from importlib import import_module
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize(
    "module_name",
    [
        "chat_use_case",
        "stream_chat_use_case",
        "advisor",
        "report",
        "smart_fill",
    ],
)
def test_old_agent_application_import_path_maps_to_new_module_object(
    module_name: str,
) -> None:
    new_module = import_module(f"app.application.{module_name}")
    old_module = import_module(f"app.agent.application.{module_name}")

    assert old_module is new_module


def test_old_agent_application_chat_use_case_import_path_exports_runtime_api() -> None:
    module = import_module("app.agent.application.chat_use_case")

    assert callable(module.chat)
    assert callable(module.new_request_id)
    assert callable(module.stream_chat_events)


def test_old_agent_application_stream_chat_use_case_import_path_exports_runtime_api() -> None:
    module = import_module("app.agent.application.stream_chat_use_case")

    assert callable(module.stream_chat_events)


@pytest.mark.parametrize(
    "target",
    [
        "app.agent.application.chat_use_case.invoke_advisor",
        "app.agent.application.chat_use_case.handle_pending_action",
        "app.agent.application.stream_chat_use_case.stream_advisor",
        "app.agent.application.stream_chat_use_case._flush_trace_queue",
        "app.agent.application.advisor.invoke_advisor",
        "app.agent.application.report.generate_cycle_report",
        "app.agent.application.smart_fill.parse_with_llm",
    ],
)
def test_old_agent_application_monkeypatch_targets_still_resolve(target: str) -> None:
    with patch(target) as patched:
        assert patched is not None
