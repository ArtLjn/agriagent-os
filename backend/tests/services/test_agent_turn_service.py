"""Agent turn service 测试。"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.agent_turn import AgentTurn
from app.models.conversation import Conversation, ConversationMessage
from app.models.farm import Farm
from app.services.agent_turn_service import create_turn, finish_turn, mark_event_range


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_agent_turn_service.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()


def test_create_finish_and_mark_event_range():
    db = Session()
    conv = Conversation(farm_id=1, user_id="user-1", session_id="sess-turn")
    db.add(conv)
    db.commit()
    msg = ConversationMessage(
        conversation_id=conv.id, role="user", content="查一下作物"
    )
    db.add(msg)
    db.commit()

    turn = create_turn(
        db,
        farm_id=1,
        session_id="sess-turn",
        conversation_id=conv.id,
        request_id="abcd1234",
        user_message_id=msg.id,
        input_text="查一下作物",
    )
    finish_turn(
        db,
        turn.id,
        reply_text="当前有水稻",
        assistant_message_id=22,
        selected_tools_count=1,
        tool_calls_count=1,
        token_total=500,
        latency_ms=1200,
        status="success",
    )
    mark_event_range(
        db,
        turn.id,
        event_file="data/agent-events/dt=2026-06-11/farm_id=1/session_id=sess-turn/events.jsonl",
        seq_start=1,
        seq_end=5,
        write_status="success",
    )

    loaded = db.query(AgentTurn).filter_by(id=turn.id).one()
    assert loaded.input_preview == "查一下作物"
    assert loaded.reply_preview == "当前有水稻"
    assert loaded.event_seq_start == 1
    assert loaded.event_seq_end == 5
    assert loaded.event_write_status == "success"
    db.refresh(conv)
    assert conv.last_turn_id == turn.id
    db.close()


def test_preview_is_truncated_to_keep_turn_lightweight():
    db = Session()
    conv = Conversation(farm_id=1, user_id="user-1", session_id="sess-long")
    db.add(conv)
    db.commit()
    long_text = "水稻" * 200

    turn = create_turn(
        db,
        farm_id=1,
        session_id="sess-long",
        conversation_id=conv.id,
        request_id="req12345",
        user_message_id=None,
        input_text=long_text,
    )

    assert len(turn.input_preview) <= 123
    assert turn.input_preview.endswith("...")
    db.close()
