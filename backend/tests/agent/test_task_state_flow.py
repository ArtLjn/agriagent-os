"""TaskState 写入闭环测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from app.application.chat.task_state_updater import (
    TaskStateTurn,
    update_task_state_after_turn,
)
from app.context.selectors.task_state import TaskStateSelector
from app.context.task_state_store import AgentTaskStateStore, TaskStateStatus
from app.domains.conversation.agent_schemas import ChatRequest


pytestmark = pytest.mark.asyncio


def _turn(
    *,
    user_input: str,
    assistant_reply: str,
    session_id: str = "sess-task",
    pending_action: object | None = None,
    pending_plan: object | None = None,
    pending_decision_handled: bool = False,
) -> TaskStateTurn:
    return TaskStateTurn(
        farm_id=1,
        user_id="test-user-001",
        session_id=session_id,
        user_input=user_input,
        assistant_reply=assistant_reply,
        pending_action=pending_action,
        pending_plan=pending_plan,
        pending_decision_handled=pending_decision_handled,
    )


async def test_task_state_updater_writes_waiting_task_when_reply_requests_info(
    db_session,
) -> None:
    await update_task_state_after_turn(
        db_session,
        _turn(
            user_input="帮我给番茄做一个补光计划",
            assistant_reply=(
                "可以，我先帮你梳理补光计划。还需要补充：补光灯功率、棚室面积。"
            ),
        ),
    )

    task = AgentTaskStateStore(db_session).get_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-task",
    )

    assert task is not None
    assert task.status == TaskStateStatus.WAITING_USER.value
    assert task.task_type == "plan_draft"
    assert task.goal == "帮我给番茄做一个补光计划"
    assert task.entities_json["crop"] == "番茄"
    assert task.missing_information_json == ["补光灯功率", "棚室面积"]
    assert task.next_action == "等待用户补充：补光灯功率"


async def test_task_state_updater_updates_same_task_after_user_supplies_missing_info(
    db_session,
) -> None:
    store = AgentTaskStateStore(db_session)
    await update_task_state_after_turn(
        db_session,
        _turn(
            user_input="帮我给番茄做一个补光计划",
            assistant_reply="还需要补充：补光灯功率、棚室面积。",
        ),
    )
    first = store.get_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-task",
    )

    await update_task_state_after_turn(
        db_session,
        _turn(
            user_input="补光灯是400瓦，棚室面积大概2亩",
            assistant_reply="收到，我会按400瓦补光灯和2亩棚室面积继续测算。",
        ),
    )
    updated = store.get_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-task",
    )

    assert first is not None
    assert updated is not None
    assert updated.task_id == first.task_id
    assert updated.status == TaskStateStatus.ACTIVE.value
    assert updated.missing_information_json == []
    assert "用户补充：补光灯是400瓦，棚室面积大概2亩" in updated.observations_json
    assert updated.next_action == "继续处理当前任务"


async def test_task_state_updater_keeps_missing_when_user_reply_has_no_missing_item(
    db_session,
) -> None:
    store = AgentTaskStateStore(db_session)
    task = store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-task",
        task_type="plan_draft",
        goal="帮我给番茄做一个补光计划",
        entities={"crop": "番茄"},
        missing_information=["补光灯功率", "棚室面积"],
        next_action="等待用户补充：补光灯功率",
        status=TaskStateStatus.WAITING_USER,
    )

    await update_task_state_after_turn(
        db_session,
        _turn(
            user_input="今天阴天，番茄长势还可以",
            assistant_reply="收到，我继续帮你看。",
        ),
    )
    db_session.refresh(task)

    assert task.status == TaskStateStatus.WAITING_USER.value
    assert task.missing_information_json == ["补光灯功率", "棚室面积"]
    assert task.next_action == "等待用户补充：补光灯功率"


async def test_task_state_updater_completion_and_cancel_stop_selector_injection(
    db_session,
) -> None:
    store = AgentTaskStateStore(db_session)
    created = store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-task",
        task_type="diagnosis_followup",
        goal="诊断黄瓜叶斑",
        status=TaskStateStatus.WAITING_USER,
    )

    await update_task_state_after_turn(
        db_session,
        _turn(
            user_input="症状是叶背有霉层",
            assistant_reply="诊断建议已经整理完成，可以按低毒杀菌剂方案执行。",
        ),
    )
    completed = db_session.get(type(created), created.id)
    assert completed.status == TaskStateStatus.COMPLETED.value
    assert (
        TaskStateSelector().select(
            db=db_session,
            farm_id=1,
            user_id="test-user-001",
            session_id="sess-task",
        )
        == []
    )

    cancelled = store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-task",
        task_type="plan_draft",
        goal="制定追肥计划",
        status=TaskStateStatus.WAITING_USER,
    )
    await update_task_state_after_turn(
        db_session,
        _turn(user_input="不用了，取消吧", assistant_reply="好的，已取消这个任务。"),
    )

    db_session.refresh(cancelled)
    assert cancelled.status == TaskStateStatus.CANCELLED.value
    assert (
        store.get_active_task(
            farm_id=1,
            user_id="test-user-001",
            session_id="sess-task",
        )
        is None
    )


async def test_task_state_updater_skips_greeting_accounting_and_pending(
    db_session,
) -> None:
    for turn in [
        _turn(user_input="你好", assistant_reply="你好，有什么要帮忙的？"),
        _turn(user_input="查一下今天账单", assistant_reply="今天收入200元。"),
        _turn(
            user_input="记一笔肥料200元",
            assistant_reply="请确认这条记账操作。",
            pending_action=SimpleNamespace(action_id="act-1"),
        ),
        _turn(
            user_input="确认",
            assistant_reply="已执行：已记账",
            pending_decision_handled=True,
        ),
    ]:
        await update_task_state_after_turn(db_session, turn)

    assert (
        AgentTaskStateStore(db_session).get_active_task(
            farm_id=1,
            user_id="test-user-001",
            session_id="sess-task",
        )
        is None
    )


async def test_task_state_updater_ignores_side_queries_when_task_exists(
    db_session,
) -> None:
    store = AgentTaskStateStore(db_session)
    task = store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-task",
        task_type="plan_draft",
        goal="帮我给番茄做一个补光计划",
        missing_information=["棚室面积"],
        observations=["用户已经提供：番茄"],
        next_action="等待用户补充：棚室面积",
        status=TaskStateStatus.WAITING_USER,
    )

    await update_task_state_after_turn(
        db_session,
        _turn(
            user_input="查一下今天账单",
            assistant_reply="今天收入200元。",
        ),
    )
    db_session.refresh(task)

    assert task.status == TaskStateStatus.WAITING_USER.value
    assert task.missing_information_json == ["棚室面积"]
    assert task.observations_json == ["用户已经提供：番茄"]
    assert task.next_action == "等待用户补充：棚室面积"


async def test_task_state_updater_only_cancels_on_user_cancel_intent(
    db_session,
) -> None:
    store = AgentTaskStateStore(db_session)
    task = store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-task",
        task_type="plan_draft",
        goal="帮我给番茄做一个补光计划",
        missing_information=["棚室面积"],
        status=TaskStateStatus.WAITING_USER,
    )

    await update_task_state_after_turn(
        db_session,
        _turn(
            user_input="那继续按原计划",
            assistant_reply="不用取消，我继续按原计划处理。还需要补充：棚室面积。",
        ),
    )
    db_session.refresh(task)

    assert task.status == TaskStateStatus.WAITING_USER.value
    assert task.missing_information_json == ["棚室面积"]


async def test_task_state_updater_skips_pending_plan(db_session) -> None:
    await update_task_state_after_turn(
        db_session,
        _turn(
            user_input="帮我制定番茄补光计划",
            assistant_reply="还需要补充：棚室面积。",
            pending_plan=SimpleNamespace(plan_id="plan-1"),
        ),
    )

    assert (
        AgentTaskStateStore(db_session).get_active_task(
            farm_id=1,
            user_id="test-user-001",
            session_id="sess-task",
        )
        is None
    )


async def test_task_state_recovers_from_fresh_db_session(db_session) -> None:
    await update_task_state_after_turn(
        db_session,
        _turn(
            user_input="帮我给番茄做一个补光计划",
            assistant_reply="还需要补充：棚室面积。",
        ),
    )

    fresh_session_factory = sessionmaker(bind=db_session.get_bind())
    fresh_db = fresh_session_factory()
    try:
        blocks = TaskStateSelector().select(
            db=fresh_db,
            farm_id=1,
            user_id="test-user-001",
            session_id="sess-task",
        )
    finally:
        fresh_db.close()

    assert len(blocks) == 1
    assert blocks[0].key == "active_task_state"
    assert "目标：帮我给番茄做一个补光计划" in blocks[0].content
    assert "缺失信息：棚室面积" in blocks[0].content


async def test_chat_use_case_updates_task_state_after_advisor_reply() -> None:
    from app.agent.executor.models import PendingActionDecision
    from app.application.chat import use_case

    db = MagicMock()
    farm = MagicMock(id=1, user_id="user-1")

    with (
        patch(
            "app.application.chat.use_case.handle_pending_action",
            new_callable=AsyncMock,
            return_value=PendingActionDecision.unhandled(),
        ),
        patch(
            "app.application.chat.use_case.invoke_advisor",
            new_callable=AsyncMock,
            return_value="还需要补充：棚室面积。",
        ),
        patch(
            "app.application.chat.use_case.get_or_create_conversation",
            return_value=MagicMock(id=42),
        ),
        patch("app.application.chat.use_case.SessionFlywheelRecorder"),
        patch("app.application.chat.use_case.schedule_session_summary"),
        patch(
            "app.application.chat.use_case.build_pending_action_response",
            return_value=None,
        ),
        patch(
            "app.application.chat.use_case.build_pending_plan_response",
            return_value=None,
        ),
        patch(
            "app.application.chat.use_case.update_task_state_after_turn",
            new_callable=AsyncMock,
        ) as mock_update,
        patch(
            "app.application.chat.use_case._observe_chat_completion",
            new_callable=AsyncMock,
        ),
    ):
        await use_case.chat(
            db,
            ChatRequest(message="帮我制定番茄补光计划", session_id="sess-chat"),
            farm,
            request_id="req-task-state",
        )

    mock_update.assert_awaited_once()
    turn = mock_update.await_args.args[1]
    assert turn.farm_id == 1
    assert turn.user_id == "user-1"
    assert turn.session_id == "sess-chat"
    assert turn.user_input == "帮我制定番茄补光计划"
    assert turn.assistant_reply == "还需要补充：棚室面积。"
    assert turn.pending_action is None
    assert turn.pending_plan is None
    assert turn.pending_decision_handled is False


async def test_stream_background_finalization_updates_task_state() -> None:
    from app.application.chat import stream_finalization
    from app.application.chat.stream_finalization import (
        StreamReplyPersistencePayload,
    )

    payload = StreamReplyPersistencePayload(
        cycle_id=None,
        session_id="sess-stream",
        user_id="user-1",
        farm_id=1,
        user_input="帮我制定番茄补光计划",
        full_reply="还需要补充：棚室面积。",
        skill_names=[],
        pending_action=None,
    )
    db = MagicMock()
    db.close = MagicMock()

    with (
        patch(
            "app.application.chat.stream_finalization.SessionLocal",
            return_value=db,
        ),
        patch(
            "app.application.chat.stream_finalization._save_stream_reply_payload",
            new_callable=AsyncMock,
        ),
        patch(
            "app.application.chat.stream_finalization._observe_chat_completion",
            new_callable=AsyncMock,
        ),
        patch(
            "app.application.chat.stream_finalization.update_task_state_after_turn",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        await stream_finalization.run_stream_background_finalization(
            payload,
            request_id="req-stream-task",
        )

    mock_update.assert_awaited_once()
    turn = mock_update.await_args.args[1]
    assert turn.session_id == "sess-stream"
    assert turn.user_input == "帮我制定番茄补光计划"
    assert turn.assistant_reply == "还需要补充：棚室面积。"
