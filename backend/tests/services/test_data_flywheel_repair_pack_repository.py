"""数据飞轮 repair pack 数据库编排服务测试。"""

import shutil

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.shared.database import Base
from app.infra.agent_events import AgentEventWriter
from app.platforms.data_flywheel.models import AgentDataFlywheelLabel, AgentRepairPack
from app.domains.farm.models import Farm
from app.agent.turn_service import create_turn, finish_turn, mark_event_range
from app.domains.conversation.service import get_or_create_conversation, save_message
from app.platforms.data_flywheel.repair_pack_repository import (
    _compute_dedup_key,
    create_repair_pack,
    get_repair_pack,
    list_repair_candidates,
    list_repair_packs,
    mark_repair_pack_discarded,
    mark_repair_pack_exported,
    mark_repair_pack_resolved,
    rebuild_repair_pack_files,
    record_repair_pack_verification_failure,
)
from app.platforms.data_flywheel.service import add_sample_label, get_sample_detail

pytestmark = pytest.mark.no_db


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_data_flywheel_repair_pack_repository.db",
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
    session_id="sess-repair-pack",
    request_id="repair001",
    router_tools=None,
    include_pending=False,
):
    router_tools = router_tools or ["create_operation_work_order"]
    user_input = "王大妈去5号棚收水稻"
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
        ("message.user", {"content": user_input}),
        ("router.decision", {"selected_tools": router_tools, "fallback": False}),
        (
            "tool.call.finished",
            {"tool_name": router_tools[0], "result": {"id": 7}},
        ),
    ]
    if include_pending:
        event_specs.append(
            (
                "pending.plan.created",
                {"plan_id": "plan-1", "steps": [{"skill_name": router_tools[0]}]},
            )
        )
    event_specs.append(("message.assistant", {"content": assistant_reply}))
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
        tool_calls_count=1,
        token_total=100,
        latency_ms=200,
        status="success",
        pending_plan_id="plan-1" if include_pending else None,
    )
    return mark_event_range(
        db,
        turn.id,
        event_file=writes[0].event_file,
        seq_start=writes[0].seq,
        seq_end=writes[-1].seq,
        write_status="success",
    )


def _sample_id(turn) -> str:
    return f"turn:{turn.farm_id}:{turn.session_id}:{turn.id}"


def test_list_repair_candidates_derives_fix_target_from_labels(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="pending_missed")

    result = list_repair_candidates(db, farm_id=1, label="pending_missed")

    assert result["total"] == 1
    assert result["items"][0]["sample_id"] == sample_id
    assert result["items"][0]["fix_target"] == "pending_plan"
    assert result["items"][0]["priority"] == 90
    db.close()


def test_create_repair_pack_persists_metadata_and_payload(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="pending_missed")

    pack = create_repair_pack(
        db,
        farm_id=1,
        sample_ids=[sample_id],
        export_base_dir=tmp_path / "repair-packs",
        created_by="admin-1",
    )
    loaded = get_repair_pack(db, farm_id=1, pack_id=pack["pack_id"])

    assert pack["status"] == "exported"
    assert pack["fix_target"] == "pending_plan"
    assert pack["source_sample_ids"] == [sample_id]
    assert pack["source_label_ids"]
    assert pack["payload"]["manifest"]["pack_id"] == pack["pack_id"]
    assert pack["payload"]["cases_jsonl"][0]["source_debug_json"].startswith("debug/")
    assert (tmp_path / "repair-packs" / pack["pack_id"] / "manifest.json").exists()
    assert (tmp_path / "repair-packs" / pack["pack_id"] / "cases.jsonl").exists()
    assert (tmp_path / "repair-packs" / pack["pack_id"] / "README.md").exists()
    assert (
        tmp_path
        / "repair-packs"
        / pack["pack_id"]
        / pack["payload"]["cases_jsonl"][0]["source_debug_json"]
    ).exists()
    assert loaded["manifest"]["source_sample_ids"] == [sample_id]
    assert db.query(AgentRepairPack).count() == 1
    db.close()


def test_rebuild_repair_pack_files_restores_cleaned_local_export(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="pending_missed")
    export_base_dir = tmp_path / "repair-packs"
    pack = create_repair_pack(
        db,
        farm_id=1,
        sample_ids=[sample_id],
        export_base_dir=export_base_dir,
        created_by="admin-1",
    )
    pack_dir = export_base_dir / pack["pack_id"]
    shutil.rmtree(pack_dir)

    rebuilt = rebuild_repair_pack_files(
        db,
        farm_id=1,
        pack_id=pack["pack_id"],
        export_base_dir=export_base_dir,
    )

    assert rebuilt["pack_id"] == pack["pack_id"]
    assert rebuilt["status"] == "exported"
    assert rebuilt["manifest"]["dedup_key"] == pack["dedup_key"]
    assert rebuilt["cases"][0]["sample_id"] == sample_id
    assert (pack_dir / "manifest.json").exists()
    assert (pack_dir / "cases.jsonl").exists()
    assert (pack_dir / "README.md").exists()
    assert (pack_dir / rebuilt["cases"][0]["source_debug_json"]).exists()
    db.close()


