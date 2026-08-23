"""Session revision、reset generation 和 source status 的 API 契约测试。"""

from __future__ import annotations

import pytest

from agent.api import api_router, conversations, turns


IDENTITY = {
    "user_id": "api-user",
    "farm_id": 7,
    "farm_uid": "api-farm",
}


def test_conversation_history_routes_register() -> None:
    paths = {route.path for route in api_router.routes}

    assert "/api/v2/conversations/{conversation_id}/messages" in paths
    assert "/api/v2/conversations/{conversation_id}/turns" in paths
    assert "/api/v2/conversations/{conversation_id}/turns/{turn_id}" in paths


@pytest.mark.asyncio
async def test_turn_status_normalizes_context_metadata(monkeypatch) -> None:
    async def fake_get_turn(_turn_id: str) -> dict[str, str]:
        return {
            "turn_id": "turn-1",
            "user_id": "api-user",
            "farm_id": "7",
            "conversation_revision": "12",
            "summary_revision": "3",
            "reset_generation": "2",
            "context_source_status": "mongo",
        }

    monkeypatch.setattr(turns, "get_turn", fake_get_turn)
    monkeypatch.setattr(turns, "parse_identity", lambda _authorization: IDENTITY)

    result = await turns.turn_status("turn-1", authorization="Bearer test")

    assert result["conversation_revision"] == 12
    assert result["summary_revision"] == 3
    assert result["reset_generation"] == 2
    assert result["source_status"] == "mongo"
    assert result["context_source_status"] == "mongo"


