"""Agent 数据飞轮服务测试。"""

import json

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.infra.agent_events import AgentEventWriter
from app.models import Farm
from app.services.agent_turn_service import create_turn, finish_turn, mark_event_range
from app.services.conversation_service import get_or_create_conversation, save_message
from app.services.data_flywheel_service import (
    add_sample_label,
    build_case_draft,
    export_sample_jsonl,
    get_sample_detail,
    list_samples,
)

pytestmark = pytest.mark.no_db


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_data_flywheel_service.db",
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


def _seed_turn(db, tmp_path, *, include_pending=True):
    session_id = "sess-flywheel"
    user_input = "王大妈工资100一天，去5号棚收水稻"
    assistant_reply = "已安排王大妈去5号棚收水稻"
    conv = get_or_create_conversation(
        db, farm_id=1, session_id=session_id, user_id="user-1"
    )
    user_msg = save_message(db, conv.id, "user", user_input)
    turn = create_turn(
        db,
        farm_id=1,
        session_id=session_id,
        conversation_id=conv.id,
        request_id="abcd1234",
        user_message_id=user_msg.id,
        input_text=user_input,
    )
    assistant_msg = save_message(db, conv.id, "assistant", assistant_reply)
    user_msg.turn_id = turn.id
    assistant_msg.turn_id = turn.id
    db.commit()

    writer = AgentEventWriter(base_dir=tmp_path)
    event_specs = [
        (
            "message.user",
            {"content": user_input},
        ),
        (
            "router.decision",
            {
                "selected_tools": [
                    "manage_workers",
                    "create_operation_work_order",
                ],
                "rejected_tools": ["get_weather_forecast"],
                "fallback": False,
            },
        ),
        (
            "tool.call.finished",
            {"tool_name": "manage_workers", "result": {"id": 7}},
        ),
    ]
    if include_pending:
        event_specs.append(
            (
                "pending.plan.created",
                {
                    "plan_id": "plan-1",
                    "steps": [{"skill_name": "manage_workers"}],
                },
            )
        )
    event_specs.append(
        (
            "message.assistant",
            {"content": assistant_reply},
        )
    )
    writes = [
        writer.write(
            event_type=event_type,
            farm_id=1,
            user_id="user-1",
            session_id=session_id,
            turn_id=turn.id,
            request_id="abcd1234",
            payload=payload,
        )
        for event_type, payload in event_specs
    ]
    turn = finish_turn(
        db,
        turn.id,
        reply_text=assistant_reply,
        assistant_message_id=assistant_msg.id,
        selected_tools_count=2,
        tool_calls_count=1,
        token_total=680,
        latency_ms=1320,
        status="success",
        pending_plan_id="plan-1" if include_pending else None,
    )
    turn = mark_event_range(
        db,
        turn.id,
        event_file=writes[0].event_file,
        seq_start=writes[0].seq,
        seq_end=writes[-1].seq,
        write_status="success",
    )
    return turn


def test_list_samples_returns_lightweight_turn_rows(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)

    result = list_samples(db, farm_id=1)

    assert result["total"] == 1
    assert result["items"][0]["sample_id"] == f"turn:1:sess-flywheel:{turn.id}"
    assert result["items"][0]["sample_type"] == "session_turn"
    assert result["items"][0]["session_id"] == "sess-flywheel"
    assert result["items"][0]["request_id"] == "abcd1234"
    assert result["items"][0]["user_input_preview"] == (
        "王大妈工资100一天，去5号棚收水稻"
    )
    assert result["items"][0]["assistant_reply_preview"] == (
        "已安排王大妈去5号棚收水稻"
    )
    assert result["items"][0]["source_type"] == "agent_event_log"
    assert result["items"][0]["selected_tools"] == [
        "manage_workers",
        "create_operation_work_order",
    ]
    assert result["items"][0]["actual_tools"] == ["manage_workers"]
    assert result["items"][0]["annotation_status"] == "unlabeled"
    db.close()


def test_labels_are_reflected_in_sample_list(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = f"turn:1:sess-flywheel:{turn.id}"

    add_sample_label(
        db,
        farm_id=1,
        sample_id=sample_id,
        label="wrong_tool_selection",
        annotator_id="admin-1",
    )

    result = list_samples(db, farm_id=1, label="wrong_tool_selection")
    assert result["total"] == 1
    assert result["items"][0]["quality_labels"] == ["wrong_tool_selection"]
    assert result["items"][0]["annotation_status"] == "labeled"

    unannotated = list_samples(db, farm_id=1, unannotated_only=True)
    assert unannotated["total"] == 0
    db.close()


def test_invalid_label_and_farm_mismatch_raise_value_error(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = f"turn:1:sess-flywheel:{turn.id}"

    with pytest.raises(ValueError) as invalid_label:
        add_sample_label(db, farm_id=1, sample_id=sample_id, label="unknown_label")
    assert str(invalid_label.value) == "INVALID_LABEL"

    with pytest.raises(ValueError) as farm_mismatch:
        get_sample_detail(db, farm_id=2, sample_id=sample_id)
    assert str(farm_mismatch.value) == "SAMPLE_NOT_FOUND"
    db.close()


def test_get_sample_detail_includes_events_and_debug_export(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = f"turn:1:sess-flywheel:{turn.id}"

    detail = get_sample_detail(db, farm_id=1, sample_id=sample_id)

    assert detail["sample"]["sample_id"] == sample_id
    assert detail["turn"]["request_id"] == "abcd1234"
    assert detail["router_decision"]["selected_tools"] == [
        "manage_workers",
        "create_operation_work_order",
    ]
    assert detail["tool_events"][0]["payload"]["tool_name"] == "manage_workers"
    assert detail["pending_lifecycle"][0]["event_type"] == "pending.plan.created"
    assert detail["source"]["event_seq_start"] == 1
    assert detail["debug_export"]["format"] == "farm-manager.chat-session-debug.v2"
    db.close()


def test_export_sample_jsonl_returns_one_serializable_line(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = f"turn:1:sess-flywheel:{turn.id}"
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="missing_wage")

    result = export_sample_jsonl(db, farm_id=1, sample_id=sample_id)
    rows = result["content"].splitlines()
    payload = json.loads(rows[0])

    assert result["filename"].startswith("data-flywheel-sample-")
    assert len(rows) == 1
    assert payload["sample_id"] == sample_id
    assert payload["quality_labels"] == ["missing_wage"]
    db.close()


def test_build_case_draft_from_sample(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = f"turn:1:sess-flywheel:{turn.id}"
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="needs_regression")

    draft = build_case_draft(
        db,
        farm_id=1,
        sample_id=sample_id,
        target_type="evaluation_replay",
        created_by="admin-1",
    )

    assert draft["status"] == "draft"
    assert draft["target_type"] == "evaluation_replay"
    assert draft["case_json"]["user_input"] == "王大妈工资100一天，去5号棚收水稻"
    assert draft["case_json"]["expected_skills"][0]["name"] == "manage_workers"
    assert draft["case_json"]["expected_pending_action"] == {
        "skill_name": "manage_workers",
        "params": {},
        "status": "created",
        "confirmation_required": True,
    }
    assert draft["case_json"]["metadata"]["source_sample_id"] == sample_id
    db.close()


def test_build_case_draft_without_pending_sets_expected_pending_action_none(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path, include_pending=False)
    sample_id = f"turn:1:sess-flywheel:{turn.id}"
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="needs_regression")

    draft = build_case_draft(
        db,
        farm_id=1,
        sample_id=sample_id,
        target_type="evaluation_replay",
    )

    assert draft["case_json"]["expected_pending_action"] is None
    db.close()
