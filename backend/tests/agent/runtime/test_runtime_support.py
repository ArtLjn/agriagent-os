"""Agent runtime support module tests."""

import pytest

from app.agent.runtime.support import (
    AgentRuntimeError,
    QUOTA_REJECT_MESSAGES,
)

pytestmark = pytest.mark.no_db


def test_runtime_support_exports_runtime_error_and_quota_messages() -> None:
    assert issubclass(AgentRuntimeError, RuntimeError)
    assert QUOTA_REJECT_MESSAGES["identity"] == "缺少可信用户上下文，无法继续处理。"


def test_runtime_support_does_not_export_graph_compiler() -> None:
    import app.agent.runtime.support as support

    assert not hasattr(support, "compile_advisor_graph")
