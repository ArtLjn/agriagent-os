"""Session revision、reset generation 和 source status 的 API 契约测试。"""

from __future__ import annotations

import pytest

from agent.api import conversations, turns


IDENTITY = {
    "user_id": "api-user",
    "farm_id": 7,
    "farm_uid": "api-farm",
}


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
async def test_conversation_detail_keeps_unavailable_state_distinct(monkeypatch) -> None:
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
