"""Mongo-backed Short Memory 摘要流程测试。"""

from __future__ import annotations

import pytest

from agent import config
from agent.domains.harness.context import summarizer
from agent.platforms.persistence.mongo import chat_store


def _history(turn_count: int = 8) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for index in range(turn_count):
        messages.extend(
            [
                {
                    "role": "user",
                    "content": f"用户问题 {index}",
                    "message_id": f"message-{index}-user",
                },
                {
                    "role": "assistant",
                    "content": f"助手答复 {index}",
                    "message_id": f"message-{index}-assistant",
                },
            ]
        )
    return messages


@pytest.mark.asyncio
async def test_summary_uses_snapshot_revision_and_persists_metadata(monkeypatch) -> None:
    monkeypatch.setattr(config.settings.mongodb, "enabled", True)
    monkeypatch.setattr(
        chat_store,
        "get_conversation_state",
        lambda *args, **kwargs: _async_result(
            {
                "status": "ready",
                "conversation_revision": 4,
                "summary_revision": 0,
            }
        ),
    )
    monkeypatch.setattr(
        chat_store,
        "load_recent",
        lambda *args, **kwargs: _async_result(_history()),
    )
    monkeypatch.setattr(
        chat_store,
        "claim_summary_generation",
        lambda *args, **kwargs: _async_result(
            {
                "ok": True,
                "status": "ready",
                "source_status": "mongo",
                "conversation_revision": 5,
                "summary_status": "generating",
            }
        ),
    )
    saved: dict = {}

    async def save_result(*args, **kwargs):
        saved.update(kwargs)
        return {
            "ok": True,
            "status": "ready",
            "source_status": "mongo",
            "conversation_revision": 6,
            "summary_revision": 1,
        }

    monkeypatch.setattr(chat_store, "save_summary_result", save_result)
    monkeypatch.setattr(
        summarizer,
        "chat",
        lambda messages: {"content": "已确认用户正在追问天气。"},
    )

    result = await summarizer.maybe_summarize_async(
        "conversation-1",
        force=True,
        user_id="user-1",
        farm_id=1,
        source_conversation_revision=4,
    )

    assert result.status == "ready"
    assert result.summary_revision == 1
    assert result.source_from_message_id == "message-0-user"
    assert result.source_to_message_id == "message-1-assistant"
    assert saved["source_conversation_revision"] == 4
    assert saved["expected_revision"] == 5
    assert saved["status"] == "ready"
    assert len(saved["content_hash"]) == 64


@pytest.mark.asyncio
async def test_summary_rejects_stale_snapshot_before_llm(monkeypatch) -> None:
    monkeypatch.setattr(config.settings.mongodb, "enabled", True)
    monkeypatch.setattr(
        chat_store,
        "get_conversation_state",
        lambda *args, **kwargs: _async_result(
            {"status": "ready", "conversation_revision": 5}
        ),
    )
    called = False

    def unexpected_llm(_messages):
        nonlocal called
        called = True
        return {"content": "不应生成"}

    monkeypatch.setattr(summarizer, "chat", unexpected_llm)

    result = await summarizer.maybe_summarize_async(
        "conversation-1",
        force=True,
        user_id="user-1",
        farm_id=1,
        source_conversation_revision=4,
    )

    assert result.status == "conflict"
    assert result.error_code == "summary_source_revision_conflict"
    assert called is False


async def _async_result(value):
    return value