def test_create_repair_pack_rejects_mixed_fix_targets(tmp_path):
    db = Session()
    first = _seed_turn(db, tmp_path, session_id="sess-a", request_id="req-a")
    second = _seed_turn(
        db,
        tmp_path,
        session_id="sess-b",
        request_id="req-b",
        include_pending=True,
    )
    first_id = _sample_id(first)
    second_id = _sample_id(second)
    add_sample_label(db, farm_id=1, sample_id=first_id, label="pending_missed")
    add_sample_label(db, farm_id=1, sample_id=second_id, label="wrong_tool_selection")

    with pytest.raises(ValueError) as exc:
        create_repair_pack(
            db,
            farm_id=1,
            sample_ids=[first_id, second_id],
            export_base_dir=tmp_path / "repair-packs",
        )

    assert exc.value.args[0]["code"] == "MIXED_FIX_TARGETS"
    assert sorted(exc.value.args[0]["groups"]) == ["pending_plan", "router"]
    db.close()


def test_create_repair_pack_allows_manual_fix_target_override(tmp_path):
    db = Session()
    first = _seed_turn(db, tmp_path, session_id="sess-a", request_id="req-a")
    second = _seed_turn(
        db,
        tmp_path,
        session_id="sess-b",
        request_id="req-b",
        include_pending=True,
    )
    first_id = _sample_id(first)
    second_id = _sample_id(second)
    add_sample_label(db, farm_id=1, sample_id=first_id, label="pending_missed")
    add_sample_label(db, farm_id=1, sample_id=second_id, label="wrong_tool_selection")

    pack = create_repair_pack(
        db,
        farm_id=1,
        sample_ids=[first_id, second_id],
        export_base_dir=tmp_path / "repair-packs",
        fix_target_override="router",
    )

    assert pack["fix_target"] == "router"
    assert pack["pack_id"].startswith("repair-router-")
    assert pack["source_sample_ids"] == [first_id, second_id]
    assert {case["fix_target"] for case in pack["payload"]["cases_jsonl"]} == {"router"}
    db.close()


def test_list_repair_candidates_filters_by_min_priority(tmp_path):
    db = Session()
    first = _seed_turn(db, tmp_path, session_id="sess-a", request_id="req-a")
    second = _seed_turn(db, tmp_path, session_id="sess-b", request_id="req-b")
    first_id = _sample_id(first)
    second_id = _sample_id(second)
    add_sample_label(db, farm_id=1, sample_id=first_id, label="bad_reply")
    add_sample_label(db, farm_id=1, sample_id=second_id, label="sensitive_info_leak")

    result = list_repair_candidates(db, farm_id=1, min_priority=95, limit=10)

    assert result["total"] == 1
    assert result["items"][0]["sample_id"] == second_id
    assert result["items"][0]["priority"] == 100
    db.close()


def test_mark_repair_pack_resolved_resolves_associated_open_labels(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="pending_missed")
    pack = create_repair_pack(
        db,
        farm_id=1,
        sample_ids=[sample_id],
        export_base_dir=tmp_path / "repair-packs",
    )
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="wrong_tool_selection")

    resolved = mark_repair_pack_resolved(
        db,
        farm_id=1,
        pack_id=pack["pack_id"],
        repair_note="已补 pending plan 回归",
        verification_summary={"passed": True},
        resolved_by="admin-1",
    )
    detail = get_sample_detail(db, farm_id=1, sample_id=sample_id)

    assert resolved["status"] == "resolved"
    assert resolved["repair_note"] == "已补 pending plan 回归"
    assert detail["quality_labels"] == ["wrong_tool_selection"]
    statuses = {
        row.label: row.status
        for row in db.query(AgentDataFlywheelLabel).order_by(
            AgentDataFlywheelLabel.id.asc()
        )
    }
    assert statuses == {
        "pending_missed": "resolved",
        "wrong_tool_selection": "open",
    }
    db.close()


def test_record_verification_failure_keeps_labels_open(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="pending_missed")
    pack = create_repair_pack(
        db,
        farm_id=1,
        sample_ids=[sample_id],
        export_base_dir=tmp_path / "repair-packs",
    )

    failed = record_repair_pack_verification_failure(
        db,
        farm_id=1,
        pack_id=pack["pack_id"],
        verification_summary={"passed": False, "failed_assertions": ["pending"]},
    )

    assert failed["status"] == "verification_failed"
    assert failed["verification_summary"]["passed"] is False
    assert db.query(AgentDataFlywheelLabel).one().status == "open"
    db.close()


