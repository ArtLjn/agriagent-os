"""Memory Service 骨架行为测试。"""

from datetime import datetime, timedelta

from app.shared.compatibility import UTC
from app.memory.models import MemoryMessage, PendingActionSnapshot, TemporaryTaskState
from app.memory.schemas import MemoryObservationEvent, MemorySearchQuery
from app.memory.service import InMemoryMemoryService


async def test_build_context_returns_empty_context_when_memory_is_empty():
    service = InMemoryMemoryService()

    context = await service.build_context(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
    )

    assert context.user_id == "user-1"
    assert context.farm_id == 1
    assert context.session_id == "session-1"
    assert context.recent_messages == []
    assert context.session_summary is None
    assert context.pending_action is None
    assert context.temporary_task_state is None
    assert context.long_term.user_preferences == []
    assert context.long_term.farm_profiles == []
    assert context.long_term.key_facts == []
    assert context.long_term.cycle_summaries == []
    assert context.long_term.ledger_summaries == []
    assert context.long_term.is_empty()
    assert context.retrieved_hits == []


async def test_short_term_memory_keeps_recent_message_window_and_session_state():
    service = InMemoryMemoryService(recent_message_limit=2)
    await service.short_term.add_message(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        message=MemoryMessage(role="user", content="第一句"),
    )
    await service.short_term.add_message(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        message=MemoryMessage(role="assistant", content="第二句"),
    )
    await service.short_term.add_message(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        message=MemoryMessage(role="user", content="第三句"),
    )
    await service.short_term.set_session_summary(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        summary="会话摘要占位",
    )
    await service.short_term.set_pending_action(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        pending_action=PendingActionSnapshot(action_id="act-1", name="create_cost"),
    )
    await service.short_term.set_temporary_task_state(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        task_state=TemporaryTaskState(task_id="task-1", status="pending"),
    )

    context = await service.build_context("user-1", 1, "session-1")

    assert [message.content for message in context.recent_messages] == [
        "第二句",
        "第三句",
    ]
    assert context.session_summary == "会话摘要占位"
    assert context.pending_action is not None
    assert context.pending_action.action_id == "act-1"
    assert context.temporary_task_state is not None
    assert context.temporary_task_state.status == "pending"


async def test_build_context_ignores_expired_pending_action_snapshot():
    service = InMemoryMemoryService()
    await service.short_term.set_pending_action(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        pending_action=PendingActionSnapshot(
            action_id="act-expired",
            name="create_cost",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        ),
    )

    context = await service.build_context("user-1", 1, "session-1")

    assert context.pending_action is None


async def test_observe_interaction_records_event_and_updates_short_term_memory():
    service = InMemoryMemoryService()
    event = MemoryObservationEvent(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        user_input="今天浇水了吗",
        assistant_reply="今天上午已经记录过浇水。",
        skills_called=["search_logs"],
        metadata={"trace_id": "trace-1"},
    )

    stored_event = await service.observe_interaction(event)
    context = await service.build_context("user-1", 1, "session-1")

    assert stored_event.event_id
    assert service.observation_events == [stored_event]
    assert [message.role for message in context.recent_messages] == [
        "user",
        "assistant",
    ]
    assert context.recent_messages[0].content == "今天浇水了吗"
    assert context.recent_messages[1].metadata["skills_called"] == ["search_logs"]


async def test_observe_interaction_records_memory_trace_event():
    records = []
    service = InMemoryMemoryService()
    event = MemoryObservationEvent(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        user_input="今天浇水了吗",
        assistant_reply="今天上午已经记录过浇水。",
        skills_called=["search_logs"],
    )

    await service.observe_interaction(
        event,
        trace_collector=lambda **kwargs: records.append(kwargs),
    )

    assert records == [
        {
            "node_type": "memory_observe",
            "node_name": "interaction_observation",
            "input_data": {
                "event_id": event.event_id,
                "farm_id": 1,
                "session_id": "session-1",
                "skills_called": ["search_logs"],
            },
            "output_data": {"stored": True, "recent_message_count": 2},
        }
    ]


async def test_search_returns_empty_results_without_retrieval_backend():
    service = InMemoryMemoryService()

    results = await service.search(
        MemorySearchQuery(query="浇水记录", user_id="user-1", farm_id=1, limit=5)
    )

    assert results == []


async def test_memory_observe_build_and_search_continue_without_rag_backend():
    service = InMemoryMemoryService()

    await service.observe_chat_completion(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        user_input="明天提醒我看温室湿度",
        assistant_reply="已记录这次对话。",
        skills_called=["schedule_reminder"],
    )

    context = await service.build_context(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
    )
    results = await service.search(
        MemorySearchQuery(
            query="温室湿度提醒",
            user_id="user-1",
            farm_id=1,
            session_id="session-1",
        )
    )

    assert [message.content for message in context.recent_messages] == [
        "明天提醒我看温室湿度",
        "已记录这次对话。",
    ]
    assert context.long_term.user_preferences == []
    assert context.long_term.farm_profiles == []
    assert context.long_term.key_facts == []
    assert context.long_term.cycle_summaries == []
    assert context.long_term.ledger_summaries == []
    assert context.long_term.is_empty()
    assert results == []
