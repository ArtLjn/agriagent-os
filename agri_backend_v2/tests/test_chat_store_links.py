"""对话消息与 agri_backend_v2 Turn/Trace 回链字段测试。"""

from __future__ import annotations

import pytest

from agent.infra import chat_store


class FakeCursor:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = list(documents)

    def sort(self, *_args):
        return self

    def limit(self, count: int):
        self.documents = self.documents[:count]
        return self

    async def to_list(self, length: int):
        return self.documents[:length]


class FakeCollection:
    def __init__(self) -> None:
        self.documents = [
            {
                "_id": "message-1",
                "farmId": 1,
                "conversationId": "conversation-1",
                "role": "user",
                "content": "请查看地块状态",
                "createdAt": "2026-08-18T10:00:00Z",
                "turnId": "turn-1",
                "traceId": "trace-1",
                "messageKind": "prompt",
                "meta": {"source": "agent_chat"},
            }
        ]
        self.indexes: list[tuple] = []

    async def create_index(self, keys, **_kwargs):
        self.indexes.append(tuple(keys))

    def find(self, _filter, projection=None):
        documents = []
        for document in self.documents:
            if document["conversationId"] != _filter["conversationId"]:
                continue
            if document["farmId"] != _filter["farmId"]:
                continue
            if projection:
                documents.append(
                    {
                        key: value
                        for key, value in document.items()
                        if projection.get(key) == 1
                    }
                )
            else:
                documents.append(document)
        return FakeCursor(documents)


@pytest.mark.asyncio
async def test_conversation_messages_expose_turn_and_trace_links(monkeypatch) -> None:
    collection = FakeCollection()
    monkeypatch.setattr(chat_store, "get_collection", lambda: collection)
    monkeypatch.setattr(chat_store, "_indexes_initialized", False)

    result = await chat_store.get_conversation(
        "conversation-1", user_id="user-1", farm_id=1
    )

    assert result["items"] == [
        {
            "role": "user",
            "content": "请查看地块状态",
            "created_at": "2026-08-18T10:00:00Z",
            "message_id": "message-1",
            "turn_id": "turn-1",
            "trace_id": "trace-1",
            "message_kind": "prompt",
            "meta": {"source": "agent_chat"},
        }
    ]
    assert len(collection.indexes) == 2