def test_create_repair_pack_records_export_failed_metadata(tmp_path, monkeypatch):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="pending_missed")

    def fail_write(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(
        "app.platforms.data_flywheel.repair_pack_repository._write_repair_pack_files",
        fail_write,
    )

    with pytest.raises(ValueError, match="REPAIR_PACK_EXPORT_FAILED"):
        create_repair_pack(
            db,
            farm_id=1,
            sample_ids=[sample_id],
            export_base_dir=tmp_path / "repair-packs",
        )

    row = db.query(AgentRepairPack).one()
    assert row.status == "export_failed"
    assert row.export_error == "disk full"
    assert row.source_sample_ids == [sample_id]
    assert row.source_label_ids
    db.close()


def test_compute_dedup_key_is_deterministic():
    kwargs = {
        "farm_id": 1,
        "fix_target": "router",
        "source_sample_ids": ["turn:1:sess-a:1", "turn:1:sess-b:2"],
        "labels": ["bad_reply", "sensitive_info_leak"],
    }
    assert _compute_dedup_key(**kwargs) == _compute_dedup_key(**kwargs)


def test_compute_dedup_key_ignores_input_order():
    first = _compute_dedup_key(
        farm_id=1,
        fix_target="router",
        source_sample_ids=["a", "b"],
        labels=["x", "y"],
    )
    second = _compute_dedup_key(
        farm_id=1,
        fix_target="router",
        source_sample_ids=["b", "a"],
        labels=["y", "x"],
    )
    assert first == second


def test_compute_dedup_key_normalizes_fix_target():
    upper = _compute_dedup_key(
        farm_id=1,
        fix_target="Router ",
        source_sample_ids=["a"],
        labels=[],
    )
    lower = _compute_dedup_key(
        farm_id=1,
        fix_target="router",
        source_sample_ids=["a"],
        labels=[],
    )
    assert upper == lower


def test_create_repair_pack_returns_existing_on_duplicate(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="pending_missed")

    first = create_repair_pack(
        db,
        farm_id=1,
        sample_ids=[sample_id],
        export_base_dir=tmp_path / "repair-packs",
    )
    second = create_repair_pack(
        db,
        farm_id=1,
        sample_ids=[sample_id],
        export_base_dir=tmp_path / "repair-packs",
    )

    assert second["pack_id"] == first["pack_id"]
    assert second.get("deduplicated") is True
    assert second.get("dedup_existing_pack_id") == first["pack_id"]
    assert db.query(AgentRepairPack).count() == 1
    db.close()


def test_create_repair_pack_rebuilds_after_discard(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="pending_missed")

    first = create_repair_pack(
        db,
        farm_id=1,
        sample_ids=[sample_id],
        export_base_dir=tmp_path / "repair-packs",
    )
    mark_repair_pack_discarded(
        db,
        farm_id=1,
        pack_id=first["pack_id"],
        resolved_by="admin-1",
        reason="duplicate",
    )
    rebuilt = create_repair_pack(
        db,
        farm_id=1,
        sample_ids=[sample_id],
        export_base_dir=tmp_path / "repair-packs",
    )

    assert rebuilt["pack_id"] != first["pack_id"]
    assert rebuilt.get("deduplicated") is not True
    rows = db.query(AgentRepairPack).order_by(AgentRepairPack.id.asc()).all()
    assert [row.status for row in rows] == ["discarded", "exported"]
    db.close()


def test_list_repair_packs_filters_discarded_by_default(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="pending_missed")
    pack = create_repair_pack(
        db,
        farm_id=1,
        sample_ids=[sample_id],
        export_base_dir=tmp_path / "repair-packs",
    )
    mark_repair_pack_discarded(db, farm_id=1, pack_id=pack["pack_id"])

    default_result = list_repair_packs(db, farm_id=1)
    include_result = list_repair_packs(db, farm_id=1, include_discarded=True)

    assert default_result["total"] == 0
    assert default_result["items"] == []
    assert include_result["total"] == 1
    assert include_result["items"][0]["pack_id"] == pack["pack_id"]
    db.close()


def test_list_repair_packs_pagination_and_status_filter(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="pending_missed")
    pack = create_repair_pack(
        db,
        farm_id=1,
        sample_ids=[sample_id],
        export_base_dir=tmp_path / "repair-packs",
    )
    mark_repair_pack_resolved(
        db,
        farm_id=1,
        pack_id=pack["pack_id"],
        resolved_by="admin-1",
        repair_note="ok",
    )

    page1 = list_repair_packs(db, farm_id=1, page=1, page_size=10)
    filtered = list_repair_packs(db, farm_id=1, status="resolved")
    empty = list_repair_packs(db, farm_id=1, status="exported")

    assert page1["total"] == 1
    assert page1["page"] == 1
    assert page1["page_size"] == 10
    assert filtered["total"] == 1
    assert empty["total"] == 0
    db.close()


def test_mark_repair_pack_exported_restores_status(tmp_path):
    db = Session()
    turn = _seed_turn(db, tmp_path)
    sample_id = _sample_id(turn)
    add_sample_label(db, farm_id=1, sample_id=sample_id, label="pending_missed")
    pack = create_repair_pack(
        db,
        farm_id=1,
        sample_ids=[sample_id],
        export_base_dir=tmp_path / "repair-packs",
    )
    mark_repair_pack_resolved(
        db,
        farm_id=1,
        pack_id=pack["pack_id"],
        resolved_by="admin-1",
    )
    reopened = mark_repair_pack_exported(db, farm_id=1, pack_id=pack["pack_id"])

    assert reopened["status"] == "exported"
    db.close()
