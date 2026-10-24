"""外部记忆语义模型的测试替身，默认测试不发送真实模型请求。"""

import hashlib
from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def memory_assessment_stub(monkeypatch):
    from agent.domains.harness.memory import tools

    assess = AsyncMock(return_value=tools.MemoryAssessment(authorized=True))
    monkeypatch.setattr(tools, "assess", assess)
    monkeypatch.setattr(tools, "content_is_grounded", AsyncMock(return_value=True))
    return assess


@pytest.fixture
def memory_writer_stub(monkeypatch, request):
    """工具边界测试隔离学习模型；真实回放及学习域测试仍执行真实统一写入器。"""
    if request.node.name.startswith("test_live"):
        return
    from agent.domains.harness.memory import learning
    from agent.domains.harness.memory.personalization import MemoryCreate, MemoryPatch
    from agent.platforms.persistence.mongo import personalization_store as store

    async def write(turn, text, scope, *, target=None):
        if target:
            return await store.modify_memory(
                turn.user_id,
                turn.farm_uid,
                target["memory_id"],
                MemoryPatch(expected_revision=target["revision"], text=text),
            )
        identifier = hashlib.sha256(turn.turn_id.encode()).hexdigest()
        return await store.create_memory(
            turn.user_id,
            turn.farm_uid,
            MemoryCreate(
                memory_id=identifier,
                key="explicit." + identifier,
                text=text,
                scope=scope,
            ),
        )

    monkeypatch.setattr(learning, "remember_explicit", write)