@pytest.mark.asyncio
async def test_conversation_detail_exposes_state_metadata(monkeypatch) -> None:
    async def fake_get_conversation(*_args, **_kwargs) -> dict:
        return {"items": [{"role": "user", "content": "你好"}], "next": None}

    async def fake_get_state(*_args, **_kwargs) -> dict:
        return {
            "conversation_revision": 12,
            "summary_revision": 3,
            "reset_generation": 2,
            "source_status": "mongo",
        }

    monkeypatch.setattr(conversations, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(conversations, "get_conversation_state", fake_get_state)
    monkeypatch.setattr(
        conversations, "parse_identity", lambda _authorization: IDENTITY
    )

    result = await conversations.conversation_detail(
        "conversation-1", authorization="Bearer test"
    )

    assert result["conversation_revision"] == 12
    assert result["summary_revision"] == 3
    assert result["reset_generation"] == 2
    assert result["source_status"] == "mongo"
    assert result["context_source_status"] == "mongo"


@pytest.mark.asyncio
async def test_conversation_detail_keeps_unavailable_state_distinct(
    monkeypatch,
) -> None:
    async def fake_get_conversation(*_args, **_kwargs) -> dict:
        return {"items": [], "next": None}

    async def fake_get_state(*_args, **_kwargs) -> dict:
        return {"status": "unavailable", "source_status": "unavailable"}

    monkeypatch.setattr(conversations, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(conversations, "get_conversation_state", fake_get_state)
    monkeypatch.setattr(
        conversations, "parse_identity", lambda _authorization: IDENTITY
    )

    result = await conversations.conversation_detail(
        "conversation-1", authorization="Bearer test"
    )

    assert result["source_status"] == "unavailable"
    assert result["conversation_revision"] == 0


@pytest.mark.asyncio
async def test_conversation_messages_returns_page_contract(monkeypatch) -> None:
    async def fake_get_state(*_args, **_kwargs) -> dict:
        return {
            "conversation_revision": 12,
            "summary_revision": 3,
            "reset_generation": 2,
            "source_status": "mongo",
        }

    async def fake_get_messages(*_args, **_kwargs) -> dict:
        return {
            "conversation_id": "conversation-1",
            "items": [
                {
                    "message_id": "message-1",
                    "turn_id": "turn-1",
                    "trace_id": "trace-1",
                    "role": "assistant",
                    "content": "结果",
                    "created_at": "2026-08-23T10:00:00Z",
                    "message_kind": "final_answer",
                    "meta": {"outcome": "completed"},
                }
            ],
            "message_count": 4,
            "page_count": 1,
            "has_more": True,
            "next_cursor": "opaque-cursor",
            "latest_message_id": "message-1",
            "pagination": {
                "next_cursor": "opaque-cursor",
                "has_more": True,
                "page_count": 1,
                "limit": 100,
                "direction": "older",
                "snapshot_revision": 12,
                "consistency": "snapshot",
            },
            "source_status": "mongo",
        }

    monkeypatch.setattr(conversations, "get_conversation_state", fake_get_state)
    monkeypatch.setattr(conversations, "get_conversation_messages", fake_get_messages)
    monkeypatch.setattr(
        conversations, "parse_identity", lambda _authorization: IDENTITY
    )

    result = await conversations.conversation_messages(
        "conversation-1", limit=100, authorization="Bearer test"
    )

    assert result["items"][0]["message_id"] == "message-1"
    assert result["message_count"] == 4
    assert result["page_count"] == 1
    assert result["pagination"]["snapshot_revision"] == 12
    assert result["conversation_revision"] == 12
    assert result["source_status"] == "mongo"


@pytest.mark.asyncio
async def test_conversation_messages_maps_cursor_conflict_to_409(monkeypatch) -> None:
    async def fake_get_state(*_args, **_kwargs) -> dict:
        return {"conversation_revision": 12, "source_status": "mongo"}

    async def fake_get_messages(*_args, **_kwargs) -> dict:
        raise conversations.ConversationCursorError(
            "conversation_revision_changed", "会话内容已更新，请重新加载最新历史"
        )

    monkeypatch.setattr(conversations, "get_conversation_state", fake_get_state)
    monkeypatch.setattr(conversations, "get_conversation_messages", fake_get_messages)
    monkeypatch.setattr(
        conversations, "parse_identity", lambda _authorization: IDENTITY
    )

    with pytest.raises(conversations.HTTPException) as raised:
        await conversations.conversation_messages(
            "conversation-1", cursor="old-cursor", authorization="Bearer test"
        )

    assert raised.value.status_code == 409
    assert raised.value.detail["code"] == "conversation_revision_changed"


@pytest.mark.asyncio
async def test_conversation_turns_joins_trace_summary_and_message_ids(
    monkeypatch,
) -> None:
    async def fake_get_conversation(*_args, **_kwargs) -> dict:
        return {
            "items": [
                {
                    "message_id": "message-1",
                    "turn_id": "turn-1",
                    "role": "user",
                    "message_kind": "prompt",
                },
                {
                    "message_id": "message-2",
                    "turn_id": "turn-1",
                    "role": "assistant",
                    "message_kind": "final_answer",
                },
            ]
        }

    async def fake_list_traces(*_args, **_kwargs) -> dict:
        return {
            "items": [
                {
                    "trace_id": "trace-1",
                    "turn_id": "turn-1",
                    "status": "completed",
                    "status_reason": "completed",
                    "metrics": None,
                    "root_error": None,
                    "started_at": "2026-08-23T10:00:00Z",
                    "ended_at": "2026-08-23T10:00:05Z",
                }
            ],
            "next_cursor": None,
            "has_more": False,
            "evidence_status": "ok",
            "evidence": {"source": "traceRequestSummaries", "status": "available"},
        }

    monkeypatch.setattr(conversations, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(conversations, "list_traces", fake_list_traces)
    monkeypatch.setattr(
        conversations, "parse_identity", lambda _authorization: IDENTITY
    )

    result = await conversations.conversation_turns(
        "conversation-1", authorization="Bearer test"
    )

    assert result["items"][0]["turn_id"] == "turn-1"
    assert result["items"][0]["message_ids"] == {
        "prompt": "message-1",
        "answer": "message-2",
    }
    assert result["items"][0]["events_status"] == "available"
    assert result["items"][0]["step_count"] == 0


@pytest.mark.asyncio
async def test_conversation_turn_detail_returns_evidence_status(monkeypatch) -> None:
    async def fake_get_turn(*_args, **_kwargs) -> dict:
        return {
            "turn_id": "turn-1",
            "conversation_id": "conversation-1",
            "user_id": "api-user",
            "farm_uid": "api-farm",
            "status": "completed",
            "trace_id": "trace-1",
            "step_count": "2",
            "committed_result": {
                "record_id": "record-1",
                "authorization": "secret",
            },
            "approved": True,
        }

    async def fake_get_conversation(*_args, **_kwargs) -> dict:
        return {
            "items": [
                {
                    "message_id": "message-1",
                    "turn_id": "turn-1",
                    "role": "user",
                    "message_kind": "prompt",
                }
            ]
        }

    async def fake_get_summary(*_args, **_kwargs) -> dict:
        return {"status": "completed", "status_reason": "completed"}

    async def fake_get_timeline(*_args, **_kwargs) -> dict:
        return {
            "items": [{"event_id": "event-1", "event_type": "turn.completed"}],
            "evidence_status": "ok",
            "evidence": {
                "nodes": {"status": "available"},
                "events": {"status": "available"},
            },
        }

    monkeypatch.setattr(conversations, "get_turn", fake_get_turn)
    monkeypatch.setattr(conversations, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(conversations, "get_trace_summary", fake_get_summary)
    monkeypatch.setattr(conversations, "get_trace_timeline", fake_get_timeline)
    monkeypatch.setattr(
        conversations, "parse_identity", lambda _authorization: IDENTITY
    )

    result = await conversations.conversation_turn_detail(
        "conversation-1", "turn-1", authorization="Bearer test"
    )

    assert result["trace_id"] == "trace-1"
    assert result["status"] == "completed"
    assert result["business_result"] == {
        "record_id": "record-1",
        "authorization": "[REDACTED]",
    }
    assert result["approval"] == {"status": "approved"}
    assert result["events_status"] == "available"
    assert result["evidence"] == {
        "runtime_turn": "available",
        "trace_summary": "available",
        "trace_nodes": "available",
        "trace_events": "available",
        "conversation_messages": "available",
    }


@pytest.mark.asyncio
async def test_conversation_turn_detail_rejects_payload_for_normal_user(
    monkeypatch,
) -> None:
    async def fake_get_turn(*_args, **_kwargs) -> dict:
        return {
            "turn_id": "turn-1",
            "conversation_id": "conversation-1",
            "user_id": "api-user",
            "farm_uid": "api-farm",
            "trace_id": "trace-1",
        }

    monkeypatch.setattr(conversations, "get_turn", fake_get_turn)

    async def fake_get_conversation(*_args, **_kwargs) -> dict:
        return {"items": []}

    monkeypatch.setattr(conversations, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(
        conversations,
        "parse_identity",
        lambda _authorization: {**IDENTITY, "role": "user"},
    )

    with pytest.raises(conversations.HTTPException) as raised:
        await conversations.conversation_turn_detail(
            "conversation-1",
            "turn-1",
            include_payload=True,
            authorization="Bearer test",
        )

    assert raised.value.status_code == 403
    assert raised.value.detail["code"] == "trace_payload_forbidden"


@pytest.mark.asyncio
async def test_conversation_turn_detail_exposes_unavailable_trace_evidence(
    monkeypatch,
) -> None:
    async def fake_get_turn(*_args, **_kwargs) -> dict:
        return {
            "turn_id": "turn-1",
            "conversation_id": "conversation-1",
            "user_id": "api-user",
            "farm_uid": "api-farm",
            "trace_id": "trace-1",
        }

    async def fake_get_conversation(*_args, **_kwargs) -> dict:
        return {"items": []}

    async def fake_get_summary(*_args, **_kwargs) -> dict | None:
        return None

    async def fake_get_timeline(*_args, **_kwargs) -> dict:
        return {
            "items": [],
            "evidence_status": "unavailable",
            "evidence": {},
        }

    monkeypatch.setattr(conversations, "get_turn", fake_get_turn)
    monkeypatch.setattr(conversations, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(conversations, "get_trace_summary", fake_get_summary)
    monkeypatch.setattr(conversations, "get_trace_timeline", fake_get_timeline)
    monkeypatch.setattr(
        conversations, "parse_identity", lambda _authorization: IDENTITY
    )

    result = await conversations.conversation_turn_detail(
        "conversation-1", "turn-1", authorization="Bearer test"
    )

    assert result["events_status"] == "error"
    assert result["source_status"] == "unavailable"
