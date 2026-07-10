"""Session debug export service 测试。"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base
from app.infra.pending_actions import store_pending_plan
from app.infra.agent_events import AgentEventWriter
from app.models.farm import Farm
from app.services.agent_turn_service import create_turn, mark_event_range
from app.services.conversation_service import get_or_create_conversation, save_message
from app.services.pending_plan_service import create_pending_plan
from app.services.session_debug_export_service import build_session_debug_export

pytestmark = pytest.mark.no_db


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_session_debug_export_service.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    settings.storage.conversation_messages = "mysql"
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场", user_id="user-1"))
    db.commit()
    db.close()


def test_build_session_debug_export_includes_messages_turns_pending_and_events(
    tmp_path,
):
    db = Session()
    conv = get_or_create_conversation(
        db, farm_id=1, session_id="sess-debug", user_id="user-1"
    )
    user_msg = save_message(db, conv.id, "user", "停用李一凡")
    save_message(db, conv.id, "assistant", "确认停用吗？")
    turn = create_turn(
        db,
        farm_id=1,
        session_id="sess-debug",
        conversation_id=conv.id,
        request_id="abcd1234",
        user_message_id=user_msg.id,
        input_text="停用李一凡",
    )
    writer = AgentEventWriter(base_dir=tmp_path)
    first = writer.write(
        event_type="message.user",
        farm_id=1,
        user_id="user-1",
        session_id="sess-debug",
        turn_id=turn.id,
        request_id="abcd1234",
        payload={"content": "停用李一凡"},
    )
    second = writer.write(
        event_type="pending.plan.created",
        farm_id=1,
        user_id="user-1",
        session_id="sess-debug",
        turn_id=turn.id,
        request_id="abcd1234",
        payload={"plan_id": "p1"},
    )
    mark_event_range(
        db,
        turn.id,
        event_file=first.event_file,
        seq_start=first.seq,
        seq_end=second.seq,
        write_status="success",
    )
    create_pending_plan(
        db,
        farm_id=1,
        session_id="sess-debug",
        raw_user_input="停用李一凡",
        router_decision={"selected_tools": ["manage_workers"]},
        steps=[{"skill_name": "manage_workers", "params": {"name": "李一凡"}}],
        ttl_seconds=300,
    )

    result = build_session_debug_export(db, farm_id=1, session_id="sess-debug")

    assert result["format"] == "farm-manager.chat-session-debug.v2"
    assert len(result["messages"]) == 2
    assert result["turns"][0]["request_id"] == "abcd1234"
    assert result["events"][0]["event_type"] == "message.user"
    assert result["pending_plans"][0]["raw_user_input"] == "停用李一凡"
    db.close()


def test_debug_export_reads_backend_relative_event_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.infra.repository_runtime.settings.storage.conversation_messages",
        "mysql",
    )
    db = Session()
    conv = get_or_create_conversation(
        db, farm_id=1, session_id="sess-backend-events", user_id="user-1"
    )
    user_msg = save_message(db, conv.id, "user", "nihao")
    turn = create_turn(
        db,
        farm_id=1,
        session_id="sess-backend-events",
        conversation_id=conv.id,
        request_id="hello1",
        user_message_id=user_msg.id,
        input_text="nihao",
    )
    backend_dir = tmp_path / "backend"
    writer = AgentEventWriter(base_dir=backend_dir / "data/agent-events")
    first = writer.write(
        event_type="message.user",
        farm_id=1,
        user_id="user-1",
        session_id="sess-backend-events",
        turn_id=turn.id,
        request_id="hello1",
        payload={"content": "nihao"},
    )
    mark_event_range(
        db,
        turn.id,
        event_file=str(first.event_file).replace(str(backend_dir) + "/", ""),
        seq_start=first.seq,
        seq_end=first.seq,
        write_status="success",
    )

    monkeypatch.chdir(tmp_path)
    result = build_session_debug_export(db, farm_id=1, session_id="sess-backend-events")

    assert result["events"][0]["event_type"] == "message.user"
    assert result["missing_event_segments"] == []
    db.close()


def test_debug_export_includes_pending_plan_created_by_runtime_store(monkeypatch):
    db = Session()

    class _SessionFactory:
        def __call__(self):
            return db

    monkeypatch.setattr("app.infra.pending_actions.SessionLocal", _SessionFactory())

    try:
        store_pending_plan(
            farm_id=1,
            session_id="sess-runtime-pending",
            raw_user_input="王大妈去5号棚收水稻",
            router_decision={
                "selected_tools": ["manage_workers", "create_operation_work_order"]
            },
            steps=[
                {
                    "tool_name": "manage_workers",
                    "params": {"name": "王大妈", "daily_wage": 100},
                    "depends_on": [],
                },
                {
                    "tool_name": "create_operation_work_order",
                    "params": {"field_name": "5号棚", "crop_name": "水稻"},
                    "depends_on": ["step-1"],
                },
            ],
        )

        result = build_session_debug_export(
            db, farm_id=1, session_id="sess-runtime-pending"
        )

        assert result["pending_plans"][0]["raw_user_input"] == "王大妈去5号棚收水稻"
        assert result["pending_plans"][0]["steps"][1]["skill_name"] == (
            "create_operation_work_order"
        )
    finally:
        db.close()
