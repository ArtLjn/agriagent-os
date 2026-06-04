"""Agent Application 聊天用例测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.application.chat_use_case import chat, stream_chat_events
from app.schemas.agent import ChatRequest


pytestmark = pytest.mark.asyncio


def _mock_farm() -> MagicMock:
    farm = MagicMock()
    farm.id = 1
    farm.user_id = "user-1"
    farm.uid = "farm-uid-1"
    return farm


def _mock_user() -> MagicMock:
    user = MagicMock()
    user.id = "user-1"
    return user


async def test_chat_invokes_pending_executor_and_advisor_without_legacy_service():
    """未处理 pending 时由 Application 调 executor 后继续调用 advisor。"""
    db = MagicMock()
    farm = _mock_farm()

    with (
        patch(
            "app.agent.application.chat_use_case.invoke_advisor",
            new_callable=AsyncMock,
        ) as mock_advisor,
        patch(
            "app.agent.application.chat_use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.agent.application.chat_use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ) as mock_observe,
        patch(
            "app.services.agent_service.chat_with_agent",
            new_callable=AsyncMock,
        ) as mock_legacy_chat,
    ):
        from app.agent.executor.models import PendingActionDecision

        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_advisor.return_value = "建议回复"

        result = await chat(
            db,
            ChatRequest(message="今天做什么", session_id=None),
            farm,
            request_id="req-1",
        )

    assert result.reply == "建议回复"
    mock_pending.assert_awaited_once_with(
        farm_id=farm.id,
        message="今天做什么",
    )
    mock_advisor.assert_awaited_once()
    mock_observe.assert_awaited_once()
    mock_legacy_chat.assert_not_awaited()
    db.add.assert_called_once()
    db.commit.assert_called_once()


async def test_chat_saves_handled_pending_reply_without_invoking_advisor():
    """pending 已处理时保存回复并跳过 advisor。"""
    db = MagicMock()
    farm = _mock_farm()

    with (
        patch(
            "app.agent.application.chat_use_case.invoke_advisor",
            new_callable=AsyncMock,
        ) as mock_advisor,
        patch(
            "app.agent.application.chat_use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.agent.application.chat_use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ) as mock_observe,
        patch(
            "app.services.agent_service.chat_with_agent",
            new_callable=AsyncMock,
        ) as mock_legacy_chat,
    ):
        from app.agent.executor.models import PendingActionDecision

        mock_pending.return_value = PendingActionDecision.confirmed("已执行：已记账")

        result = await chat(
            db,
            ChatRequest(message="确认", session_id=None),
            farm,
            request_id="req-1",
        )

    assert result.reply == "已执行：已记账"
    mock_pending.assert_awaited_once_with(
        farm_id=farm.id,
        message="确认",
    )
    mock_advisor.assert_not_awaited()
    mock_observe.assert_awaited_once()
    mock_legacy_chat.assert_not_awaited()
    db.add.assert_called_once()
    db.commit.assert_called_once()


async def test_chat_with_session_id_saves_user_and_assistant_messages():
    """session_id 存在时保存用户和助手消息到会话。"""
    db = MagicMock()
    farm = _mock_farm()
    conversation = MagicMock()
    conversation.id = 42

    with (
        patch(
            "app.agent.application.chat_use_case.get_or_create_conversation",
            return_value=conversation,
        ) as mock_get_conversation,
        patch("app.agent.application.chat_use_case.save_message") as mock_save_message,
        patch(
            "app.agent.application.chat_use_case.invoke_advisor",
            new_callable=AsyncMock,
        ) as mock_advisor,
        patch(
            "app.agent.application.chat_use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.agent.application.chat_use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ),
    ):
        from app.agent.executor.models import PendingActionDecision

        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_advisor.return_value = "回复内容"

        result = await chat(
            db,
            ChatRequest(message="你好", session_id="sess-123"),
            farm,
            request_id="req-1",
        )

    assert result.reply == "回复内容"
    mock_get_conversation.assert_called_once_with(
        db,
        farm.id,
        "sess-123",
        user_id=farm.user_id,
    )
    assert mock_save_message.call_count == 2
    mock_save_message.assert_any_call(db, 42, "user", "你好")
    mock_save_message.assert_any_call(db, 42, "assistant", "回复内容")
    mock_advisor.assert_awaited_once()


async def test_chat_with_session_id_passes_conversation_context_to_advisor():
    """session_id 存在时将会话上下文传给 advisor。"""
    db = MagicMock()
    farm = _mock_farm()
    conversation = MagicMock()
    conversation.id = 99

    with (
        patch(
            "app.agent.application.chat_use_case.get_or_create_conversation",
            return_value=conversation,
        ),
        patch("app.agent.application.chat_use_case.save_message"),
        patch(
            "app.agent.application.chat_use_case.invoke_advisor",
            new_callable=AsyncMock,
        ) as mock_advisor,
        patch(
            "app.agent.application.chat_use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.agent.application.chat_use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ),
    ):
        from app.agent.executor.models import PendingActionDecision

        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_advisor.return_value = "回复"

        await chat(
            db,
            ChatRequest(message="问题", session_id="sess-abc"),
            farm,
            request_id="req-1",
        )

    mock_advisor.assert_awaited_once_with(
        "问题",
        farm_id=farm.id,
        db=db,
        conversation_id=99,
        session_id="sess-abc",
        request_id="req-1",
        user_id=farm.user_id,
    )


async def test_chat_without_session_id_does_not_save_conversation_messages():
    """无 session_id 时不写会话消息。"""
    db = MagicMock()
    farm = _mock_farm()

    with (
        patch("app.agent.application.chat_use_case.save_message") as mock_save_message,
        patch(
            "app.agent.application.chat_use_case.invoke_advisor",
            new_callable=AsyncMock,
        ) as mock_advisor,
        patch(
            "app.agent.application.chat_use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.agent.application.chat_use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ),
    ):
        from app.agent.executor.models import PendingActionDecision

        mock_pending.return_value = PendingActionDecision.unhandled()
        mock_advisor.return_value = "回复"

        result = await chat(
            db,
            ChatRequest(message="问题"),
            farm,
            request_id="req-1",
        )

    assert result.reply == "回复"
    mock_save_message.assert_not_called()


async def test_chat_pending_confirm_saves_to_conversation():
    """pending action 确认路径保存助手回复到会话。"""
    db = MagicMock()
    farm = _mock_farm()
    conversation = MagicMock()
    conversation.id = 10

    with (
        patch(
            "app.agent.application.chat_use_case.get_or_create_conversation",
            return_value=conversation,
        ),
        patch("app.agent.application.chat_use_case.save_message") as mock_save_message,
        patch(
            "app.agent.application.chat_use_case.invoke_advisor",
            new_callable=AsyncMock,
        ) as mock_advisor,
        patch(
            "app.agent.application.chat_use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.agent.application.chat_use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ),
    ):
        from app.agent.executor.models import PendingActionDecision

        mock_pending.return_value = PendingActionDecision.confirmed("已执行：已记账")

        result = await chat(
            db,
            ChatRequest(message="确认", session_id="sess-confirm"),
            farm,
            request_id="req-1",
        )

    assert result.reply == "已执行：已记账"
    mock_advisor.assert_not_awaited()
    assert mock_save_message.call_count == 2
    mock_save_message.assert_any_call(db, 10, "user", "确认")
    mock_save_message.assert_any_call(db, 10, "assistant", "已执行：已记账")


async def test_stream_chat_handles_pending_without_legacy_service_or_advisor():
    """流式 pending 已处理时由 Application 收尾，不委托旧 service 或 advisor。"""
    db = MagicMock()
    user = _mock_user()
    farm = _mock_farm()

    with (
        patch(
            "app.agent.application.chat_use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.agent.application.chat_use_case.stream_advisor",
        ) as mock_stream_advisor,
        patch(
            "app.agent.application.chat_use_case._flush_trace_queue",
            new_callable=AsyncMock,
        ) as mock_flush,
        patch(
            "app.agent.application.chat_use_case._get_skill_names",
            return_value=[],
        ) as mock_get_skills,
        patch(
            "app.agent.application.chat_use_case._save_stream_reply",
            return_value=None,
        ) as mock_save_reply,
        patch(
            "app.agent.application.chat_use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ) as mock_observe,
        patch(
            "app.agent.application.chat_use_case.build_pending_action_response",
            return_value=None,
        ),
    ):
        from app.agent.executor.models import PendingActionDecision

        mock_pending.return_value = PendingActionDecision.confirmed("已执行：已记账")

        events = [
            event
            async for event in stream_chat_events(
                db,
                ChatRequest(message="确认", session_id=None),
                user,
                farm,
                request_id="req-stream-1",
            )
        ]

    assert events[0] == 'data: {"content": "已执行：已记账"}\n\n'
    assert events[-1] == "data: [DONE]\n\n"
    mock_pending.assert_awaited_once_with(farm_id=farm.id, message="确认")
    mock_stream_advisor.assert_not_called()
    mock_flush.assert_awaited_once()
    mock_get_skills.assert_called_once_with(db, "req-stream-1")
    mock_save_reply.assert_called_once()
    mock_observe.assert_awaited_once_with(
        user_id=user.id,
        farm_id=farm.id,
        session_id=None,
        user_input="确认",
        assistant_reply="已执行：已记账",
        skills_called=[],
        request_id="req-stream-1",
    )


async def test_stream_chat_routes_unhandled_pending_to_stream_advisor():
    """pending 未处理时 Application 直接调用 advisor 流并继续 SSE 收尾。"""
    db = MagicMock()
    user = _mock_user()
    farm = _mock_farm()
    conversation = MagicMock()
    conversation.id = 88

    async def _fake_stream(*args, **kwargs):
        yield "chunk1"
        yield "chunk2"

    with (
        patch(
            "app.agent.application.chat_use_case.get_or_create_conversation",
            return_value=conversation,
        ),
        patch("app.agent.application.chat_use_case.save_message"),
        patch(
            "app.agent.application.chat_use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.agent.application.chat_use_case.stream_advisor",
            side_effect=_fake_stream,
        ) as mock_stream_advisor,
        patch(
            "app.agent.application.chat_use_case._flush_trace_queue",
            new_callable=AsyncMock,
        ),
        patch(
            "app.agent.application.chat_use_case._get_skill_names",
            return_value=[],
        ),
        patch(
            "app.agent.application.chat_use_case._save_stream_reply",
            return_value=None,
        ),
        patch(
            "app.agent.application.chat_use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ),
        patch(
            "app.agent.application.chat_use_case.build_pending_action_response",
            return_value=None,
        ),
    ):
        from app.agent.executor.models import PendingActionDecision

        mock_pending.return_value = PendingActionDecision.unhandled()

        events = [
            event
            async for event in stream_chat_events(
                db,
                ChatRequest(message="问题", cycle_id=7, session_id="sess-stream"),
                user,
                farm,
                request_id="req-stream-2",
            )
        ]

    assert events[:2] == [
        'data: {"content": "chunk1"}\n\n',
        'data: {"content": "chunk2"}\n\n',
    ]
    assert events[-1] == "data: [DONE]\n\n"
    mock_stream_advisor.assert_called_once_with(
        "【关联周期 ID: 7】\n问题",
        farm_id=farm.id,
        db=db,
        conversation_id=88,
        session_id="sess-stream",
        request_id="req-stream-2",
        user_id=user.id,
        call_type="stream_chat",
    )
