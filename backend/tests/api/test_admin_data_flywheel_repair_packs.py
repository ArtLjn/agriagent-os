"""Admin 数据飞轮 repair pack API 测试。"""

import shutil
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.infra.agent_events import AgentEventWriter
from app.main import app
from app.models.data_flywheel import AgentDataFlywheelLabel, AgentRepairPack
from app.models.farm import Farm
from app.services.agent_turn_service import create_turn, finish_turn, mark_event_range
from app.services.conversation_service import get_or_create_conversation, save_message
from app.platforms.data_flywheel.service import add_sample_label
from tests.api.auth_helpers import (
    ADMIN_USER_ID,
    admin_headers,
    auth_override_scope,
    ensure_admin_user,
)


def _seed_turn(db, tmp_path):
    ensure_admin_user(db)
    farm = db.query(Farm).filter(Farm.user_id == ADMIN_USER_ID).one()
    session_id = "sess-admin-flywheel-repair"
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
        request_id="adminfly-repair",
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
            request_id="adminfly-repair",
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
    return f"turn:{turn.farm_id}:sess-admin-flywheel-repair:{turn.id}"


def _admin_client():
    return auth_override_scope(app), TestClient(app)


def test_list_repair_packs_returns_paginated_items(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(
        db_session, farm_id=turn.farm_id, sample_id=sample_id, label="pending_missed"
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        create_resp = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [sample_id]},
            headers=admin_headers(),
        )
        list_resp = client.get(
            "/admin/data-flywheel/repair-packs",
            headers=admin_headers(),
        )

    assert create_resp.status_code == 200
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["items"][0]["pack_id"] == create_resp.json()["pack_id"]
    assert data["items"][0]["status"] == "exported"
    assert data["items"][0]["dedup_key"]


def test_create_repair_pack_response_includes_deduplicated_flag(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(
        db_session, farm_id=turn.farm_id, sample_id=sample_id, label="pending_missed"
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        first = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [sample_id]},
            headers=admin_headers(),
        )
        second = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [sample_id]},
            headers=admin_headers(),
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["pack_id"] == first.json()["pack_id"]
    assert second.json()["deduplicated"] is True
    assert second.json()["dedup_existing_pack_id"] == first.json()["pack_id"]
    assert db_session.query(AgentRepairPack).count() == 1


def test_discard_and_reopen_repair_pack(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(
        db_session, farm_id=turn.farm_id, sample_id=sample_id, label="pending_missed"
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        create_resp = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [sample_id]},
            headers=admin_headers(),
        )
        pack_id = create_resp.json()["pack_id"]
        discard_resp = client.post(
            f"/admin/data-flywheel/repair-packs/{pack_id}/discard",
            json={"reason": "duplicate"},
            headers=admin_headers(),
        )
        default_list = client.get(
            "/admin/data-flywheel/repair-packs",
            headers=admin_headers(),
        )
        include_list = client.get(
            "/admin/data-flywheel/repair-packs?include_discarded=true",
            headers=admin_headers(),
        )
        reopen_resp = client.post(
            f"/admin/data-flywheel/repair-packs/{pack_id}/reopen",
            headers=admin_headers(),
        )

    assert discard_resp.status_code == 200
    assert discard_resp.json()["status"] == "discarded"
    assert discard_resp.json()["repair_note"] == "duplicate"
    assert default_list.json()["total"] == 0
    assert include_list.json()["total"] == 1
    assert reopen_resp.status_code == 200
    assert reopen_resp.json()["status"] == "exported"


def test_list_repair_packs_status_filter(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(
        db_session, farm_id=turn.farm_id, sample_id=sample_id, label="pending_missed"
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        create_resp = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [sample_id]},
            headers=admin_headers(),
        )
        pack_id = create_resp.json()["pack_id"]
        client.post(
            f"/admin/data-flywheel/repair-packs/{pack_id}/resolve",
            json={"repair_note": "ok"},
            headers=admin_headers(),
        )
        exported_resp = client.get(
            "/admin/data-flywheel/repair-packs?status=exported",
            headers=admin_headers(),
        )
        resolved_resp = client.get(
            "/admin/data-flywheel/repair-packs?status=resolved",
            headers=admin_headers(),
        )

    assert exported_resp.json()["total"] == 0
    assert resolved_resp.json()["total"] == 1
    assert resolved_resp.json()["items"][0]["status"] == "resolved"


def test_resolve_repair_pack_marks_labels_resolved(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(
        db_session, farm_id=turn.farm_id, sample_id=sample_id, label="pending_missed"
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        create_resp = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [sample_id]},
            headers=admin_headers(),
        )
        pack_id = create_resp.json()["pack_id"]
        resolve_resp = client.post(
            f"/admin/data-flywheel/repair-packs/{pack_id}/resolve",
            json={"repair_note": "done"},
            headers=admin_headers(),
        )

    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "resolved"
    label = db_session.query(AgentDataFlywheelLabel).one()
    assert label.status == "resolved"


def test_rebuild_repair_pack_endpoint_restores_cleaned_data(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(
        db_session, farm_id=turn.farm_id, sample_id=sample_id, label="pending_missed"
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        create_resp = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [sample_id]},
            headers=admin_headers(),
        )
        pack_id = create_resp.json()["pack_id"]
        pack_dir = Path(create_resp.json()["export_path"])
        shutil.rmtree(pack_dir)
        rebuild_resp = client.post(
            f"/admin/data-flywheel/repair-packs/{pack_id}/rebuild",
            headers=admin_headers(),
        )

    assert rebuild_resp.status_code == 200
    assert rebuild_resp.json()["pack_id"] == pack_id
    assert rebuild_resp.json()["cases"][0]["sample_id"] == sample_id
    assert rebuild_resp.json()["manifest"]["asset_path"] == "compatibility_debug"
    assert rebuild_resp.json()["manifest"]["formal_review_required"] is True
    assert (pack_dir / "manifest.json").exists()
    assert (pack_dir / "cases.jsonl").exists()
    rebuilt_manifest = json.loads((pack_dir / "manifest.json").read_text())
    assert rebuilt_manifest["asset_path"] == "compatibility_debug"
    assert rebuilt_manifest["formal_review_required"] is True


def test_sample_repair_pack_is_marked_compatibility_debug(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(
        db_session, farm_id=turn.farm_id, sample_id=sample_id, label="pending_missed"
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        create_resp = client.post(
            "/admin/data-flywheel/repair-packs",
            json={"sample_ids": [sample_id]},
            headers=admin_headers(),
        )
        detail_resp = client.get(
            f"/admin/data-flywheel/repair-packs/{create_resp.json()['pack_id']}",
            headers=admin_headers(),
        )

    assert create_resp.status_code == 200
    data = create_resp.json()
    assert data["manifest"]["asset_path"] == "compatibility_debug"
    assert data["manifest"]["formal_review_required"] is True
    assert "source_chain_ids" not in data["manifest"]
    assert data["payload"]["manifest"]["asset_path"] == "compatibility_debug"
    assert data["payload"]["manifest"]["formal_review_required"] is True
    assert detail_resp.status_code == 200
    assert detail_resp.json()["manifest"]["asset_path"] == "compatibility_debug"
    assert detail_resp.json()["manifest"]["formal_review_required"] is True
