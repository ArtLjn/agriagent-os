"""Memory service 具体实现契约测试。"""

import pytest

from app.memory.service import InMemoryMemoryService, get_memory_service

pytestmark = pytest.mark.no_db


def test_memory_service_exposes_runtime_methods() -> None:
    service = InMemoryMemoryService()

    assert hasattr(service, "build_context")
    assert hasattr(service, "observe_interaction")
    assert hasattr(service, "search")
    assert hasattr(service, "observe_chat_completion")


def test_default_memory_service_uses_concrete_service() -> None:
    assert isinstance(get_memory_service(), InMemoryMemoryService)
