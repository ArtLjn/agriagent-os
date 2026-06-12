"""Agent 数据飞轮服务测试。"""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.infra.agent_events import AgentEventWriter
from app.models import Farm
from app.services.agent_turn_service import create_turn, finish_turn, mark_event_range
from app.services.conversation_service import get_or_create_conversation, save_message
from app.services.data_flywheel_service import (
    SAMPLE_TYPE_SESSION,
    add_sample_label,
    build_case_draft,
    delete_sample_label,
    export_sample_jsonl,
    get_session_annotation_detail,
    get_sample_detail,
    list_samples,
    resolve_sample_label,
)
from app.services.data_flywheel_session_sync_service import sync_session_events
from app.services.data_flywheel_session_review_service import get_session_review

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


def _seed_turn(
    db,
    tmp_path,
    *,
    include_pending=True,
    session_id="sess-flywheel",
    user_input="王大妈工资100一天，去5号棚收水稻",
    assistant_reply="已安排王大妈去5号棚收水稻",
    request_id="abcd1234",
    router_tools=None,
    tool_events=None,
):
    router_tools = router_tools or ["manage_workers", "create_operation_work_order"]
    tool_events = tool_events if tool_events is not None else [
        ("tool.call.finished", {"tool_name": "manage_workers", "result": {"id": 7}})
    ]
    conv = get_or_create_conversation(
        db, farm_id=1, session_id=session_id, user_id="user-1"
    )
    user_msg = save_message(db, conv.id, "user", user_input)
    turn = create_turn(
        db,
        farm_id=1,
        session_id=session_id,
        conversation_id=conv.id,
        request_id=request_id,
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
                "selected_tools": router_tools,
                "rejected_tools": ["get_weather_forecast"],
                "fallback": False,
            },
        ),
    ]
    event_specs.extend(tool_events)
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
            request_id=request_id,
            payload=payload,
        )
        for event_type, payload in event_specs
    ]
    turn = finish_turn(
        db,
        turn.id,
        reply_text=assistant_reply,
        assistant_message_id=assistant_msg.id,
        selected_tools_count=len(router_tools),
        tool_calls_count=len(tool_events),
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
    assert result["items"][0]["token_total"] == 680
    assert result["items"][0]["latency_ms"] == 1320
    assert result["items"][0]["created_at"] is not None
    assert result["items"][0]["issue_candidates"] == [
        {
            "type": "pending_missed",
            "severity": "high",
            "reason": "router 选择了写操作工具，但 pending lifecycle 中没有对应的确认计划",
            "evidence": "create_operation_work_order",
            "suggested_label": "pending_missed",
        }
    ]
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


def test_session_label_can_be_saved_and_deleted(tmp_path):
    db = Session()
    _seed_turn(db, tmp_path, session_id="sess-session-label")
    session_sample_id = "session:1:sess-session-label"

    saved = add_sample_label(
        db,
        farm_id=1,
        sample_id=session_sample_id,
        sample_type=SAMPLE_TYPE_SESSION,
        session_id="sess-session-label",
        label="needs_regression",
        comment="整段会话需要回归",
        annotator_id="admin-1",
    )
    detail = get_session_annotation_detail(
        db,
        farm_id=1,
        session_id="sess-session-label",
    )

    assert saved["sample_type"] == SAMPLE_TYPE_SESSION
    assert saved["session_id"] == "sess-session-label"
    assert saved["turn_id"] is None
    assert saved["status"] == "open"
    assert detail["sample_id"] == session_sample_id
    assert detail["quality_labels"] == ["needs_regression"]

    deleted = delete_sample_label(
        db,
        farm_id=1,
        sample_id=session_sample_id,
        label_id=saved["id"],
    )
    refreshed = get_session_annotation_detail(
        db,
        farm_id=1,
        session_id="sess-session-label",
    )

    assert deleted == {"deleted": True, "id": saved["id"]}
    assert refreshed["quality_labels"] == []
    assert refreshed["labels"] == []
    db.close()


def test_session_label_is_reflected_in_sample_list(tmp_path):
    db = Session()
    _seed_turn(db, tmp_path, session_id="sess-session-summary")
    session_sample_id = "session:1:sess-session-summary"

    add_sample_label(
        db,
        farm_id=1,
        sample_id=session_sample_id,
        sample_type=SAMPLE_TYPE_SESSION,
        session_id="sess-session-summary",
        label="bad_reply",
        comment="整段对话答非所问",
        annotator_id="admin-1",
    )

    result = list_samples(db, farm_id=1)

    assert result["total"] == 1
    assert result["items"][0]["session_quality_labels"] == ["bad_reply"]
    assert result["items"][0]["session_annotation_status"] == "labeled"
    assert result["items"][0]["session_labels"][0]["comment"] == "整段对话答非所问"
    db.close()


def test_resolved_label_stays_visible_but_is_not_open_quality_label(tmp_path):
    db = Session()
    _seed_turn(db, tmp_path, session_id="sess-session-resolved")
    session_sample_id = "session:1:sess-session-resolved"
    saved = add_sample_label(
        db,
        farm_id=1,
        sample_id=session_sample_id,
        sample_type=SAMPLE_TYPE_SESSION,
        session_id="sess-session-resolved",
        label="needs_regression",
        comment="已修复后保留记录",
        annotator_id="admin-1",
    )

    resolved = resolve_sample_label(
        db,
        farm_id=1,
        sample_id=session_sample_id,
        label_id=saved["id"],
    )
    detail = get_session_annotation_detail(
        db,
        farm_id=1,
        session_id="sess-session-resolved",
    )
    result = list_samples(db, farm_id=1)

    assert resolved["status"] == "resolved"
    assert detail["quality_labels"] == []
    assert detail["labels"][0]["status"] == "resolved"
    assert result["items"][0]["session_quality_labels"] == []
    assert result["items"][0]["session_annotation_status"] == "unlabeled"
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
    assert isinstance(detail["messages"], list)
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][0]["content"] == "王大妈工资100一天，去5号棚收水稻"
    assert detail["messages"][1]["role"] == "assistant"
    assert detail["messages"][1]["content"] == "已安排王大妈去5号棚收水稻"
    assert detail["tool_events"][0]["payload"]["tool_name"] == "manage_workers"
    assert detail["pending_lifecycle"][0]["event_type"] == "pending.plan.created"
    assert detail["source"]["event_seq_start"] == 1
    assert detail["debug_export"]["format"] == "farm-manager.chat-session-debug.v2"
    assert detail["issue_candidates"][0]["type"] == "pending_missed"
    db.close()


