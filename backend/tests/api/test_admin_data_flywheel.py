"""Admin 数据飞轮 API 测试。"""

import json

from fastapi.testclient import TestClient

import app.api.admin_data_flywheel as admin_data_flywheel_api
from app.infra.agent_events import AgentEventWriter
from app.main import app
from app.models.data_flywheel import AgentDataFlywheelLabel
from app.models.farm import Farm
from app.services.agent_turn_service import create_turn, finish_turn, mark_event_range
from app.services.conversation_service import get_or_create_conversation, save_message
from tests.api.auth_helpers import (
    ADMIN_USER_ID,
    admin_headers,
    auth_override_scope,
    ensure_admin_user,
)


def _seed_turn(db, tmp_path):
    ensure_admin_user(db)
    farm = db.query(Farm).filter(Farm.user_id == ADMIN_USER_ID).one()
    session_id = "sess-admin-flywheel"
    user_input = "王大妈工资100一天，去5号棚收水稻"
    assistant_reply = "已安排王大妈去5号棚收水稻"
    conv = get_or_create_conversation(
        db,
        farm_id=farm.id,
        session_id=session_id,
        user_id=ADMIN_USER_ID,
    )
    user_msg = save_message(db, conv.id, "user", user_input)
    turn = create_turn(
        db,
        farm_id=farm.id,
        session_id=session_id,
        conversation_id=conv.id,
        request_id="adminfly",
        user_message_id=user_msg.id,
        input_text=user_input,
    )
    assistant_msg = save_message(db, conv.id, "assistant", assistant_reply)
    user_msg.turn_id = turn.id
    assistant_msg.turn_id = turn.id
    db.commit()

    writer = AgentEventWriter(base_dir=tmp_path)
    event_specs = [
        ("message.user", {"content": user_input}),
        (
            "router.decision",
            {
                "selected_tools": [
                    "manage_workers",
                    "create_operation_work_order",
                ],
                "fallback": False,
            },
        ),
        (
            "tool.call.finished",
            {"tool_name": "manage_workers", "result": {"id": 7}},
        ),
        (
            "pending.plan.created",
            {"plan_id": "plan-1", "steps": [{"skill_name": "manage_workers"}]},
        ),
        ("message.assistant", {"content": assistant_reply}),
    ]
    writes = [
        writer.write(
            event_type=event_type,
            farm_id=farm.id,
            user_id=ADMIN_USER_ID,
            session_id=session_id,
            turn_id=turn.id,
            request_id="adminfly",
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
        pending_plan_id="plan-1",
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


def _sample_id(turn) -> str:
    return f"turn:{turn.farm_id}:sess-admin-flywheel:{turn.id}"


def _admin_client():
    return auth_override_scope(app), TestClient(app)


def test_list_samples_returns_items_total_and_request_id(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            "/admin/data-flywheel/samples",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["sample_id"] == _sample_id(turn)
    assert data["items"][0]["request_id"] == "adminfly"
    assert data["items"][0]["quality_labels"] == []
    assert data["items"][0]["issue_candidates"][0]["type"] == "pending_missed"

    with auth_override_scope(app):
        q_resp = client.get(
            "/admin/data-flywheel/samples?q=sess-admin-flywheel",
            headers=admin_headers(),
        )
    assert q_resp.status_code == 200
    assert q_resp.json()["total"] == 1


def test_add_label_uses_current_admin_as_annotator(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/labels",
            json={"label": "wrong_tool_selection", "comment": "工具选择不准"},
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["sample_id"] == sample_id
    assert data["label"] == "wrong_tool_selection"
    assert data["comment"] == "工具选择不准"
    assert data["annotator_id"] == ADMIN_USER_ID
    row = db_session.query(AgentDataFlywheelLabel).filter_by(sample_id=sample_id).one()
    assert row.annotator_id == ADMIN_USER_ID


def test_get_sample_detail_returns_labels_router_decision_and_messages(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    auth_scope, client = _admin_client()
    with auth_scope:
        client.post(
            f"/admin/data-flywheel/samples/{sample_id}/labels",
            json={"label": "needs_regression"},
            headers=admin_headers(),
        )
        resp = client.get(
            f"/admin/data-flywheel/samples/{sample_id}",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["sample"]["quality_labels"] == ["needs_regression"]
    assert data["router_decision"]["selected_tools"] == [
        "manage_workers",
        "create_operation_work_order",
    ]
    assert data["messages"] == [
        {
            "id": data["messages"][0]["id"],
            "role": "user",
            "content": "王大妈工资100一天，去5号棚收水稻",
        },
        {
            "id": data["messages"][1]["id"],
            "role": "assistant",
            "content": "已安排王大妈去5号棚收水稻",
        },
    ]
    assert data["issue_candidates"][0]["suggested_label"] == "pending_missed"


def test_get_session_review_returns_session_turns_for_admin(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            "/admin/data-flywheel/sessions/sess-admin-flywheel/review",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "sess-admin-flywheel"
    assert data["turns"][0]["sample"]["sample_id"] == _sample_id(turn)
    assert data["turns"][0]["messages"][0]["content"] == (
        "王大妈工资100一天，去5号棚收水稻"
    )
    assert data["turns"][0]["router_decision"]["selected_tools"] == [
        "manage_workers",
        "create_operation_work_order",
    ]
    assert data["turns"][0]["pending_lifecycle"][0]["event_type"] == (
        "pending.plan.created"
    )


def test_export_jsonl_returns_content_ending_with_newline(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            "/admin/data-flywheel/export-jsonl",
            json={"sample_id": sample_id},
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["content"].endswith("\n")
    payload = json.loads(data["content"].splitlines()[0])
    assert payload["sample_id"] == sample_id


def test_build_case_draft_returns_source_sample_metadata(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/case-draft",
            json={"target_type": "evaluation_replay"},
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"
    assert data["created_by"] == ADMIN_USER_ID
    assert data["case_json"]["metadata"]["source_sample_id"] == sample_id


def test_invalid_label_returns_code_detail(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/labels",
            json={"label": "unknown_label"},
            headers=admin_headers(),
        )

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_LABEL"


def test_missing_sample_returns_code_detail(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            f"/admin/data-flywheel/samples/turn:{turn.farm_id}:"
            "sess-admin-flywheel:999999",
            headers=admin_headers(),
        )

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "SAMPLE_NOT_FOUND"


def test_sync_sessions_schedules_background_job_by_default(
    db_session, tmp_path, monkeypatch
) -> None:
    ensure_admin_user(db_session)
    farm = db_session.query(Farm).filter(Farm.user_id == ADMIN_USER_ID).one()
    calls = []

    def fake_run_job(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(admin_data_flywheel_api, "AGENT_EVENT_BASE_DIR", tmp_path)
    monkeypatch.setattr(admin_data_flywheel_api, "run_session_events_sync_job", fake_run_job)

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            "/admin/data-flywheel/sync-sessions",
            json={"session_id": "sess-admin-db-only"},
            headers=admin_headers(),
        )
        status_resp = client.get(
            f"/admin/data-flywheel/sync-sessions/{resp.json()['job_id']}",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    assert resp.json()["mode"] == "background"
    assert resp.json()["session_id"] == "sess-admin-db-only"
    assert status_resp.status_code == 200
    assert status_resp.json()["job_id"] == resp.json()["job_id"]
    assert status_resp.json()["status"] == "queued"
    assert calls[0]["farm_id"] == farm.id
    assert calls[0]["session_id"] == "sess-admin-db-only"
    assert calls[0]["event_base_dir"] == tmp_path
