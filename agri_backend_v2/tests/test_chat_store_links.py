"""对话消息与 agri_backend_v2 Turn/Trace 回链字段测试。"""

from __future__ import annotations

import pytest

from agent.platforms.persistence.mongo import chat_store


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
    assert len(collection.indexes) == 3


@pytest.mark.asyncio
async def test_conversation_cursor_excludes_previous_pages_and_preserves_tenant(
    monkeypatch,
) -> None:
    class ConversationCollection:
        def __init__(self):
            self.pipelines = []
            self.rows = [
                {"_id": name, "last_at": time, "last_msg": name}
                for name, time in [
                    ("c", "2026-10-04"),
                    ("b", "2026-10-04"),
                    ("a", "2026-10-03"),
                ]
            ]

        async def find_one(self, query, *, sort):
            assert query["farmId"] == 7 and query["userId"] == "user-1"
            assert sort[0] == ("createdAt", -1)
            return (
                {"createdAt": "2026-10-04"} if query["conversationId"] == "b" else None
            )

        def aggregate(self, pipeline):
            self.pipelines.append(pipeline)
            rows = self.rows
            filters = [stage["$match"] for stage in pipeline if "$match" in stage]
            assert filters[0] == {"farmId": 7, "userId": "user-1"}
            if len(filters) > 1:
                boundary = filters[1]["$or"]
                rows = [
                    row
                    for row in rows
                    if row["last_at"] < boundary[0]["last_at"]["$lt"]
                    or (
                        row["last_at"] == boundary[1]["last_at"]
                        and row["_id"] < boundary[1]["_id"]["$lt"]
                    )
                ]
            return FakeCursor(rows).limit(pipeline[-1]["$limit"])

    collection = ConversationCollection()
    monkeypatch.setattr(chat_store, "get_collection", lambda: collection)
    first = await chat_store.list_conversations(limit=2, user_id="user-1", farm_id=7)
    assert [item["conversation_id"] for item in first["items"]] == ["c", "b"]
    second = await chat_store.list_conversations(
        limit=2, cursor=first["next_cursor"], user_id="user-1", farm_id=7
    )
    assert [item["conversation_id"] for item in second["items"]] == ["a"]
    assert second["has_more"] is False
    missing = await chat_store.list_conversations(
        cursor="foreign-conversation", user_id="user-1", farm_id=7
    )
    assert missing["items"] == []
