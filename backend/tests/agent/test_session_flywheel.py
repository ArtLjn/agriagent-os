"""Session flywheel orchestration 测试。"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.agent.application.session_flywheel import (
    SessionFlywheelRecorder,
    build_message_meta,
)
from app.core.database import Base
from app.models.farm import Farm
from app.services.conversation_service import get_or_create_conversation


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_session_flywheel.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场", user_id="user-1"))
    db.commit()
    db.close()


def test_build_message_meta_keeps_only_light_fields():
    meta = build_message_meta(
        skills=["get_farm_status"],
        pending_action={"action_id": "a1"},
        trace_request_id="abcd1234",
        event_file="events.jsonl",
        event_seq_range=(1, 4),
    )

    assert meta == {
        "skills": ["get_farm_status"],
        "pending_action": {"action_id": "a1"},
        "trace_request_id": "abcd1234",
        "event_file": "events.jsonl",
        "event_seq_range": [1, 4],
    }


def test_recorder_records_user_and_assistant_messages_turn_and_events(tmp_path):
    db = Session()
    conv = get_or_create_conversation(
        db, farm_id=1, session_id="sess-flow", user_id="user-1"
    )
    recorder = SessionFlywheelRecorder(event_base_dir=tmp_path)

    started = recorder.start_turn(
        db,
        farm_id=1,
        user_id="user-1",
        session_id="sess-flow",
        conversation_id=conv.id,
        request_id="abcd1234",
        user_message="查一下作物",
    )
    finished = recorder.finish_turn(
        db,
        started,
        assistant_reply="当前有水稻",
        skills=["get_farm_status"],
        pending_action=None,
        selected_tools_count=1,
        tool_calls_count=1,
        token_total=500,
        latency_ms=1200,
        status="success",
    )

    assert finished.turn_id == started.turn_id
    assert finished.user_message_id is not None
    assert finished.assistant_message_id is not None
    assert finished.event_file is not None
    assert finished.event_seq_start == 1
    assert finished.event_seq_end == 2
    db.close()
