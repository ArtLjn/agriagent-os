"""会话 running summary 集成流测试。"""

from unittest.mock import AsyncMock

import pytest

from app.context.selectors import ConversationSelector
from app.memory.service import InMemoryMemoryService
from app.models.conversation import Conversation, ConversationMessage


@pytest.mark.asyncio
async def test_running_summary_written_after_multiturn_and_injected_into_context(
    db_session,
    monkeypatch,
) -> None:
    """多轮对话达到阈值后写入 summary，并由 ConversationSelector 注入。"""
    from app.memory import service as service_module

    conversation = Conversation(
        farm_id=1,
        user_id="test-user-001",
        session_id="summary-flow-session",
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    for index in range(13):
        db_session.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"第 {index + 1} 轮：西棚黄瓜预算 200 元",
            )
        )
    db_session.commit()

    monkeypatch.setattr(service_module.settings.ai, "enable_session_summary", True)
    monkeypatch.setattr(
        service_module.settings.ai,
        "session_summary_message_threshold",
        12,
    )
    monkeypatch.setattr(
        service_module.settings.ai, "session_summary_debounce_minutes", 30
    )
    monkeypatch.setattr(service_module, "get_llm", lambda role: object())
    monkeypatch.setattr(
        service_module,
        "generate_summary",
        AsyncMock(return_value="用户反复确认西棚黄瓜预算 200 元。"),
    )

    service = InMemoryMemoryService()
    await service.maybe_summarize(
        db_session,
        conversation.id,
        farm_id=1,
        session_id="summary-flow-session",
        messages=None,
    )

    db_session.refresh(conversation)
    assert conversation.summary == "用户反复确认西棚黄瓜预算 200 元。"
    blocks = ConversationSelector().select(
        db_session,
        farm_id=1,
        session_id="summary-flow-session",
    )
    blocks_by_key = {block.key: block for block in blocks}
    assert "conversation_summary" in blocks_by_key
    assert "西棚黄瓜预算 200 元" in blocks_by_key["conversation_summary"].content
