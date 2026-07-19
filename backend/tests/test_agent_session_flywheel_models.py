"""Agent 会话飞轮模型测试。"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.shared.database import Base
from app.models.agent_turn import AgentTurn
from app.models.conversation import Conversation, ConversationMessage
from app.models.farm import Farm
from app.models.pending_plan import AgentPendingPlan, AgentPendingPlanStep

pytestmark = pytest.mark.no_db


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_agent_session_flywheel_models.db",
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


def test_conversation_hot_path_columns_round_trip():
    db = Session()
    conv = Conversation(
        farm_id=1,
        user_id="user-1",
        session_id="sess-hot",
        summary="前面聊过水稻收割",
        last_turn_id=7,
        last_event_seq=12,
        meta_json={"source": "playground"},
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    msg = ConversationMessage(
        conversation_id=conv.id,
        turn_id=7,
        role="assistant",
        content="已为您整理",
        content_hash="hash-1",
        meta_json={"skills": ["get_farm_status"]},
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    assert conv.summary == "前面聊过水稻收割"
    assert conv.meta_json == {"source": "playground"}
    assert msg.turn_id == 7
    assert msg.meta_json == {"skills": ["get_farm_status"]}
    db.close()


def test_agent_turn_links_messages_and_event_range():
    db = Session()
    conv = Conversation(farm_id=1, user_id="user-1", session_id="sess-turn")
    db.add(conv)
    db.commit()
    user_msg = ConversationMessage(
        conversation_id=conv.id, role="user", content="查一下作物"
    )
    assistant_msg = ConversationMessage(
        conversation_id=conv.id, role="assistant", content="有水稻"
    )
    db.add_all([user_msg, assistant_msg])
    db.commit()

    turn = AgentTurn(
        farm_id=1,
        session_id="sess-turn",
        conversation_id=conv.id,
        request_id="abcd1234",
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        input_preview="查一下作物",
        reply_preview="有水稻",
        selected_tools_count=1,
        tool_calls_count=1,
        token_total=320,
        latency_ms=1200,
        status="success",
        event_file="data/agent-events/dt=2026-06-11/farm_id=1/session_id=sess-turn/events.jsonl",
        event_seq_start=1,
        event_seq_end=4,
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)

    assert turn.id is not None
    assert turn.selected_tools_count == 1
    assert turn.event_seq_end == 4
    db.close()


def test_agent_turn_discovery_risk_fields_have_defaults():
    db = Session()
    turn = AgentTurn(
        farm_id=1,
        session_id="sess-risk",
        request_id="risk1234",
        input_preview="查一下天气",
        reply_preview="今天天气不错",
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)

    assert turn.risk_score == 0.0
    assert turn.rule_score == 0.0
    assert turn.risk_dominant_signal is None
    assert turn.rule_hits == []
    assert turn.risk_severity is None
    assert turn.judge_bad_prob is None
    assert turn.judge_issue_type is None
    assert turn.judge_suggested_label is None
    db.close()


def test_pending_plan_and_steps_are_recoverable():
    db = Session()
    expires_at = datetime.now() + timedelta(minutes=5)
    plan = AgentPendingPlan(
        plan_id="plan-1",
        farm_id=1,
        session_id="sess-pending",
        status="pending",
        current_step_index=0,
        raw_user_input="王大妈工资100一天，去5号棚收水稻",
        router_decision_json={
            "selected_tools": ["manage_workers", "create_operation_work_order"]
        },
        expires_at=expires_at,
    )
    step1 = AgentPendingPlanStep(
        plan_id="plan-1",
        step_index=0,
        skill_name="manage_workers",
        params_json={"name": "王大妈", "daily_wage": 100},
        status="pending",
        requires_confirmation=True,
        confirmation_text="确认创建工人王大妈吗？",
    )
    step2 = AgentPendingPlanStep(
        plan_id="plan-1",
        step_index=1,
        skill_name="create_operation_work_order",
        params_json={"field_name": "5号棚", "crop_name": "水稻"},
        status="pending",
        requires_confirmation=True,
        confirmation_text="确认安排王大妈去5号棚收水稻吗？",
    )
    db.add_all([plan, step1, step2])
    db.commit()

    loaded = db.query(AgentPendingPlan).filter_by(plan_id="plan-1").one()
    assert loaded.status == "pending"
    assert len(loaded.steps) == 2
    assert loaded.steps[0].params_json["daily_wage"] == 100
    db.close()