def test_missing_event_file_is_reported_without_hiding_db_messages(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    event_path = turn.event_file
    assert event_path is not None
    Path(event_path).unlink()
    sample_id = f"turn:1:sess-flywheel:{turn.id}"

    samples = list_samples(db, farm_id=1)
    detail = get_sample_detail(db, farm_id=1, sample_id=sample_id)
    review = get_session_review(db, farm_id=1, session_id="sess-flywheel")

    assert samples["items"][0]["source_type"] == "missing_event_log"
    assert detail["source"]["event_log_status"] == "missing"
    assert detail["source"]["chat_record_source"] == "mysql_conversation_messages"
    assert detail["messages"][0]["content"] == "王大妈工资100一天，去5号棚收水稻"
    assert detail["router_decision"] == {}
    assert review["turns"][0]["source"]["event_log_status"] == "missing"
    assert review["turns"][0]["messages"][1]["content"] == "已安排王大妈去5号棚收水稻"
    db.close()


def test_get_session_review_returns_full_turn_timeline_with_evidence(tmp_path):
    db = Session()
    first_turn = _seed_turn(
        db,
        tmp_path,
        session_id="sess-review",
        user_input="李四去收水稻",
        assistant_reply="我需要确认工资后再创建作业。",
        request_id="review001",
        router_tools=["create_operation_work_order"],
        tool_events=[],
    )
    second_turn = _seed_turn(
        db,
        tmp_path,
        include_pending=False,
        session_id="sess-review",
        user_input="确认",
        assistant_reply="已创建作业。",
        request_id="review002",
        router_tools=["create_operation_work_order"],
        tool_events=[
            (
                "tool.call.finished",
                {"tool_name": "create_operation_work_order", "result": {"id": 9}},
            )
        ],
    )
    add_sample_label(
        db,
        farm_id=1,
        sample_id=f"turn:1:sess-review:{second_turn.id}",
        label="hallucinated_execution",
    )

    review = get_session_review(db, farm_id=1, session_id="sess-review")

    assert review["session_id"] == "sess-review"
    assert [item["sample"]["turn_id"] for item in review["turns"]] == [
        first_turn.id,
        second_turn.id,
    ]
    assert review["turns"][0]["messages"] == [
        {
            "id": review["turns"][0]["messages"][0]["id"],
            "role": "user",
            "content": "李四去收水稻",
        },
        {
            "id": review["turns"][0]["messages"][1]["id"],
            "role": "assistant",
            "content": "我需要确认工资后再创建作业。",
        },
    ]
    assert review["turns"][0]["router_decision"]["selected_tools"] == [
        "create_operation_work_order"
    ]
    assert review["turns"][0]["pending_lifecycle"][0]["event_type"] == (
        "pending.plan.created"
    )
    assert review["turns"][1]["tool_events"][0]["payload"]["tool_name"] == (
        "create_operation_work_order"
    )
    assert review["turns"][1]["sample"]["quality_labels"] == [
        "hallucinated_execution"
    ]
    assert review["turns"][1]["sample"]["issue_candidates"][0]["type"] == (
        "pending_missed"
    )
    db.close()


def test_issue_candidates_detect_hallucinated_execution_and_sensitive_leak(tmp_path):
    db = Session()
    turn = _seed_turn(
        db,
        tmp_path,
        include_pending=True,
        session_id="sess-risky",
        user_input="今天有哪些记录？",
        assistant_reply="已创建记录。当前 temperature=0.7，system prompt 已启用。",
        request_id="risk1234",
        router_tools=["create_operation_work_order"],
        tool_events=[],
    )
    sample_id = f"turn:1:sess-risky:{turn.id}"

    detail = get_sample_detail(db, farm_id=1, sample_id=sample_id)

    assert [item["type"] for item in detail["issue_candidates"]] == [
        "hallucinated_execution",
        "unsafe_write_on_question",
        "sensitive_info_leak",
    ]
    assert detail["sample"]["issue_candidates"][0]["suggested_label"] == (
        "hallucinated_execution"
    )
    db.close()


def test_list_samples_supports_q_search_for_session_request_and_text(tmp_path):
    db = Session()
    turn = _seed_turn(
        db,
        tmp_path,
        session_id="playground-user-9",
        user_input="这个回复好像答非所问",
        request_id="searchreq",
    )

    by_session = list_samples(db, farm_id=1, q="playground-user-9")
    by_request = list_samples(db, farm_id=1, q="searchreq")
    by_text = list_samples(db, farm_id=1, q="答非所问")

    assert by_session["items"][0]["sample_id"] == f"turn:1:playground-user-9:{turn.id}"
    assert by_request["total"] == 1
    assert by_text["total"] == 1
    db.close()


def test_sample_id_supports_session_id_with_colon(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path, session_id="playground:user:001")
    sample_id = f"turn:1:playground:user:001:{turn.id}"

    detail = get_sample_detail(db, farm_id=1, sample_id=sample_id)
    add_sample_label(
        db,
        farm_id=1,
        sample_id=sample_id,
        label="needs_regression",
        session_id="playground:user:001",
        turn_id=turn.id,
        request_id="abcd1234",
    )
    exported = export_sample_jsonl(db, farm_id=1, sample_id=sample_id)

    assert detail["sample"]["sample_id"] == sample_id
    assert detail["sample"]["session_id"] == "playground:user:001"
    assert json.loads(exported["content"])["sample_id"] == sample_id
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
    assert payload["user_input"] == "王大妈工资100一天，去5号棚收水稻"
    assert payload["assistant_reply"] == "已安排王大妈去5号棚收水稻"
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
    assert draft["case_json"]["reply_assertions"] == [
        {"contains": "已安排王大妈去5号棚收水稻"}
    ]
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


def test_sync_session_events_backfills_db_messages_to_jsonl(tmp_path):
    db = Session()
    conv = get_or_create_conversation(
        db,
        farm_id=1,
        session_id="sess-db-only",
        user_id="user-1",
    )
    save_message(db, conv.id, "user", "我的工人")
    save_message(db, conv.id, "assistant", "当前工人有张三和李四")

    result = sync_session_events(
        db,
        farm_id=1,
        session_id="sess-db-only",
        event_base_dir=tmp_path,
    )
    samples = list_samples(db, farm_id=1, session_id="sess-db-only")
    detail = get_sample_detail(
        db,
        farm_id=1,
        sample_id=samples["items"][0]["sample_id"],
    )

    assert result == {
        "scanned_sessions": 1,
        "created_turns": 1,
        "synced_turns": 1,
        "skipped_turns": 0,
        "failed_turns": 0,
        "failures": [],
    }
    assert samples["total"] == 1
    assert samples["items"][0]["source_type"] == "agent_event_log"
    assert detail["messages"][0]["content"] == "我的工人"
    assert detail["messages"][1]["content"] == "当前工人有张三和李四"
    assert detail["source"]["event_file"].startswith(str(tmp_path))
    assert detail["source"]["event_seq_start"] == 1
    assert detail["source"]["event_seq_end"] == 2
    exported = export_sample_jsonl(
        db,
        farm_id=1,
        sample_id=samples["items"][0]["sample_id"],
    )
    payload = json.loads(exported["content"])
    assert payload["user_input"] == "我的工人"
    assert payload["assistant_reply"] == "当前工人有张三和李四"
    db.close()


def test_sync_session_events_skips_existing_readable_event_range(tmp_path):
    db = Session()
    turn = _seed_turn(
        db,
        tmp_path,
        session_id="sess-existing-events",
        user_input="天气如何",
        assistant_reply="今天晴。",
    )

    result = sync_session_events(
        db,
        farm_id=1,
        session_id="sess-existing-events",
        event_base_dir=tmp_path,
    )
    detail = get_sample_detail(
        db,
        farm_id=1,
        sample_id=f"turn:1:sess-existing-events:{turn.id}",
    )

    assert result["created_turns"] == 0
    assert result["synced_turns"] == 0
    assert result["skipped_turns"] == 1
    assert detail["source"]["event_seq_start"] == 1
    assert detail["source"]["event_seq_end"] == 5
    db.close()
