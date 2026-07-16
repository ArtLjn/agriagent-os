"""Application 旧路径兼容测试。"""

from importlib import import_module
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.no_db


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
    ],
)
def test_old_agent_application_monkeypatch_targets_still_resolve(target: str) -> None:
    with patch(target) as patched:
        assert patched is not None
