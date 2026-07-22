"""Task Context 持久化 store 测试。"""

from datetime import datetime, timedelta

from app.context.task_state_store import AgentTaskStateStore, TaskStateStatus


def test_task_state_store_upserts_and_gets_latest_active_task(db_session) -> None:
    store = AgentTaskStateStore(db_session)

    first = store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
        task_type="plan_draft",
        goal="补全黄瓜施肥计划",
        entities={"crop": "黄瓜"},
        observations=["用户已经提供作物"],
        missing_information=["施肥日期"],
        next_action="询问施肥日期",
    )
    second = store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
        task_type="plan_draft",
        goal="补全番茄打药计划",
        entities={"crop": "番茄"},
        observations=["用户已经提供病害症状"],
        missing_information=["用药偏好"],
        next_action="询问是否优先低毒药剂",
    )

    active = store.get_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
    )

    assert first.task_id == second.task_id
    assert active is not None
    assert active.task_id == second.task_id
    assert active.goal == "补全番茄打药计划"
    assert active.entities_json == {"crop": "番茄"}
    assert active.missing_information_json == ["用药偏好"]
    assert active.next_action == "询问是否优先低毒药剂"
    assert active.status == TaskStateStatus.ACTIVE.value


def test_task_state_store_isolates_by_session(db_session) -> None:
    store = AgentTaskStateStore(db_session)
    store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
        task_type="plan_draft",
        goal="会话一任务",
    )
    store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="session-2",
        task_type="plan_draft",
        goal="会话二任务",
    )

    active = store.get_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
    )

    assert active is not None
    assert active.goal == "会话一任务"


def test_task_state_store_ignores_expired_tasks(db_session) -> None:
    store = AgentTaskStateStore(db_session)
    store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
        task_type="plan_draft",
        goal="已经过期的任务",
        expires_at=datetime.now() - timedelta(minutes=1),
    )

    active = store.get_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
    )

    assert active is None


def test_task_state_store_completed_task_is_not_returned(db_session) -> None:
    store = AgentTaskStateStore(db_session)
    task = store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
        task_type="plan_draft",
        goal="待完成任务",
    )

    store.mark_completed(
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
        task_id=task.task_id,
    )

    assert (
        store.get_active_task(
            farm_id=1,
            user_id="test-user-001",
            session_id="session-1",
        )
        is None
    )
