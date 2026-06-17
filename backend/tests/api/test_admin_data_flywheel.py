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


class FakeJudgeClient:
    judge_model = "fake-judge"
    prompt_version = "data-flywheel-prelabel-v1"

    def __init__(self):
        self.calls = []

    def judge(self, payload):
        self.calls.append(payload)
        return {
            "labels": ["bad_reply", "pending_missed"],
            "root_cause": "缺少 pending 确认",
            "severity": "high",
            "confidence": 0.91,
            "reason": "回复声称已安排，但证据中缺少写操作确认链路。",
            "recommended_fix": "补齐 pending 确认后再执行写工具。",
        }


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


def test_add_session_label_and_delete_label_by_id(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = f"session:{turn.farm_id}:sess-admin-flywheel"

    auth_scope, client = _admin_client()
    with auth_scope:
        create_resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/labels",
            json={
                "label": "needs_regression",
                "sample_type": "session",
                "session_id": "sess-admin-flywheel",
                "comment": "整段会话需要回归",
            },
            headers=admin_headers(),
        )
        detail_resp = client.get(
            "/admin/data-flywheel/sessions/sess-admin-flywheel/annotations",
            headers=admin_headers(),
        )
        resolve_resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/labels/"
            f"{create_resp.json()['id']}/resolve",
            headers=admin_headers(),
        )
        resolved_detail_resp = client.get(
            "/admin/data-flywheel/sessions/sess-admin-flywheel/annotations",
            headers=admin_headers(),
        )
        delete_resp = client.delete(
            f"/admin/data-flywheel/samples/{sample_id}/labels/"
            f"{create_resp.json()['id']}",
            headers=admin_headers(),
        )

    assert create_resp.status_code == 200
    assert create_resp.json()["sample_type"] == "session"
    assert create_resp.json()["turn_id"] is None
    assert create_resp.json()["status"] == "open"
    assert detail_resp.status_code == 200
    assert detail_resp.json()["quality_labels"] == ["needs_regression"]
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "resolved"
    assert resolved_detail_resp.status_code == 200
    assert resolved_detail_resp.json()["quality_labels"] == []
    assert resolved_detail_resp.json()["labels"][0]["status"] == "resolved"
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"deleted": True, "id": create_resp.json()["id"]}
    assert (
        db_session.query(AgentDataFlywheelLabel).filter_by(sample_id=sample_id).count()
        == 0
    )


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


