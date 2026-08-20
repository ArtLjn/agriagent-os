"""Conversation state Mongo 边界测试，不连接真实 Mongo。"""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from agent.infra import chat_store


class FakeUpdateResult:
    def __init__(self, *, matched_count: int, upserted_id: str | None = None) -> None:
        self.matched_count = matched_count
        self.upserted_id = upserted_id


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict] = []
        self.indexes: list[dict] = []
        self._next_id = 1

    async def create_index(self, keys, **options):
        self.indexes.append({"keys": tuple(keys), "options": options})

    async def find_one(self, filter_doc):
        for document in self.documents:
            if all(document.get(key) == value for key, value in filter_doc.items()):
                return deepcopy(document)
        return None

    async def update_one(self, filter_doc, update_doc, *, upsert):
        for document in self.documents:
            if all(document.get(key) == value for key, value in filter_doc.items()):
                document.update(deepcopy(update_doc.get("$set", {})))
                for key, value in update_doc.get("$inc", {}).items():
                    document[key] = document.get(key, 0) + value
                return FakeUpdateResult(matched_count=1)

        if not upsert:
            return FakeUpdateResult(matched_count=0)
        document = deepcopy(update_doc.get("$setOnInsert", {}))
        document.update(deepcopy(update_doc.get("$set", {})))
        for key, value in update_doc.get("$inc", {}).items():
            document[key] = document.get(key, 0) + value
        document["_id"] = f"state-{self._next_id}"
        self._next_id += 1
        self.documents.append(document)
        return FakeUpdateResult(matched_count=0, upserted_id=document["_id"])


@pytest.fixture
def fake_state_store(monkeypatch):
    collection = FakeCollection()
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
            ),
            context=SimpleNamespace(
                conversation_state=SimpleNamespace(collection="conversationStates")
            ),
        ),
    )
    monkeypatch.setattr(chat_store, "get_state_collection", lambda: collection)
    monkeypatch.setattr(chat_store, "_state_indexes_initialized", False)
    return collection


@pytest.mark.asyncio
async def test_state_is_tenant_scoped_and_has_unique_indexes(fake_state_store) -> None:
    saved = await chat_store.save_conversation_state(
        "conversation-1",
        user_id="user-1",
        farm_id=1,
        farm_uid="farm-a",
        summary="已确认地块 A",
        summary_status="ready",
        idempotency_key="write-1",
    )

    assert saved["ok"] is True
    assert saved["conversation_revision"] == 1
    assert saved["summary_status"] == "ready"
    assert (
        await chat_store.get_conversation_state(
            "conversation-1", user_id="user-2", farm_id=1
        )
        is None
    )
    assert (
        await chat_store.get_conversation_state(
            "conversation-1", user_id="user-1", farm_id=1
        )
    )["summary"] == "已确认地块 A"

    assert {item["options"].get("name") for item in fake_state_store.indexes} == {
        "uniq_conversation_state_tenant",
        "idx_conversation_state_updated",
    }
    unique_index = next(
        item
        for item in fake_state_store.indexes
        if item["options"].get("name") == "uniq_conversation_state_tenant"
    )
    assert unique_index["options"]["unique"] is True
    assert unique_index["keys"] == (
        ("userId", 1),
        ("farmId", 1),
        ("conversationId", 1),
    )


@pytest.mark.asyncio
async def test_state_revision_cas_rejects_stale_writer(fake_state_store) -> None:
    first = await chat_store.save_conversation_state(
        "conversation-1", user_id="user-1", farm_id=1
    )
    current = await chat_store.save_conversation_state(
        "conversation-1",
        user_id="user-1",
        farm_id=1,
        expected_revision=first["conversation_revision"],
        pending_action={"type": "approval"},
    )
    stale = await chat_store.save_conversation_state(
        "conversation-1",
        user_id="user-1",
        farm_id=1,
        expected_revision=first["conversation_revision"],
        summary="旧摘要",
    )

    assert current["conversation_revision"] == 2
    assert stale["status"] == "conflict"
    assert stale["code"] == "conversation_state_revision_conflict"
    assert stale["actual_revision"] == 2
    persisted = await chat_store.get_conversation_state(
        "conversation-1", user_id="user-1", farm_id=1
    )
    assert persisted["summary"] is None
    assert persisted["pending_action"] == {"type": "approval"}


@pytest.mark.asyncio
async def test_state_write_is_idempotent_for_same_key(fake_state_store) -> None:
    first = await chat_store.save_conversation_state(
        "conversation-1",
        user_id="user-1",
        farm_id=1,
        expected_revision=0,
        reset_generation=1,
        idempotency_key="turn-1-finalize",
    )
    retry = await chat_store.save_conversation_state(
        "conversation-1",
        user_id="user-1",
        farm_id=1,
        expected_revision=0,
        reset_generation=1,
        idempotency_key="turn-1-finalize",
    )

    assert first["conversation_revision"] == 1
    assert retry["ok"] is True
    assert retry["status"] == "idempotent"
    assert retry["conversation_revision"] == 1
    assert retry["reset_generation"] == 1


@pytest.mark.asyncio
async def test_state_boundary_reports_unavailable_without_fake_success(
    monkeypatch,
) -> None:
    monkeypatch.setattr(chat_store, "get_state_collection", lambda: None)

    result = await chat_store.save_conversation_state(
        "conversation-1", user_id="user-1", farm_id=1
    )

    assert result == {
        "ok": False,
        "status": "unavailable",
        "source_status": "unavailable",
        "code": "conversation_state_unavailable",
        "operation": "save_conversation_state",
    }
