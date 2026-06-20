"""Agent turn service 测试。"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.infra.agent_events import AgentEventWriter
from app.models.agent_turn import AgentTurn
from app.models.conversation import Conversation, ConversationMessage
from app.models.farm import Farm
from app.models.trace import TraceRecord
from app.services.agent_turn_service import create_turn, finish_turn, mark_event_range

pytestmark = pytest.mark.no_db


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


def test_finish_turn_persists_discovery_rule_risk():
    db = Session()
    conv = Conversation(farm_id=1, user_id="user-1", session_id="sess-risk")
    db.add(conv)
    db.commit()

    turn = create_turn(
        db,
        farm_id=1,
        session_id="sess-risk",
        conversation_id=conv.id,
        request_id="risk1234",
        user_message_id=None,
        input_text="今天会下雨吗",
    )
    finish_turn(
        db,
        turn.id,
        reply_text="今天有雨，建议减少户外作业。",
        assistant_message_id=None,
        selected_tools_count=0,
        tool_calls_count=0,
        status="success",
    )

    loaded = db.query(AgentTurn).filter_by(id=turn.id).one()
    assert loaded.rule_hits == ["weather_without_search"]
    assert loaded.rule_score == 0.75
    assert loaded.risk_score == 0.75
    assert loaded.risk_dominant_signal == "rule"
    assert loaded.risk_severity == "P1"
    db.close()


def test_mark_event_range_refreshes_rule_risk_from_event_log(tmp_path):
    db = Session()
    conv = Conversation(farm_id=1, user_id="user-1", session_id="sess-event-risk")
    db.add(conv)
    db.commit()
    turn = create_turn(
        db,
        farm_id=1,
        session_id="sess-event-risk",
        conversation_id=conv.id,
        request_id="event123",
        user_message_id=None,
        input_text="记录一笔化肥成本",
    )
    finish_turn(
        db,
        turn.id,
        reply_text="已帮你记录好了。",
        assistant_message_id=None,
        selected_tools_count=1,
        tool_calls_count=1,
        status="success",
    )

    writer = AgentEventWriter(base_dir=tmp_path)
    user_event = writer.write(
        event_type="message.user",
        farm_id=1,
        user_id="user-1",
        session_id="sess-event-risk",
        turn_id=turn.id,
        request_id="event123",
        payload={"content": "记录一笔化肥成本"},
    )
    tool_event = writer.write(
        event_type="tool.call.finished",
        farm_id=1,
        user_id="user-1",
        session_id="sess-event-risk",
        turn_id=turn.id,
        request_id="event123",
        payload={
            "tool_name": "create_cost",
            "status": "error",
            "result": {"message": "db unavailable"},
        },
    )

    mark_event_range(
        db,
        turn.id,
        event_file=user_event.event_file,
        seq_start=user_event.seq,
        seq_end=tool_event.seq,
        write_status="success",
    )

    loaded = db.query(AgentTurn).filter_by(id=turn.id).one()
    assert loaded.rule_hits == ["tool_error_ignored"]
    assert loaded.risk_score == 0.95
    assert loaded.risk_severity == "P0"
    db.close()


def test_finish_turn_reads_tool_status_from_trace_records():
    db = Session()
    conv = Conversation(farm_id=1, user_id="user-1", session_id="sess-trace-risk")
    db.add(conv)
    db.commit()
    turn = create_turn(
        db,
        farm_id=1,
        session_id="sess-trace-risk",
        conversation_id=conv.id,
        request_id="trace123",
        user_message_id=None,
        input_text="记录一笔化肥成本",
    )
    db.add(
        TraceRecord(
            request_id="trace123",
            session_id="sess-trace-risk",
            farm_id=1,
            round_index=1,
            node_type="skill_call",
            node_name="create_cost",
            input_data={"amount": 100},
            output_data={"status": "validation_error"},
            status="error",
        )
    )
    db.commit()

    finish_turn(
        db,
        turn.id,
        reply_text="已帮你记录好了。",
        assistant_message_id=None,
        selected_tools_count=1,
        tool_calls_count=1,
        status="success",
    )

    loaded = db.query(AgentTurn).filter_by(id=turn.id).one()
    assert loaded.rule_hits == ["tool_error_ignored"]
    assert loaded.risk_score == 0.95
    assert loaded.risk_dominant_signal == "rule"
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
