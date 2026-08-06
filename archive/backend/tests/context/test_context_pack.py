"""ContextPack 构建测试。"""

import pytest

from app.context.pack import (
    ContextPack,
    ContextPackDiagnostics,
    ContextPackService,
    MessageSnapshot,
)
from app.domains.conversation.models import Conversation, ConversationMessage
from app.shared.compatibility import UTC


def test_context_pack_service_从_context_顶层导出() -> None:
    from app.context import ContextPackService as ExportedContextPackService

    assert ExportedContextPackService is ContextPackService


def _新建会话(db_session, *, summary=None, meta_json=None):
    conversation = Conversation(
        farm_id=1,
        user_id="test-user-001",
        session_id="context-pack-session",
        summary=summary,
        meta_json=meta_json,
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    return conversation


def _补充消息(db_session, conversation, count):
    messages = []
    for index in range(count):
        message = ConversationMessage(
            conversation_id=conversation.id,
            role="user" if index % 2 == 0 else "assistant",
            content=f"第 {index + 1} 条消息",
        )
        db_session.add(message)
        messages.append(message)
    db_session.commit()
    for message in messages:
        db_session.refresh(message)
    return messages


@pytest.mark.asyncio
async def test_context_pack_读取摘要边界并选择边界后的最近消息(db_session):
    conversation = _新建会话(db_session, summary="完整新版摘要：西棚黄瓜预算 200 元。")
    messages = _补充消息(db_session, conversation, 10)
    boundary_message = messages[5]
    conversation.meta_json = {
        "context_cursor": {
            "summary_version": 2,
            "summarized_until_message_id": boundary_message.id,
            "summarized_until_created_at": boundary_message.created_at.replace(
                tzinfo=UTC
            ).isoformat(),
            "summary_hash": "sha256:abc",
        }
    }
    db_session.commit()

    pack = await ContextPackService(recent_message_limit=4).build(
        db=db_session,
        farm_id=1,
        session_id="context-pack-session",
    )

    assert pack.conversation_id == conversation.id
    assert pack.summary is not None
    assert pack.summary.content == "完整新版摘要：西棚黄瓜预算 200 元。"
    assert pack.summary.version == 2
    assert pack.summary.summarized_until_message_id == boundary_message.id
    assert [message.message_id for message in pack.recent_messages] == [
        message.id for message in messages[6:10]
    ]
    assert pack.diagnostics.recent_message_ids == [
        message.id for message in messages[6:10]
    ]
    assert pack.diagnostics.summary_hash == "sha256:abc"
    assert pack.diagnostics.selected_blocks == [
        "conversation_summary",
        "recent_messages",
    ]


@pytest.mark.asyncio
async def test_context_pack_摘要为空时保留最多十二条最近原文(db_session):
    conversation = _新建会话(db_session)
    messages = _补充消息(db_session, conversation, 15)

    pack = await ContextPackService(recent_message_limit=8).build(
        db=db_session,
        farm_id=1,
        session_id="context-pack-session",
    )

    assert pack.summary is None
    assert [message.message_id for message in pack.recent_messages] == [
        message.id for message in messages[-12:]
    ]
    assert pack.diagnostics.summary_version is None
    assert pack.diagnostics.selected_blocks == ["recent_messages"]


@pytest.mark.asyncio
async def test_context_pack_可转换为_context_builder_兼容_blocks(db_session):
    conversation = _新建会话(db_session, summary="摘要：用户正在确认浇水安排。")
    messages = _补充消息(db_session, conversation, 3)
    conversation.meta_json = {
        "context_cursor": {
            "summary_version": 1,
            "summarized_until_message_id": messages[0].id,
            "summary_hash": "sha256:def",
        }
    }
    db_session.commit()

    pack = await ContextPackService(recent_message_limit=2).build(
        db=db_session,
        farm_id=1,
        session_id="context-pack-session",
    )

    blocks = pack.to_context_blocks()

    assert [block.key for block in blocks] == [
        "conversation_summary",
        "recent_messages",
    ]
    assert blocks[0].metadata["summary_version"] == 1
    assert blocks[0].metadata["summarized_until_message_id"] == messages[0].id
    assert blocks[1].metadata["message_ids"] == [messages[1].id, messages[2].id]
    assert "assistant: 第 2 条消息" in blocks[1].content


@pytest.mark.asyncio
async def test_context_pack_recent_messages_do_not_inline_message_ids(db_session):
    pack = ContextPack(
        conversation_id=1,
        session_id="context-pack-session",
        farm_id=1,
        user_id="test-user-001",
        summary=None,
        recent_messages=[
            MessageSnapshot(
                message_id=1785231256426903159, role="assistant", content="已执行"
            ),
            MessageSnapshot(
                message_id=1785231294639429161, role="user", content="创建种植单元"
            ),
        ],
        diagnostics=ContextPackDiagnostics(
            recent_message_ids=[1785231256426903159, 1785231294639429161],
        ),
    )

    blocks = pack.to_context_blocks()

    assert blocks[0].metadata["message_ids"] == [
        1785231256426903159,
        1785231294639429161,
    ]
    assert "#1785231256426903159" not in blocks[0].content
    assert "assistant: 已执行" in blocks[0].content
