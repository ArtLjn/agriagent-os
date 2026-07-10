"""查询能力菜单状态测试。"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.application.chat_use_case import chat
from app.agent.application.query_capability_menu import resolve_query_capability_menu
from app.agent.application.stream_chat_use_case import stream_chat_events
from app.memory.models import TemporaryTaskState
from app.memory.service import InMemoryMemoryService
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


class _SyncAgentRecordRepo:
    def create(self, row):
        return row


async def test_query_menu_request_stores_state_without_fixed_reply():
    service = InMemoryMemoryService()

    result = await resolve_query_capability_menu(
        memory_service=service,
        user_id="user-1",
        farm_id=1,
        session_id="sess-1",
        message="查数据，给我几个选项",
    )

    assert result.reply is None
    assert result.rewritten_message is None
    context = await service.build_context("user-1", 1, "sess-1")
    assert context.temporary_task_state is not None
    assert context.temporary_task_state.task_id == "query_capability_menu"


async def test_query_menu_number_without_pending_state_is_not_rewritten():
    service = InMemoryMemoryService()

    result = await resolve_query_capability_menu(
        memory_service=service,
        user_id="user-1",
        farm_id=1,
        session_id="sess-1",
        message="2",
    )

    assert result.reply is None
    assert result.rewritten_message is None


async def test_query_menu_number_with_pending_state_rewrites_and_clears_state():
    service = InMemoryMemoryService()
    await resolve_query_capability_menu(
        memory_service=service,
        user_id="user-1",
        farm_id=1,
        session_id="sess-1",
        message="我可以查啥",
    )

    result = await resolve_query_capability_menu(
        memory_service=service,
        user_id="user-1",
        farm_id=1,
        session_id="sess-1",
        message="2",
    )

    assert result.rewritten_message is not None
    assert "第 2 个选项" in result.rewritten_message
    assert "结合本会话上文理解" in result.rewritten_message
    context = await service.build_context("user-1", 1, "sess-1")
    assert context.temporary_task_state is None


async def test_chat_query_capability_menu_uses_advisor_and_stores_selection_state():
    db = MagicMock()
    farm = _mock_farm()
    memory_service = InMemoryMemoryService()
    conversation = MagicMock()
    conversation.id = 11
    recorder = MagicMock()
    recorder.start_turn.return_value = MagicMock()

    with (
        patch(
            "app.agent.application.chat_use_case.get_or_create_conversation",
            return_value=conversation,
        ),
        patch(
            "app.agent.application.chat_use_case.SessionFlywheelRecorder",
            return_value=recorder,
        ),
        patch("app.agent.application.chat_use_case.schedule_session_summary"),
        patch(
            "app.agent.application.chat_use_case.get_agent_record_repository",
            return_value=_SyncAgentRecordRepo(),
        ),
        patch(
            "app.agent.application.chat_use_case.get_memory_service",
            return_value=memory_service,
        ),
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
        mock_advisor.return_value = "你可以选择：\n1. 天气\n2. 茬口"

        result = await chat(
            db,
            ChatRequest(
                message="你不是可以查数据吗 给我几个选项我选择查啥",
                session_id="sess-menu",
            ),
            farm,
            request_id="req-menu",
        )

    assert result.reply == "你可以选择：\n1. 天气\n2. 茬口"
    mock_advisor.assert_awaited_once_with(
        "你不是可以查数据吗 给我几个选项我选择查啥",
        farm_id=farm.id,
        db=db,
        conversation_id=11,
        session_id="sess-menu",
        request_id="req-menu",
        user_id=farm.user_id,
    )
    context = await memory_service.build_context("user-1", 1, "sess-menu")
    assert context.temporary_task_state is not None
    assert context.temporary_task_state.task_id == "query_capability_menu"
    assert context.temporary_task_state.status == "awaiting_selection"


async def test_chat_query_capability_menu_number_selection_returns_to_model():
    db = MagicMock()
    farm = _mock_farm()
    memory_service = InMemoryMemoryService()
    conversation = MagicMock()
    conversation.id = 11
    recorder = MagicMock()
    recorder.start_turn.return_value = MagicMock()
    await memory_service.short_term.set_temporary_task_state(
        user_id="user-1",
        farm_id=1,
        session_id="sess-menu",
        task_state=TemporaryTaskState(
            task_id="query_capability_menu",
            status="awaiting_selection",
            data={"source": "model_generated_query_options"},
        ),
    )

    with (
        patch(
            "app.agent.application.chat_use_case.get_or_create_conversation",
            return_value=conversation,
        ),
        patch(
            "app.agent.application.chat_use_case.SessionFlywheelRecorder",
            return_value=recorder,
        ),
        patch("app.agent.application.chat_use_case.schedule_session_summary"),
        patch(
            "app.agent.application.chat_use_case.get_agent_record_repository",
            return_value=_SyncAgentRecordRepo(),
        ),
        patch(
            "app.agent.application.chat_use_case.get_memory_service",
            return_value=memory_service,
        ),
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
        mock_advisor.return_value = "当前茬口：夏季水稻、夏季大豆"

        result = await chat(
            db,
            ChatRequest(message="2", session_id="sess-menu"),
            farm,
            request_id="req-menu-select",
        )

    assert result.reply == "当前茬口：夏季水稻、夏季大豆"
    advisor_message = mock_advisor.await_args.args[0]
    assert "第 2 个选项" in advisor_message
    assert "结合本会话上文理解" in advisor_message
    context = await memory_service.build_context("user-1", 1, "sess-menu")
    assert context.temporary_task_state is None


async def test_stream_query_capability_menu_uses_stream_advisor():
    db = MagicMock()
    user = _mock_user()
    farm = _mock_farm()
    memory_service = InMemoryMemoryService()

    with (
        patch(
            "app.agent.application.stream_chat_use_case.get_memory_service",
            return_value=memory_service,
        ),
        patch(
            "app.agent.application.stream_chat_use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.agent.application.stream_chat_use_case.stream_advisor",
            side_effect=_fake_stream_options,
        ) as mock_stream,
        patch(
            "app.agent.application.stream_chat_use_case._flush_trace_queue",
            new_callable=AsyncMock,
        ),
        patch(
            "app.agent.application.stream_chat_use_case._get_skill_names",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.agent.application.stream_chat_use_case._schedule_stream_background_finalization",
        ),
    ):
        from app.agent.executor.models import PendingActionDecision

        mock_pending.return_value = PendingActionDecision.unhandled()
        events = [
            event
            async for event in stream_chat_events(
                db,
                ChatRequest(message="查数据，给我几个选项", session_id=None),
                user,
                farm,
                request_id="req-stream-menu",
            )
        ]

    first_payload = json.loads(events[0].removeprefix("data: ").strip())
    assert "2. 茬口" in first_payload["content"]
    assert events[-1] == "data: [DONE]\n\n"
    mock_stream.assert_called_once()


async def _fake_stream_options(*_args, **_kwargs):
    yield "1. 天气\n2. 茬口"
