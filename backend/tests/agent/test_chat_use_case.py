"""Agent Application 聊天用例测试。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.application import (
    chat_use_case,
    stream_chat_persistence,
    stream_chat_use_case,
)
from app.agent.application.chat_use_case import chat
from app.agent.application.stream_chat_use_case import stream_chat_events
from app.agent.application.session_summary import (
    run_session_summary_task,
    schedule_session_summary,
)
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
        session_id=None,
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
        session_id=None,
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
    recorder = MagicMock()
    started_turn = MagicMock()
    recorder.start_turn.return_value = started_turn

    with (
        patch(
            "app.agent.application.chat_use_case.get_or_create_conversation",
            return_value=conversation,
        ) as mock_get_conversation,
        patch(
            "app.agent.application.chat_use_case.SessionFlywheelRecorder",
            return_value=recorder,
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
        patch(
            "app.agent.application.chat_use_case.schedule_session_summary",
        ) as mock_schedule_summary,
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
    recorder.start_turn.assert_called_once_with(
        db,
        farm_id=farm.id,
        user_id=farm.user_id,
        session_id="sess-123",
        conversation_id=42,
        request_id="req-1",
        user_message="你好",
    )
    recorder.finish_turn.assert_called_once()
    mock_schedule_summary.assert_called_once_with(
        conversation_id=42,
        farm_id=farm.id,
        session_id="sess-123",
        memory_service_provider=chat_use_case.get_memory_service,
    )
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
        patch("app.agent.application.chat_use_case.SessionFlywheelRecorder"),
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
        patch("app.agent.application.chat_use_case.schedule_session_summary"),
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
    recorder = MagicMock()

    with (
        patch(
            "app.agent.application.chat_use_case.SessionFlywheelRecorder",
            return_value=recorder,
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
        mock_advisor.return_value = "回复"

        result = await chat(
            db,
            ChatRequest(message="问题"),
            farm,
            request_id="req-1",
        )

    assert result.reply == "回复"
    recorder.start_turn.assert_not_called()
    recorder.finish_turn.assert_not_called()


async def test_chat_pending_confirm_saves_to_conversation():
    """pending action 确认路径保存助手回复到会话。"""
    db = MagicMock()
    farm = _mock_farm()
    conversation = MagicMock()
    conversation.id = 10
    recorder = MagicMock()
    started_turn = MagicMock()
    recorder.start_turn.return_value = started_turn

    with (
        patch(
            "app.agent.application.chat_use_case.get_or_create_conversation",
            return_value=conversation,
        ),
        patch(
            "app.agent.application.chat_use_case.SessionFlywheelRecorder",
            return_value=recorder,
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
        patch("app.agent.application.chat_use_case.schedule_session_summary"),
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
    recorder.start_turn.assert_called_once()
    recorder.finish_turn.assert_called_once()


async def test_stream_chat_handles_pending_without_legacy_service_or_advisor():
    """流式 pending 已处理时由 Application 收尾，不委托旧 service 或 advisor。"""
    db = MagicMock()
    user = _mock_user()
    farm = _mock_farm()

    with (
        patch(
            "app.agent.application.stream_chat_use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.agent.application.stream_chat_use_case.stream_advisor",
        ) as mock_stream_advisor,
        patch(
            "app.agent.application.stream_chat_use_case._flush_trace_queue",
            new_callable=AsyncMock,
        ) as mock_flush,
        patch(
            "app.agent.application.stream_chat_use_case._get_skill_names",
            return_value=[],
        ) as mock_get_skills,
        patch(
            "app.agent.application.stream_chat_use_case._save_stream_reply",
            return_value=None,
        ) as mock_save_reply,
        patch(
            "app.agent.application.stream_chat_use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ) as mock_observe,
        patch(
            "app.agent.application.stream_chat_use_case.build_pending_action_response",
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
    mock_pending.assert_awaited_once_with(
        farm_id=farm.id,
        message="确认",
        session_id=None,
    )
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


async def test_get_skill_names_falls_back_to_fresh_session(db_session, monkeypatch):
    """trace flush 使用独立 session 写入时，读取 skills 不受当前事务快照影响。"""
    from app.agent.application import stream_chat_use_case
    from app.models.trace import TraceRecord

    db_session.add(
        TraceRecord(
            request_id="req-fresh-trace",
            farm_id=1,
            node_type="skill_call",
            node_name="get_weather_forecast",
            status="success",
        )
    )
    db_session.commit()
    empty_current_db = MagicMock()
    empty_current_db.query.return_value.filter.return_value.filter.return_value.distinct.return_value.all.return_value = []
    monkeypatch.setattr(
        stream_chat_persistence,
        "SessionLocal",
        lambda: db_session,
        raising=False,
    )

    assert stream_chat_use_case._get_skill_names(
        empty_current_db, "req-fresh-trace"
    ) == ["get_weather_forecast"]


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
            "app.agent.application.stream_chat_use_case.get_or_create_conversation",
            return_value=conversation,
        ),
        patch("app.agent.application.stream_chat_use_case.SessionFlywheelRecorder"),
        patch(
            "app.agent.application.stream_chat_use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.agent.application.stream_chat_use_case.stream_advisor",
            side_effect=_fake_stream,
        ) as mock_stream_advisor,
        patch(
            "app.agent.application.stream_chat_use_case._flush_trace_queue",
            new_callable=AsyncMock,
        ),
        patch(
            "app.agent.application.stream_chat_use_case._get_skill_names",
            return_value=[],
        ),
        patch(
            "app.agent.application.stream_chat_use_case._save_stream_reply",
            return_value=None,
        ),
        patch(
            "app.agent.application.stream_chat_use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ),
        patch(
            "app.agent.application.stream_chat_use_case.build_pending_action_response",
            return_value=None,
        ),
        patch("app.agent.application.stream_chat_use_case.schedule_session_summary"),
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


async def test_save_stream_reply_filters_conversation_by_farm_id(monkeypatch):
    """流式回复落库时必须按当前 farm 限定 session_id。"""
    from app.agent.application.stream_chat_use_case import _save_stream_reply

    db = MagicMock()
    user = _mock_user()
    farm = _mock_farm()
    query = db.query.return_value
    query.filter.return_value.first.return_value = None
    created = []

    class SyncRepo:
        def create(self, row):
            created.append(row)
            return row

    monkeypatch.setattr(
        stream_chat_persistence,
        "get_agent_record_repository",
        lambda _db: SyncRepo(),
    )

    await _save_stream_reply(
        db,
        ChatRequest(message="问题", session_id="shared-session"),
        user,
        farm,
        "回复",
        [],
    )

    filter_sql = [str(expr) for expr in query.filter.call_args.args]
    assert "conversations.session_id" in filter_sql[0]
    assert "conversations.farm_id" in filter_sql[1]
    assert created[0].conversation_id is None


async def test_save_stream_reply_awaits_async_agent_record_repository(monkeypatch):
    """流式回复在 async 链路中直接 await AgentRecord 文档仓储。"""
    from app.agent.application.stream_chat_use_case import _save_stream_reply

    db = MagicMock()
    user = _mock_user()
    farm = _mock_farm()
    db.query.return_value.filter.return_value.first.return_value = None
    created = []

    class AsyncRepo:
        async def create(self, row):
            created.append(row)
            return row

    monkeypatch.setattr(
        stream_chat_persistence,
        "get_agent_record_repository",
        lambda _db: AsyncRepo(),
    )

    await _save_stream_reply(
        db,
        ChatRequest(message="问题", session_id="shared-session"),
        user,
        farm,
        "回复",
        [],
    )

    assert created[0].content == "回复"
    assert created[0].conversation_id is None


async def test_chat_records_turn_and_event_metadata(db_session, monkeypatch):
    from app.models.agent_turn import AgentTurn
    from app.models.conversation import ConversationMessage
    from app.models.farm import Farm
    from app.schemas.agent import ChatRequest

    farm = db_session.query(Farm).filter_by(id=1).one()
    farm.user_id = "user-1"
    db_session.commit()

    async def fake_invoke_advisor(*_args, **_kwargs):
        return "当前有水稻"

    monkeypatch.setattr(chat_use_case, "invoke_advisor", fake_invoke_advisor)
    monkeypatch.setattr(
        chat_use_case, "schedule_session_summary", lambda **_kwargs: None
    )

    response = await chat_use_case.chat(
        db_session,
        ChatRequest(message="我家有哪些作物栽种", session_id="sess-chat"),
        farm,
        request_id="abcd1234",
    )

    assert response.reply == "当前有水稻"
    turn = db_session.query(AgentTurn).filter_by(session_id="sess-chat").one()
    messages = (
        db_session.query(ConversationMessage)
        .filter(ConversationMessage.turn_id == turn.id)
        .order_by(ConversationMessage.id.asc())
        .all()
    )
    assert [message.role for message in messages] == ["user", "assistant"]
    assert turn.input_preview == "我家有哪些作物栽种"
    assert turn.reply_preview == "当前有水稻"


async def test_stream_chat_records_turn_after_completion(db_session, monkeypatch):
    from app.models.agent_turn import AgentTurn
    from app.models.farm import Farm
    from app.models.user import User
    from app.schemas.agent import ChatRequest

    user = User(
        id="stream-user-1",
        phone="18800000001",
        password_hash="h",
        nickname="流式用户",
        role="user",
        status="active",
    )
    farm = db_session.query(Farm).filter_by(id=1).one()
    farm.user_id = "stream-user-1"
    db_session.add(user)
    db_session.commit()

    async def fake_stream_advisor(*_args, **_kwargs):
        yield "当前"
        yield "有水稻"

    async def fake_flush_trace_queue():
        return None

    monkeypatch.setattr(stream_chat_use_case, "stream_advisor", fake_stream_advisor)
    monkeypatch.setattr(
        stream_chat_use_case, "_flush_trace_queue", fake_flush_trace_queue
    )
    monkeypatch.setattr(
        stream_chat_use_case, "_get_skill_names", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        stream_chat_use_case, "schedule_session_summary", lambda **_kwargs: None
    )

    chunks = []
    async for chunk in stream_chat_use_case.stream_chat_events(
        db_session,
        ChatRequest(message="我家有哪些作物栽种", session_id="sess-stream"),
        user,
        farm,
        request_id="abcd1234",
    ):
        chunks.append(chunk)

    assert any("当前" in chunk for chunk in chunks)
    turn = db_session.query(AgentTurn).filter_by(session_id="sess-stream").one()
    assert turn.reply_preview == "当前有水稻"


async def test_stream_chat_completion_schedules_session_summary():
    """流式回复落库后触发会话摘要后台任务。"""
    db = MagicMock()
    user = _mock_user()
    farm = _mock_farm()
    conversation = MagicMock()
    conversation.id = 88
    recorder = MagicMock()
    recorder.start_turn.return_value = MagicMock()

    async def _fake_stream(*args, **kwargs):
        yield "当前"
        yield "有水稻"

    with (
        patch(
            "app.agent.application.stream_chat_use_case.get_or_create_conversation",
            return_value=conversation,
        ),
        patch(
            "app.agent.application.stream_chat_use_case.SessionFlywheelRecorder",
            return_value=recorder,
        ),
        patch(
            "app.agent.application.stream_chat_use_case.handle_pending_action",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "app.agent.application.stream_chat_use_case.stream_advisor",
            side_effect=_fake_stream,
        ),
        patch(
            "app.agent.application.stream_chat_use_case._flush_trace_queue",
            new_callable=AsyncMock,
        ),
        patch(
            "app.agent.application.stream_chat_use_case._get_skill_names",
            return_value=[],
        ),
        patch(
            "app.agent.application.stream_chat_use_case._save_stream_reply",
            return_value=conversation,
        ),
        patch(
            "app.agent.application.stream_chat_use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ),
        patch(
            "app.agent.application.stream_chat_use_case.schedule_session_summary",
        ) as mock_schedule_summary,
    ):
        from app.agent.executor.models import PendingActionDecision

        mock_pending.return_value = PendingActionDecision.unhandled()

        events = [
            event
            async for event in stream_chat_events(
                db,
                ChatRequest(message="问题", session_id="sess-stream"),
                user,
                farm,
                request_id="req-stream-3",
            )
        ]

    assert events[-1] == "data: [DONE]\n\n"
    recorder.finish_turn.assert_called_once()
    mock_schedule_summary.assert_called_once_with(
        conversation_id=88,
        farm_id=farm.id,
        session_id="sess-stream",
        memory_service_provider=stream_chat_use_case.get_memory_service,
    )


async def test_run_session_summary_task_uses_fresh_db_and_calls_maybe_summarize():
    """后台任务使用独立 DB session 调用 maybe_summarize。"""
    fresh_db = MagicMock()
    memory_service = MagicMock()
    memory_service.maybe_summarize = AsyncMock()

    await run_session_summary_task(
        conversation_id=42,
        farm_id=1,
        session_id="sess-123",
        memory_service_provider=lambda: memory_service,
        session_factory=lambda: fresh_db,
        timeout_seconds=1,
    )

    memory_service.maybe_summarize.assert_awaited_once_with(
        fresh_db,
        42,
        1,
        "sess-123",
        messages=None,
    )
    fresh_db.close.assert_called_once()


async def test_schedule_session_summary_creates_task_that_calls_maybe_summarize():
    """调度函数通过 create_task 创建任务，任务最终调用 maybe_summarize。"""
    created = []
    fresh_db = MagicMock()
    memory_service = MagicMock()
    memory_service.maybe_summarize = AsyncMock()

    def _capture_task(coro):
        created.append(coro)
        return "task-1"

    task = schedule_session_summary(
        conversation_id=42,
        farm_id=1,
        session_id="sess-123",
        memory_service=memory_service,
        session_factory=lambda: fresh_db,
        create_task=_capture_task,
        timeout_seconds=1,
    )

    assert task == "task-1"
    assert len(created) == 1
    await created[0]
    memory_service.maybe_summarize.assert_awaited_once_with(
        fresh_db,
        42,
        1,
        "sess-123",
        messages=None,
    )
    fresh_db.close.assert_called_once()


async def test_schedule_session_summary_closes_coroutine_when_create_task_fails():
    """调度失败时关闭 coroutine，避免未 await 警告并不影响调用方。"""

    def _raise_create_task(_coro):
        raise RuntimeError("event loop closed")

    result = schedule_session_summary(
        conversation_id=42,
        farm_id=1,
        session_id="sess-123",
        memory_service=MagicMock(),
        create_task=_raise_create_task,
        timeout_seconds=1,
    )

    assert result is None


async def test_run_session_summary_task_closes_db_when_maybe_summarize_errors():
    """摘要任务异常时不向外抛出并关闭 DB session。"""
    fresh_db = MagicMock()
    memory_service = MagicMock()
    memory_service.maybe_summarize = AsyncMock(side_effect=RuntimeError("boom"))

    await run_session_summary_task(
        conversation_id=42,
        farm_id=1,
        session_id="sess-123",
        memory_service=memory_service,
        session_factory=lambda: fresh_db,
        timeout_seconds=1,
    )

    fresh_db.close.assert_called_once()


async def test_run_session_summary_task_closes_db_when_timeout():
    """摘要任务超时时不向外抛出并关闭 DB session。"""
    fresh_db = MagicMock()
    memory_service = MagicMock()

    async def _never_finish(*args, **kwargs):
        await asyncio.sleep(1)

    memory_service.maybe_summarize = AsyncMock(side_effect=_never_finish)

    await run_session_summary_task(
        conversation_id=42,
        farm_id=1,
        session_id="sess-123",
        memory_service=memory_service,
        session_factory=lambda: fresh_db,
        timeout_seconds=0.01,
    )

    fresh_db.close.assert_called_once()
