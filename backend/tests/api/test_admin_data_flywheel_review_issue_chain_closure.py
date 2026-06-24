"""DataFlywheel 问题链回归与修复闭环 API 测试。"""

import json

from fastapi.testclient import TestClient
import pytest

from app.infra.agent_events import AgentEventWriter
from app.main import app
from app.models.data_flywheel import AgentCaseDraft
from app.models.farm import Farm
from app.services.agent_turn_service import create_turn, finish_turn, mark_event_range
from app.services.conversation_service import get_or_create_conversation, save_message
from tests.api.auth_helpers import (
    ADMIN_USER_ID,
    admin_headers,
    auth_override_scope,
    ensure_admin_user,
)


def _admin_client() -> tuple[object, TestClient]:
    return auth_override_scope(app), TestClient(app)


def _chain_id(turn) -> str:
    return f"chain:{turn.farm_id}:{turn.session_id}:{turn.id}"


def _sample_id(turn) -> str:
    return f"turn:{turn.farm_id}:{turn.session_id}:{turn.id}"


def _seed_turn(
    db,
    tmp_path,
    *,
    farm_id: int,
    session_id: str,
    request_id: str,
    user_input: str,
    assistant_reply: str,
    router_tools: list[str] | None = None,
    include_pending: bool = False,
    include_tool: bool = False,
):
    conv = get_or_create_conversation(
        db,
        farm_id=farm_id,
        session_id=session_id,
        user_id=ADMIN_USER_ID,
    )
    user_msg = save_message(db, conv.id, "user", user_input)
    turn = create_turn(
        db,
        farm_id=farm_id,
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

    router_tools = router_tools or []
    event_specs = [
        ("message.user", {"content": user_input}),
        ("router.decision", {"selected_tools": router_tools, "fallback": False}),
    ]
    if include_tool:
        event_specs.append(
            (
                "tool.call.finished",
                {
                    "tool_name": router_tools[0] if router_tools else "get_labor_payables",
                    "result": {"ok": True},
                },
            )
        )
    if include_pending:
        event_specs.append(
            (
                "pending.plan.created",
                {"plan_id": "plan-1", "steps": [{"skill_name": router_tools[0]}]},
            )
        )
    event_specs.append(("message.assistant", {"content": assistant_reply}))
    writer = AgentEventWriter(base_dir=tmp_path)
    writes = [
        writer.write(
            event_type=event_type,
            farm_id=farm_id,
            user_id=ADMIN_USER_ID,
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
        tool_calls_count=1 if include_tool else 0,
        token_total=520,
        latency_ms=900,
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


def _seed_reviewed_chain(db, tmp_path, *, expected_behavior: str | None = None):
    ensure_admin_user(db)
    farm = db.query(Farm).filter(Farm.user_id == ADMIN_USER_ID).one()
    session_id = "sess-chain-closure"
    context = _seed_turn(
        db,
        tmp_path,
        farm_id=farm.id,
        session_id=session_id,
        request_id="chainctx1",
        user_input="哪些人工还没结清？",
        assistant_reply="王大妈、李四还有未结工资。",
        router_tools=["get_labor_payables"],
        include_tool=True,
    )
    trigger = _seed_turn(
        db,
        tmp_path,
        farm_id=farm.id,
        session_id=session_id,
        request_id="chaintrg1",
        user_input="把这些人工都结清",
        assistant_reply="已为王大妈创建结算确认。",
        router_tools=["settle_labor_payment"],
        include_pending=True,
    )
    result = _seed_turn(
        db,
        tmp_path,
        farm_id=farm.id,
        session_id=session_id,
        request_id="chainres1",
        user_input="确认",
        assistant_reply="已结清王大妈工资。",
        router_tools=["settle_labor_payment"],
        include_tool=True,
    )
    trigger.risk_score = 0.96
    trigger.risk_severity = "P0"
    trigger.risk_dominant_signal = "rule"
    trigger.rule_hits = ["bulk_intent_narrowed_to_single_entity"]
    trigger.judge_issue_type = "tool_parameter_mismatch"
    trigger.judge_suggested_label = "wrong_tool_selection"
    db.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        payload = {
            "status": "accepted",
            "context_turn_ids": [context.id],
            "result_turn_ids": [result.id],
            "final_labels": ["needs_regression", "wrong_tool_selection"],
            "root_cause": "批量结算意图被参数抽取收窄为单个工人",
            "expected_behavior": expected_behavior or "确认批量结算时应保留所有待结算工人。",
        }
        review_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/review",
            json=payload,
            headers=admin_headers(),
        )
    assert review_resp.status_code == 200
    return context, trigger, result


def test_chain_case_draft_preserves_review_metadata_and_related_turns(
    db_session, tmp_path
) -> None:
    context, trigger, result = _seed_reviewed_chain(db_session, tmp_path)

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/case-draft",
            json={"target_type": "evaluation_replay"},
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    case_json = data["case_json"]
    metadata = case_json["metadata"]
    assert data["source_sample_id"] == _sample_id(trigger)
    assert metadata["source"] == "data_flywheel_review_issue_chain"
    assert metadata["chain_id"] == _chain_id(trigger)
    assert metadata["session_id"] == trigger.session_id
    assert metadata["trigger_turn_id"] == trigger.id
    assert metadata["context_turn_ids"] == [context.id]
    assert metadata["result_turn_ids"] == [result.id]
    assert metadata["related_turn_ids"] == [context.id, trigger.id, result.id]
    assert metadata["expected_behavior"] == "确认批量结算时应保留所有待结算工人。"
    assert metadata["root_cause"] == "批量结算意图被参数抽取收窄为单个工人"
    assert metadata["quality_labels"] == ["needs_regression", "wrong_tool_selection"]
    assert case_json["context"]["related_turns"][0]["turn_id"] == context.id
    assert case_json["context"]["related_turns"][1]["turn_id"] == trigger.id
    assert case_json["context"]["related_turns"][2]["turn_id"] == result.id
    assert case_json["issue_assertions"][0]["type"] == (
        "bulk_intent_narrowed_to_single_entity"
    )
    assert case_json["issue_assertions"][0]["expected"] == (
        "确认批量结算时应保留所有待结算工人。"
    )

    stored = db_session.query(AgentCaseDraft).filter_by(draft_id=data["draft_id"]).one()
    assert stored.case_json["metadata"]["chain_id"] == _chain_id(trigger)


def test_chain_case_draft_rejects_missing_expected_behavior(
    db_session, tmp_path
) -> None:
    _, trigger, _ = _seed_reviewed_chain(db_session, tmp_path)
    row = db_session.query(AgentCaseDraft).count()
    from app.models.data_flywheel import AgentReviewIssueChain

    saved = db_session.query(AgentReviewIssueChain).filter_by(
        chain_id=_chain_id(trigger)
    ).one()
    saved.expected_behavior = None
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/case-draft",
            json={"target_type": "evaluation_replay"},
            headers=admin_headers(),
        )

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "CHAIN_EXPECTED_BEHAVIOR_REQUIRED"
    assert db_session.query(AgentCaseDraft).count() == row


def test_chain_repair_pack_exports_traceable_case_and_debug_evidence(
    db_session, tmp_path, monkeypatch
) -> None:
    context, trigger, result = _seed_reviewed_chain(db_session, tmp_path)
    import app.api.admin_data_flywheel_review_issue_chains as chain_api

    monkeypatch.setattr(chain_api, "REPAIR_PACK_BASE_DIR", tmp_path / "repair-packs")

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/repair-pack",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    manifest = data["payload"]["manifest"]
    case = data["payload"]["cases_jsonl"][0]
    assert data["fix_target"] == "router"
    assert manifest["source_chain_ids"] == [_chain_id(trigger)]
    assert manifest["source_sample_ids"] == [_sample_id(trigger)]
    assert manifest["root_cause"] == "批量结算意图被参数抽取收窄为单个工人"
    assert manifest["expected_behavior"] == "确认批量结算时应保留所有待结算工人。"
    assert manifest["warnings"] == []
    assert case["chain_id"] == _chain_id(trigger)
    assert case["session_id"] == trigger.session_id
    assert case["trigger_turn_id"] == trigger.id
    assert case["context_turn_ids"] == [context.id]
    assert case["result_turn_ids"] == [result.id]
    assert case["root_cause"] == "批量结算意图被参数抽取收窄为单个工人"
    assert case["expected_behavior"] == "确认批量结算时应保留所有待结算工人。"
    assert case["regression_draft"].startswith("regression-drafts/")
    assert case["source_debug_json"].startswith("debug/")
    assert "参数抽取" in case["suggested_action"]
    assert "批量作用域" in case["suggested_action"]
    debug_payload = data["payload"]["debug_files"][case["source_debug_json"]]
    debug_turn_ids = [item["turn_id"] for item in debug_payload["related_turns"]]
    assert debug_turn_ids == [context.id, trigger.id, result.id]
    assert debug_payload["related_turns"][1]["pending_lifecycle"]

    cases_path = tmp_path / "repair-packs" / data["pack_id"] / "cases.jsonl"
    written_case = json.loads(cases_path.read_text(encoding="utf-8").splitlines()[0])
    assert written_case["chain_id"] == _chain_id(trigger)


def test_chain_repair_pack_rejects_needs_evidence_or_missing_expected(
    db_session, tmp_path, monkeypatch
) -> None:
    _, trigger, _ = _seed_reviewed_chain(db_session, tmp_path)
    from app.models.data_flywheel import AgentReviewIssueChain

    import app.api.admin_data_flywheel_review_issue_chains as chain_api

    monkeypatch.setattr(chain_api, "REPAIR_PACK_BASE_DIR", tmp_path / "repair-packs")
    saved = db_session.query(AgentReviewIssueChain).filter_by(
        chain_id=_chain_id(trigger)
    ).one()

    auth_scope, client = _admin_client()
    with auth_scope:
        saved.status = "needs_evidence"
        saved.missing_evidence = ["trace", "db_diff"]
        db_session.commit()
        needs_evidence = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/repair-pack",
            headers=admin_headers(),
        )
        saved.status = "accepted"
        saved.expected_behavior = None
        db_session.commit()
        missing_expected = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/repair-pack",
            headers=admin_headers(),
        )

    assert needs_evidence.status_code == 400
    assert needs_evidence.json()["detail"]["code"] == "CHAIN_NEEDS_EVIDENCE"
    assert needs_evidence.json()["detail"]["missing_evidence"] == ["trace", "db_diff"]
    assert missing_expected.status_code == 400
    assert missing_expected.json()["detail"]["code"] == (
        "CHAIN_EXPECTED_BEHAVIOR_REQUIRED"
    )


def test_chain_repair_pack_cleans_export_dir_when_db_commit_fails(
    db_session, tmp_path, monkeypatch
) -> None:
    _, trigger, _ = _seed_reviewed_chain(db_session, tmp_path)
    import app.modules.data_flywheel.review_issue_chain_repair as chain_repair

    export_base_dir = tmp_path / "repair-packs"
    original_commit = db_session.commit
    commit_calls = 0

    def fail_after_write():
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 1:
            raise RuntimeError("commit failed")
        return original_commit()

    monkeypatch.setattr(db_session, "commit", fail_after_write)

    with pytest.raises(RuntimeError, match="commit failed"):
        chain_repair.create_repair_pack_from_review_issue_chain(
            db_session,
            farm_id=trigger.farm_id,
            chain_id=_chain_id(trigger),
            export_base_dir=export_base_dir,
            created_by=ADMIN_USER_ID,
        )

    assert list(export_base_dir.glob("repair-router-*")) == []