def test_build_case_draft_api_returns_issue_candidate_assertions(
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
        resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/case-draft",
            json={"target_type": "evaluation_replay"},
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["case_json"]["metadata"]["issue_candidates"] == [
        {
            "type": "pending_missed",
            "severity": "high",
            "reason": "router 选择了写操作工具，但 pending lifecycle 中没有对应的确认计划",
            "evidence": "create_operation_work_order",
            "suggested_label": "pending_missed",
        }
    ]
    assert data["case_json"]["issue_assertions"] == [
        {
            "type": "pending_missed",
            "expected": "写操作必须先创建 pending plan，用户确认后才能执行",
            "evidence": "create_operation_work_order",
        }
    ]


def test_list_repair_candidates_returns_fix_target(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)

    auth_scope, client = _admin_client()
    with auth_scope:
        client.post(
            f"/admin/data-flywheel/samples/{sample_id}/labels",
            json={"label": "pending_missed"},
            headers=admin_headers(),
        )
        resp = client.get(
            "/admin/data-flywheel/repair-candidates?label=pending_missed",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["sample_id"] == sample_id
    assert data["items"][0]["fix_target"] == "pending_plan"
    assert data["items"][0]["priority"] == 90
    assert data["items"][0]["verification_commands"]


def test_list_repair_candidates_accepts_explicit_sample_ids(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)

    auth_scope, client = _admin_client()
    with auth_scope:
        client.post(
            f"/admin/data-flywheel/samples/{sample_id}/labels",
            json={"label": "sensitive_info_leak"},
            headers=admin_headers(),
        )
        resp = client.get(
            "/admin/data-flywheel/repair-candidates",
            params={"sample_ids": sample_id},
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["sample_id"] == sample_id
    assert data["items"][0]["fix_target"] == "guardrail"


def test_list_repair_candidates_filters_by_min_priority(db_session, tmp_path) -> None:
    first = _seed_turn(db_session, tmp_path)
    second = _seed_turn(db_session, tmp_path)
    second.session_id = "sess-admin-flywheel-2"
    second.request_id = "adminfly2"
    db_session.commit()
    first_id = _sample_id(first)
    second_id = f"turn:{second.farm_id}:sess-admin-flywheel-2:{second.id}"

    auth_scope, client = _admin_client()
    with auth_scope:
        client.post(
            f"/admin/data-flywheel/samples/{first_id}/labels",
            json={"label": "bad_reply"},
            headers=admin_headers(),
        )
        client.post(
            f"/admin/data-flywheel/samples/{second_id}/labels",
            json={"label": "sensitive_info_leak"},
            headers=admin_headers(),
        )
        resp = client.get(
            "/admin/data-flywheel/repair-candidates?min_priority=95",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["sample_id"] == second_id
    assert data["items"][0]["priority"] == 100


def test_create_repair_pack_returns_payload_and_metadata(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    auth_scope, client = _admin_client()
    with auth_scope:
        client.post(
            f"/admin/data-flywheel/samples/{sample_id}/labels",
            json={"label": "pending_missed"},
            headers=admin_headers(),
        )
        resp = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [sample_id]},
            headers=admin_headers(),
        )
        detail_resp = client.get(
            f"/admin/data-flywheel/repair-packs/{resp.json()['pack_id']}",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "exported"
    assert data["created_by"] == ADMIN_USER_ID
    assert data["fix_target"] == "pending_plan"
    assert data["source_sample_ids"] == [sample_id]
    assert data["source_label_ids"]
    assert data["payload"]["manifest"]["pack_id"] == data["pack_id"]
    assert data["payload"]["cases_jsonl"][0]["source_debug_json"].startswith("debug/")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["manifest"]["source_sample_ids"] == [sample_id]


def test_create_repair_pack_rejects_mixed_fix_targets(
    db_session, tmp_path
) -> None:
    first = _seed_turn(db_session, tmp_path)
    second = _seed_turn(db_session, tmp_path)
    second.session_id = "sess-admin-flywheel-2"
    second.request_id = "adminfly2"
    db_session.commit()
    first_id = _sample_id(first)
    second_id = f"turn:{second.farm_id}:sess-admin-flywheel-2:{second.id}"
    auth_scope, client = _admin_client()
    with auth_scope:
        client.post(
            f"/admin/data-flywheel/samples/{first_id}/labels",
            json={"label": "pending_missed"},
            headers=admin_headers(),
        )
        client.post(
            f"/admin/data-flywheel/samples/{second_id}/labels",
            json={"label": "sensitive_info_leak"},
            headers=admin_headers(),
        )
        resp = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [first_id, second_id]},
            headers=admin_headers(),
        )

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "MIXED_FIX_TARGETS"
    assert sorted(resp.json()["detail"]["groups"]) == ["guardrail", "pending_plan"]


def test_create_repair_pack_accepts_manual_fix_target_override(
    db_session, tmp_path
) -> None:
    first = _seed_turn(db_session, tmp_path)
    second = _seed_turn(db_session, tmp_path)
    second.session_id = "sess-admin-flywheel-2"
    second.request_id = "adminfly2"
    db_session.commit()
    first_id = _sample_id(first)
    second_id = f"turn:{second.farm_id}:sess-admin-flywheel-2:{second.id}"
    auth_scope, client = _admin_client()
    with auth_scope:
        client.post(
            f"/admin/data-flywheel/samples/{first_id}/labels",
            json={"label": "pending_missed"},
            headers=admin_headers(),
        )
        client.post(
            f"/admin/data-flywheel/samples/{second_id}/labels",
            json={"label": "sensitive_info_leak"},
            headers=admin_headers(),
        )
        resp = client.post(
            "/admin/data-flywheel/repair-packs",
            json={
                "sample_ids": [first_id, second_id],
                "fix_target_override": "router",
            },
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["fix_target"] == "router"
    assert data["pack_id"].startswith("repair-router-")
    assert {case["fix_target"] for case in data["payload"]["cases_jsonl"]} == {
        "router"
    }


def test_resolve_repair_pack_marks_labels_resolved(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    auth_scope, client = _admin_client()
    with auth_scope:
        client.post(
            f"/admin/data-flywheel/samples/{sample_id}/labels",
            json={"label": "pending_missed"},
            headers=admin_headers(),
        )
        pack_resp = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [sample_id]},
            headers=admin_headers(),
        )
        resolve_resp = client.post(
            f"/admin/data-flywheel/repair-packs/{pack_resp.json()['pack_id']}/resolve",
            json={
                "repair_note": "已修复 pending plan",
                "verification_summary": {"passed": True},
            },
            headers=admin_headers(),
        )
        sample_resp = client.get(
            f"/admin/data-flywheel/samples/{sample_id}",
            headers=admin_headers(),
        )

    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "resolved"
    assert resolve_resp.json()["resolved_by"] == ADMIN_USER_ID
    assert sample_resp.json()["quality_labels"] == []
    assert sample_resp.json()["labels"][0]["status"] == "resolved"


def test_verification_failure_keeps_repair_pack_labels_open(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    auth_scope, client = _admin_client()
    with auth_scope:
        client.post(
            f"/admin/data-flywheel/samples/{sample_id}/labels",
            json={"label": "pending_missed"},
            headers=admin_headers(),
        )
        pack_resp = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [sample_id]},
            headers=admin_headers(),
        )
        fail_resp = client.post(
            "/admin/data-flywheel/repair-packs/"
            f"{pack_resp.json()['pack_id']}/verification-failed",
            json={"verification_summary": {"passed": False}},
            headers=admin_headers(),
        )
        sample_resp = client.get(
            f"/admin/data-flywheel/samples/{sample_id}",
            headers=admin_headers(),
        )

    assert fail_resp.status_code == 200
    assert fail_resp.json()["status"] == "verification_failed"
    assert sample_resp.json()["quality_labels"] == ["pending_missed"]


def test_prelabel_endpoint_is_disabled_by_default(
    db_session, tmp_path, monkeypatch
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    calls = []

    def forbidden_factory():
        calls.append("called")
        return FakeJudgeClient()

    monkeypatch.setattr(
        admin_data_flywheel_api.settings.data_flywheel,
        "llm_prelabel_enabled",
        False,
    )
    monkeypatch.setattr(
        admin_data_flywheel_api,
        "build_data_flywheel_judge_client",
        forbidden_factory,
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/prelabel",
            headers=admin_headers(),
        )

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "LLM_PRELABEL_DISABLED"
    assert calls == []


def test_prelabel_endpoint_creates_pending_llm_judge_prelabel(
    db_session, tmp_path, monkeypatch
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    fake_client = FakeJudgeClient()

    monkeypatch.setattr(
        admin_data_flywheel_api.settings.data_flywheel,
        "llm_prelabel_enabled",
        True,
    )
    monkeypatch.setattr(
        admin_data_flywheel_api,
        "build_data_flywheel_judge_client",
        lambda: fake_client,
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/prelabel",
            headers=admin_headers(),
        )
        detail_resp = client.get(
            f"/admin/data-flywheel/samples/{sample_id}",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "llm_judge"
    assert data["status"] == "pending"
    assert data["labels"] == ["bad_reply", "pending_missed"]
    assert len(fake_client.calls) == 1
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["quality_labels"] == []
    assert detail["prelabels"][0]["id"] == data["id"]
    assert detail["prelabels"][0]["status"] == "pending"


def test_batch_prelabel_inline_creates_pending_prelabels_without_human_labels(
    db_session, tmp_path, monkeypatch
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    fake_client = FakeJudgeClient()

    monkeypatch.setattr(
        admin_data_flywheel_api.settings.data_flywheel,
        "llm_prelabel_enabled",
        True,
    )
    monkeypatch.setattr(
        admin_data_flywheel_api,
        "build_data_flywheel_judge_client",
        lambda: fake_client,
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            "/admin/data-flywheel/prelabels/batch",
            json={"unannotated_only": True, "limit": 10, "run_inline": True},
            headers=admin_headers(),
        )
        detail_resp = client.get(
            f"/admin/data-flywheel/samples/{sample_id}",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "inline"
    assert data["status"] == "completed"
    assert data["result"]["total"] == 1
    assert data["result"]["created"] == 1
    assert data["result"]["skipped_existing"] == 0
    assert data["result"]["failed"] == 0
    assert data["result"]["items"][0]["sample_id"] == sample_id
    assert data["result"]["items"][0]["status"] == "created"
    assert len(fake_client.calls) == 1
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["quality_labels"] == []
    assert detail["prelabels"][0]["status"] == "pending"


def test_batch_prelabel_skips_samples_with_existing_prelabel(
    db_session, tmp_path, monkeypatch
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    fake_client = FakeJudgeClient()

    monkeypatch.setattr(
        admin_data_flywheel_api.settings.data_flywheel,
        "llm_prelabel_enabled",
        True,
    )
    monkeypatch.setattr(
        admin_data_flywheel_api,
        "build_data_flywheel_judge_client",
        lambda: fake_client,
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        first_resp = client.post(
            "/admin/data-flywheel/prelabels/batch",
            json={"unannotated_only": True, "limit": 10, "run_inline": True},
            headers=admin_headers(),
        )
        second_resp = client.post(
            "/admin/data-flywheel/prelabels/batch",
            json={"unannotated_only": True, "limit": 10, "run_inline": True},
            headers=admin_headers(),
        )

    assert first_resp.status_code == 200
    assert second_resp.status_code == 200
    assert second_resp.json()["result"]["created"] == 0
    assert second_resp.json()["result"]["skipped_existing"] == 1
    assert second_resp.json()["result"]["items"] == [
        {"sample_id": sample_id, "status": "skipped_existing"}
    ]
    assert len(fake_client.calls) == 1


def test_batch_prelabel_schedules_background_job(db_session, monkeypatch) -> None:
    ensure_admin_user(db_session)
    farm = db_session.query(Farm).filter(Farm.user_id == ADMIN_USER_ID).one()
    calls = []

    def fake_run_job(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(admin_data_flywheel_api, "run_prelabel_batch_job", fake_run_job)
    monkeypatch.setattr(
        admin_data_flywheel_api.settings.data_flywheel,
        "llm_prelabel_enabled",
        True,
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            "/admin/data-flywheel/prelabels/batch",
            json={"unannotated_only": True, "q": "sess-admin", "limit": 25},
            headers=admin_headers(),
        )
        status_resp = client.get(
            f"/admin/data-flywheel/prelabels/batch/{resp.json()['job_id']}",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    assert resp.json()["mode"] == "background"
    assert status_resp.status_code == 200
    assert status_resp.json()["job_id"] == resp.json()["job_id"]
    assert calls[0]["farm_id"] == farm.id
    assert calls[0]["q"] == "sess-admin"
    assert calls[0]["limit"] == 25


def test_build_prelabel_judge_client_uses_llm_manager(monkeypatch) -> None:
    class FakeManager:
        fallback_mode = False

        def get_sync_client_with_info(self, role):
            assert role == "generation"
            return object(), {"model": "judge-model"}

    monkeypatch.setattr(
        "app.core.llm_client_manager.get_llm_manager",
        lambda: FakeManager(),
    )

    judge_client = admin_data_flywheel_api.build_data_flywheel_judge_client()

    assert judge_client.judge_model == "judge-model"


def test_build_prelabel_judge_client_requires_config(monkeypatch) -> None:
    class FakeManager:
        fallback_mode = True

    monkeypatch.setattr(
        "app.core.llm_client_manager.get_llm_manager",
        lambda: FakeManager(),
    )
    monkeypatch.setattr(admin_data_flywheel_api.settings.ai, "api_key", "")

    try:
        admin_data_flywheel_api.build_data_flywheel_judge_client()
    except ValueError as exc:
        assert str(exc) == "JUDGE_CLIENT_NOT_CONFIGURED"
    else:
        raise AssertionError("missing judge config should raise")


def test_accept_prelabel_endpoint_supports_human_modified_labels(
    db_session, tmp_path, monkeypatch
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    fake_client = FakeJudgeClient()

    monkeypatch.setattr(
        admin_data_flywheel_api.settings.data_flywheel,
        "llm_prelabel_enabled",
        True,
    )
    monkeypatch.setattr(
        admin_data_flywheel_api,
        "build_data_flywheel_judge_client",
        lambda: fake_client,
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        prelabel_resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/prelabel",
            headers=admin_headers(),
        )
        accept_resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/prelabels/"
            f"{prelabel_resp.json()['id']}/accept",
            json={"labels": ["needs_regression"], "comment": "人工改为回归标签"},
            headers=admin_headers(),
        )
        detail_resp = client.get(
            f"/admin/data-flywheel/samples/{sample_id}",
            headers=admin_headers(),
        )

    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "accepted"
    assert accept_resp.json()["reviewed_by"] == ADMIN_USER_ID
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["quality_labels"] == ["needs_regression"]
    assert detail["prelabels"][0]["status"] == "accepted"
    assert detail["labels"][0]["comment"] == "人工改为回归标签"


def test_reject_prelabel_endpoint_does_not_write_quality_labels(
    db_session, tmp_path, monkeypatch
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    fake_client = FakeJudgeClient()

    monkeypatch.setattr(
        admin_data_flywheel_api.settings.data_flywheel,
        "llm_prelabel_enabled",
        True,
    )
    monkeypatch.setattr(
        admin_data_flywheel_api,
        "build_data_flywheel_judge_client",
        lambda: fake_client,
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        prelabel_resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/prelabel",
            headers=admin_headers(),
        )
        reject_resp = client.post(
            f"/admin/data-flywheel/samples/{sample_id}/prelabels/"
            f"{prelabel_resp.json()['id']}/reject",
            headers=admin_headers(),
        )
        detail_resp = client.get(
            f"/admin/data-flywheel/samples/{sample_id}",
            headers=admin_headers(),
        )

    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"
    assert reject_resp.json()["reviewed_by"] == ADMIN_USER_ID
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["quality_labels"] == []
    assert detail["prelabels"][0]["status"] == "rejected"


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
    monkeypatch.setattr(
        admin_data_flywheel_api, "run_session_events_sync_job", fake_run_job
    )

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
