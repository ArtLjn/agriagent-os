"""Chat runtime helper consolidation tests."""

import pytest

from app.application import chat_use_case_helpers as helpers

pytestmark = pytest.mark.no_db


def test_chat_runtime_helpers_exports_context_and_trace_helpers() -> None:
    assert hasattr(helpers, "invalidate_user_farm_context")
    assert hasattr(helpers, "load_memory_context")
    assert hasattr(helpers, "record_agent_response")
