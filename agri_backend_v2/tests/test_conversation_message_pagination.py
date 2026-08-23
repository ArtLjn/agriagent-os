"""规范历史消息接口的 cursor 分页和一致性测试。"""

from __future__ import annotations

import pytest

from agent.platforms.persistence.mongo import chat_store


class FakeCursor:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = list(documents)

    def sort(self, fields):
        for field, direction in reversed(fields):
            self.documents.sort(
                key=lambda document: document.get(field), reverse=direction < 0
            )
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
                "conversationId": "conversation-1",
                "farmId": 1,
                "userId": "user-1",
                "role": "user",
                "content": "第一条",
                "createdAt": "2026-08-23T10:00:00.000Z",
            },
            {
                "_id": "message-2",
                "conversationId": "conversation-1",
                "farmId": 1,
                "userId": "user-1",
                "role": "assistant",
                "content": "第二条",
                "createdAt": "2026-08-23T10:00:00.000Z",
            },
            {
                "_id": "message-3",
                "conversationId": "conversation-1",
                "farmId": 1,
                "userId": "user-1",
                "role": "user",
                "content": "第三条",
                "createdAt": "2026-08-23T10:01:00.000Z",
            },
        ]

    def find(self, filter_doc, projection=None):
        documents = []
        for document in self.documents:
            if any(
                document.get(key) != value
                for key, value in filter_doc.items()
                if key not in {"$or"}
            ):
                continue
            if "$or" in filter_doc:
                older = filter_doc["$or"]
                before_time = older[0]["createdAt"]["$lt"]
                same_time_before_id = older[1]["_id"]["$lt"]
                if not (
                    document["createdAt"] < before_time
                    or (
                        document["createdAt"] == older[1]["createdAt"]
                        and document["_id"] < same_time_before_id
                    )
                ):
                    continue
            documents.append(
                {
                    key: value
                    for key, value in document.items()
                    if not projection or projection.get(key) == 1
                }
            )
        return FakeCursor(documents)

    async def count_documents(self, filter_doc):
        return sum(
            all(document.get(key) == value for key, value in filter_doc.items())
            for document in self.documents
        )


@pytest.mark.asyncio
async def test_message_page_returns_latest_slice_and_older_cursor(monkeypatch) -> None:
    collection = FakeCollection()
    monkeypatch.setattr(chat_store, "get_collection", lambda: collection)
    monkeypatch.setattr(chat_store, "_indexes_initialized", False)
    monkeypatch.setattr(chat_store.settings.auth, "jwt_secret", "pagination-secret")

    first = await chat_store.get_conversation_messages(
        "conversation-1",
        limit=2,
        snapshot_revision=4,
        user_id="user-1",
        farm_id=1,
    )

    assert [item["message_id"] for item in first["items"]] == [
        "message-2",
        "message-3",
    ]
    assert first["message_count"] == 3
    assert first["pagination"]["direction"] == "older"
    assert first["pagination"]["snapshot_revision"] == 4
    assert first["next_cursor"]

    second = await chat_store.get_conversation_messages(
        "conversation-1",
        limit=2,
        cursor=first["next_cursor"],
        snapshot_revision=4,
        user_id="user-1",
        farm_id=1,
    )

    assert [item["message_id"] for item in second["items"]] == ["message-1"]
    assert second["has_more"] is False

    collection.documents.append(
        {
            "_id": "message-4",
            "conversationId": "conversation-1",
            "farmId": 1,
            "userId": "user-1",
            "role": "assistant",
            "content": "后来新增",
            "createdAt": "2026-08-23T10:02:00.000Z",
        }
    )
    refreshed = await chat_store.get_conversation_messages(
        "conversation-1",
        limit=2,
        snapshot_revision=5,
        user_id="user-1",
        farm_id=1,
    )
    assert [item["message_id"] for item in refreshed["items"]] == [
        "message-3",
        "message-4",
    ]


@pytest.mark.asyncio
async def test_message_cursor_rejects_revision_change(monkeypatch) -> None:
    monkeypatch.setattr(chat_store.settings.auth, "jwt_secret", "pagination-secret")
    cursor = chat_store._encode_conversation_cursor(
        {
            "v": 1,
            "conversation_id": "conversation-1",
            "user_id": "user-1",
            "farm_id": 1,
            "direction": "older",
            "snapshot_revision": 4,
            "anchor": {
                "created_at": "2026-08-23T10:00:00.000Z",
                "message_id": "message-1",
            },
        }
    )

    with pytest.raises(chat_store.ConversationCursorError) as raised:
        chat_store._decode_conversation_cursor(
            cursor,
            conversation_id="conversation-1",
            user_id="user-1",
            farm_id=1,
            snapshot_revision=5,
        )

    assert raised.value.code == "conversation_revision_changed"


def test_message_cursor_rejects_malformed_payload(monkeypatch) -> None:
    monkeypatch.setattr(chat_store.settings.auth, "jwt_secret", "pagination-secret")

    with pytest.raises(chat_store.ConversationCursorError) as raised:
        chat_store._decode_conversation_cursor(
            "not-a-valid-cursor",
            conversation_id="conversation-1",
            user_id="user-1",
            farm_id=1,
            snapshot_revision=4,
        )

    assert raised.value.code == "conversation_cursor_invalid"


def test_message_projection_normalizes_kind_and_filters_meta() -> None:
    assert chat_store._normalize_message_kind("assistant_answer") == "final_answer"
    assert chat_store._normalize_message_kind(None) is None
    assert chat_store._normalize_message_kind("tool_started") is None
    assert chat_store._sanitize_message_meta(None) == {}
    assert chat_store._sanitize_message_meta(
        {
            "outcome": "completed",
            "tool_summary": "查询完成",
            "tool_arguments": {"location": "苏州"},
        }
    ) == {"outcome": "completed", "tool_summary": "查询完成"}
