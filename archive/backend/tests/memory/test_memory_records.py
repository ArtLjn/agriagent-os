"""显式长期记忆最小闭环测试。"""

from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from app.memory.long_term.store import (
    MemoryRecordStatus,
    MemoryRecordStore,
    SQLLongTermMemoryStore,
)
from app.memory.explicit import ExplicitMemoryTurn, record_explicit_memory_after_turn


def test_memory_record_store_confirms_and_isolates_by_farm_user(db_session) -> None:
    store = MemoryRecordStore(db_session)

    record = store.create_confirmed(
        farm_id=1,
        user_id="test-user-001",
        memory_type="preference",
        content="以后面积单位用亩",
    )
    other_user_context = store.build_context(farm_id=1, user_id="other-user")
    other_farm_context = store.build_context(farm_id=2, user_id="test-user-001")
    same_context = store.build_context(farm_id=1, user_id="test-user-001")

    assert record.status == MemoryRecordStatus.CONFIRMED.value
    assert record.source == "user_explicit"
    assert other_user_context.is_empty()
    assert other_farm_context.is_empty()
    assert same_context.user_preferences[0].value == "以后面积单位用亩"


@pytest.mark.asyncio
async def test_explicit_memory_turn_writes_confirmed_memory(db_session) -> None:
    for user_input in ("记住我以后用亩", "请你记住我以后默认用亩"):
        await record_explicit_memory_after_turn(
            db_session,
            ExplicitMemoryTurn(
                farm_id=1,
                user_id="test-user-001",
                session_id="session-memory",
                user_input=user_input,
                assistant_reply="好的，以后默认按亩来处理面积。",
            ),
        )

    context = MemoryRecordStore(db_session).build_context(
        farm_id=1,
        user_id="test-user-001",
    )

    assert [item.value for item in context.user_preferences] == [
        "以后默认用亩",
        "以后用亩",
    ]


@pytest.mark.asyncio
async def test_explicit_memory_turn_skips_non_explicit_and_pending(db_session) -> None:
    turns = [
        ExplicitMemoryTurn(
            farm_id=1,
            user_id="test-user-001",
            session_id="session-memory",
            user_input="你好",
            assistant_reply="你好，有什么可以帮你？",
        ),
        ExplicitMemoryTurn(
            farm_id=1,
            user_id="test-user-001",
            session_id="session-memory",
            user_input="记一笔肥料200元",
            assistant_reply="请确认这条记账操作。",
            pending_action=SimpleNamespace(action_id="act-1"),
        ),
        ExplicitMemoryTurn(
            farm_id=1,
            user_id="test-user-001",
            session_id="session-memory",
            user_input="确认",
            assistant_reply="已执行：已记账",
            pending_decision_handled=True,
        ),
        ExplicitMemoryTurn(
            farm_id=1,
            user_id="test-user-001",
            session_id="session-memory",
            user_input="不要记这个",
            assistant_reply="好的，不记录。",
        ),
        ExplicitMemoryTurn(
            farm_id=1,
            user_id="test-user-001",
            session_id="session-memory",
            user_input="记住了吗",
            assistant_reply="还没有保存任何长期记忆。",
        ),
    ]

    for turn in turns:
        await record_explicit_memory_after_turn(db_session, turn)

    assert (
        MemoryRecordStore(db_session)
        .build_context(
            farm_id=1,
            user_id="test-user-001",
        )
        .is_empty()
    )


def test_memory_record_archive_removes_context_injection(db_session) -> None:
    store = MemoryRecordStore(db_session)
    record = store.create_confirmed(
        farm_id=1,
        user_id="test-user-001",
        memory_type="alias",
        content="老王就是农资店老板",
    )

    archived = store.archive(
        farm_id=1,
        user_id="test-user-001",
        memory_id=record.memory_id,
    )

    assert archived is not None
    assert archived.status == MemoryRecordStatus.ARCHIVED.value
    assert store.build_context(farm_id=1, user_id="test-user-001").is_empty()


@pytest.mark.asyncio
async def test_sql_long_term_store_recovers_from_fresh_db_session(db_session) -> None:
    MemoryRecordStore(db_session).create_confirmed(
        farm_id=1,
        user_id="test-user-001",
        memory_type="preference",
        content="以后默认按一号棚算",
    )
    fresh_session_factory = sessionmaker(bind=db_session.get_bind())
    store = SQLLongTermMemoryStore(session_factory=fresh_session_factory)

    context = await store.build_context(
        farm_id=1,
        user_id="test-user-001",
    )

    assert [item.value for item in context.user_preferences] == ["以后默认按一号棚算"]
