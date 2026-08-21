"""Conversation message 与 MemoryObservation 幂等提交测试。"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent.application import worker
from agent.domains.harness.runtime.turn import Turn
from agent.platforms.persistence.mongo import chat_store


class FakeInsertResult:
    def __init__(self, inserted_id: str) -> None:
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict] = []
        self.indexes: list[dict] = []

    async def create_index(self, keys, **options):
        self.indexes.append({"keys": tuple(keys), "options": options})

    async def find_one(self, filter_doc, projection=None):
        for document in self.documents:
            if all(document.get(key) == value for key, value in filter_doc.items()):
                if projection:
                    return {
                        key: value
                        for key, value in document.items()
                        if projection.get(key) == 1
                    }
                return deepcopy(document)
        return None

    async def insert_one(self, document):
        saved = deepcopy(document)
        saved["_id"] = f"message-{len(self.documents) + 1}"
        self.documents.append(saved)
        return FakeInsertResult(saved["_id"])


@pytest.mark.asyncio
async def test_message_append_is_idempotent(fake_collection, monkeypatch) -> None:
    monkeypatch.setattr(chat_store, "get_collection", lambda: fake_collection)
    monkeypatch.setattr(chat_store, "_indexes_initialized", False)

    first = await chat_store.append_message(
        conversation_id="conversation-1",
        role="assistant",
        content="已完成",
        turn_id="turn-1",
        message_kind="final_answer",
        user_id="user-1",
        farm_id=1,
        idempotency_key="turn:turn-1:assistant:final_answer",
    )
    retry = await chat_store.append_message(
        conversation_id="conversation-1",
        role="assistant",
        content="已完成",
        turn_id="turn-1",
        message_kind="final_answer",
        user_id="user-1",
        farm_id=1,
        idempotency_key="turn:turn-1:assistant:final_answer",
    )

    assert first == retry == "message-1"
    assert len(fake_collection.documents) == 1
    assert any(
        item["options"].get("name") == "uniq_message_idempotency_key"
        for item in fake_collection.indexes
    )


@pytest.mark.asyncio
async def test_observation_append_is_idempotent(fake_observation_collection, monkeypatch) -> None:
    monkeypatch.setattr(
        chat_store, "get_observation_collection", lambda: fake_observation_collection
    )
    monkeypatch.setattr(chat_store, "_observation_indexes_initialized", False)

    payload = {"status": "pending", "turnId": "turn-1"}
    first = await chat_store.append_observation(
        observation_id="turn:turn-1:memory-observation",
        user_id="user-1",
        farm_id=1,
        conversation_id="conversation-1",
        payload=payload,
    )
    retry = await chat_store.append_observation(
        observation_id="turn:turn-1:memory-observation",
        user_id="user-1",
        farm_id=1,
        conversation_id="conversation-1",
        payload=payload,
    )

    assert first["status"] == "ready"
    assert retry["status"] == "idempotent"
    assert len(fake_observation_collection.documents) == 1


@pytest.mark.asyncio
async def test_failed_assistant_message_does_not_advance_session(monkeypatch) -> None:
    persist_state = AsyncMock()
    persist_observation = AsyncMock()
    update_turn = AsyncMock()
    monkeypatch.setattr(worker, "append_message", AsyncMock(return_value=None))
    monkeypatch.setattr(worker, "_persist_session_state", persist_state)
    monkeypatch.setattr(worker, "_persist_observation", persist_observation)
    monkeypatch.setattr(worker, "update_turn", update_turn)

    persisted = await worker._persist_visible_assistant_message(
        Turn(turn_id="turn-1", conversation_id="conversation-1"),
        content="答复",
        message_kind="final_answer",
        trace_id="trace-1",
    )

    assert persisted is False
    persist_state.assert_not_awaited()
    persist_observation.assert_not_awaited()
    update_turn.assert_awaited_once_with(
        "turn-1",
        message_persistence_status="unavailable",
        error_code="conversation_message_persist_failed",
    )


@pytest.fixture
def fake_collection():
    return FakeCollection()


@pytest.fixture
def fake_observation_collection():
    return FakeCollection()


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    monkeypatch.setattr(
        chat_store,
        "settings",
        SimpleNamespace(
            mongodb=SimpleNamespace(
                enabled=True,
                uri="mongodb://fake",
                database="agent",
                tls=False,
                connect_timeout_ms=10,
                server_selection_timeout_ms=10,
                max_pool_size=2,
                collections={},
            )
        ),
    )
