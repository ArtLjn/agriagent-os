"""Admin 数据飞轮 API 测试。"""

import json

from fastapi.testclient import TestClient

import app.modules.data_flywheel.router as admin_data_flywheel_api
import app.modules.data_flywheel.review_issue_chains_router as review_chain_api
import app.modules.data_flywheel.review_issue_chain_service as review_chain_service
import app.modules.data_flywheel.review_issue_chain_repository as review_chain_repo
from app.evaluation.discovery.judge_worker import run_judge_batch
from app.infra.agent_events import AgentEventWriter
from app.main import app
from app.models.data_flywheel import AgentDataFlywheelLabel, AgentReviewIssueChain
from app.models.farm import Farm
from app.models.trace import TraceRecord
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


class DiscoveryJudgeClient:
    def judge(self, payload):
        return {
            "bad_prob": 0.97,
            "issue_type": "tool_error_ignored",
            "suggested_label": "bad",
            "evidence": [f"turn {payload['turn_id']} 工具失败后仍声称成功"],
            "usage": {"input_tokens": 100, "output_tokens": 20},
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
    db.add(
        TraceRecord(
            farm_id=farm.id,
            session_id=session_id,
            request_id="adminfly",
            node_type="llm_call",
            node_name="data_flywheel_test_trace",
            status="success",
            conversation_message_id=assistant_msg.id,
        )
    )
    db.commit()
    return turn


def _seed_chitchat_turn(db):
    ensure_admin_user(db)
    farm = db.query(Farm).filter(Farm.user_id == ADMIN_USER_ID).one()
    session_id = "sess-admin-chitchat"
    conv = get_or_create_conversation(
        db,
        farm_id=farm.id,
        session_id=session_id,
        user_id=ADMIN_USER_ID,
    )
    user_msg = save_message(db, conv.id, "user", "hi")
    turn = create_turn(
        db,
        farm_id=farm.id,
        session_id=session_id,
        conversation_id=conv.id,
        request_id="chitchat",
        user_message_id=user_msg.id,
        input_text="hi",
    )
    assistant_msg = save_message(
        db,
        conv.id,
        "assistant",
        "你好呀，我是芽芽。想查天气、记一笔，或者看看农场情况都可以找我。",
    )
    user_msg.turn_id = turn.id
    assistant_msg.turn_id = turn.id
    db.commit()
    return finish_turn(
        db,
        turn.id,
        reply_text=assistant_msg.content,
        assistant_message_id=assistant_msg.id,
        selected_tools_count=0,
        tool_calls_count=0,
        token_total=64,
        latency_ms=120,
        status="success",
    )


def _sample_id(turn) -> str:
    return f"turn:{turn.farm_id}:sess-admin-flywheel:{turn.id}"


def _chain_id(turn) -> str:
    return f"chain:{turn.farm_id}:{turn.session_id}:{turn.id}"


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


def test_list_samples_defaults_to_risk_sort_and_exposes_discovery_fields(
    db_session, tmp_path
) -> None:
    low_risk = _seed_turn(db_session, tmp_path)
    high_risk = _seed_turn(db_session, tmp_path)
    high_risk.session_id = "sess-admin-risk"
    high_risk.request_id = "riskhigh"
    high_risk.risk_score = 0.91
    high_risk.rule_score = 0.91
    high_risk.risk_dominant_signal = "rule"
    high_risk.risk_severity = "P0"
    high_risk.rule_hits = ["tool_error_ignored"]
    high_risk.judge_bad_prob = 0.7
    high_risk.judge_issue_type = "tool_error_ignored"
    high_risk.judge_suggested_label = "bad_reply"
    low_risk.risk_score = 0.2
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get("/admin/data-flywheel/samples", headers=admin_headers())

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["request_id"] == "riskhigh"
    assert items[0]["risk_score"] == 0.91
    assert items[0]["rule_score"] == 0.91
    assert items[0]["risk_dominant_signal"] == "rule"
    assert items[0]["risk_severity"] == "P0"
    assert items[0]["rule_hits"] == ["tool_error_ignored"]
    assert items[0]["judge_bad_prob"] == 0.7
    assert items[0]["judge_issue_type"] == "tool_error_ignored"
    assert items[0]["judge_suggested_label"] == "bad_reply"


def test_list_samples_supports_time_sort_min_risk_and_severity_filter(
    db_session, tmp_path
) -> None:
    first = _seed_turn(db_session, tmp_path)
    second = _seed_turn(db_session, tmp_path)
    second.session_id = "sess-admin-risk-2"
    second.request_id = "riskp0"
    first.risk_score = 0.1
    first.risk_severity = "P1"
    second.risk_score = 0.8
    second.risk_severity = "P0"
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        time_resp = client.get(
            "/admin/data-flywheel/samples?sort=time", headers=admin_headers()
        )
        hidden_resp = client.get(
            "/admin/data-flywheel/samples?min_risk=0.3", headers=admin_headers()
        )
        p0_resp = client.get(
            "/admin/data-flywheel/samples?severity=P0", headers=admin_headers()
        )

    assert time_resp.status_code == 200
    assert time_resp.json()["items"][0]["turn_id"] == second.id
    assert hidden_resp.status_code == 200
    assert [item["turn_id"] for item in hidden_resp.json()["items"]] == [second.id]
    assert p0_resp.status_code == 200
    assert [item["turn_id"] for item in p0_resp.json()["items"]] == [second.id]


def test_discovery_pipeline_updates_risk_visible_in_admin_samples(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.input_preview = "记录一笔化肥成本"
    turn.reply_preview = "已帮你记录好了。"
    turn.rule_score = 0.95
    turn.rule_hits = ["tool_error_ignored"]
    turn.risk_score = 0.95
    turn.risk_dominant_signal = "rule"
    turn.risk_severity = "P0"
    db_session.commit()

    summary = run_judge_batch(
        db_session,
        judge_client=DiscoveryJudgeClient(),
        month_cost_usd=0,
        limit=10,
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get("/admin/data-flywheel/samples", headers=admin_headers())

    assert summary.updated == 1
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["turn_id"] == turn.id
    assert item["rule_hits"] == ["tool_error_ignored"]
    assert item["judge_bad_prob"] == 0.97
    assert item["judge_issue_type"] == "tool_error_ignored"
    assert item["judge_suggested_label"] == "bad"
    assert item["risk_score"] == 0.97
    assert item["risk_dominant_signal"] == "judge"


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


def test_daily_review_inbox_groups_risk_chains_by_session(db_session, tmp_path) -> None:
    first = _seed_turn(db_session, tmp_path)
    first.risk_score = 0.65
    first.risk_severity = "P1"
    first.risk_dominant_signal = "rule"
    second = _seed_turn(db_session, tmp_path)
    second.risk_score = 0.92
    second.rule_score = 0.8
    second.risk_severity = "P0"
    second.risk_dominant_signal = "judge"
    second.judge_bad_prob = 0.92
    second.judge_issue_type = "tool_parameter_mismatch"
    second.judge_suggested_label = "wrong_tool_selection"
    result = _seed_turn(db_session, tmp_path)
    result.risk_score = 0.0
    other = _seed_turn(db_session, tmp_path)
    other.session_id = "sess-review-low"
    other.request_id = "reviewlow"
    other.risk_score = 0.4
    other.risk_severity = "P1"
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            "/admin/data-flywheel/daily-review/inbox",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    item = data["items"][0]
    assert item["session_id"] == "sess-admin-flywheel"
    assert item["candidate_chain_count"] == 2
    assert item["highest_risk_chain"]["chain_id"] == _chain_id(second)
    assert item["highest_risk_chain"]["context_turn_ids"] == [first.id]
    assert item["highest_risk_chain"]["result_turn_ids"] == [result.id]
    assert item["highest_risk_chain"]["severity"] == "P0"
    assert item["highest_risk_chain"]["dominant_signal"] == "judge"
    assert item["highest_risk_chain"]["risk_context"] == {
        "risk_score": 0.92,
        "rule_score": 0.8,
        "judge_bad_prob": 0.92,
        "dominant_signal": "judge",
        "rule_hits": ["missing_wage", "missing_pending_confirmation"],
        "trigger_reason": "命中规则：missing_wage, missing_pending_confirmation。风险分取规则分和 AI 坏例概率中的较高值。",
        "scoring_rule": "risk_score = max(rule_score, judge_bad_prob)",
    }
    assert item["evidence_status"] == "ready_for_review"
    assert item["next_action"] == "review_chain"


def test_daily_review_inbox_prefers_persisted_candidate_chain_over_virtual_highest_risk(
    db_session, tmp_path
) -> None:
    context = _seed_turn(db_session, tmp_path)
    persisted_trigger = _seed_turn(db_session, tmp_path)
    persisted_trigger.risk_score = 0.55
    persisted_trigger.risk_severity = "P1"
    persisted_trigger.risk_dominant_signal = "rule"
    higher_virtual_trigger = _seed_turn(db_session, tmp_path)
    higher_virtual_trigger.risk_score = 0.97
    higher_virtual_trigger.risk_severity = "P0"
    higher_virtual_trigger.risk_dominant_signal = "judge"
    db_session.add(
        AgentReviewIssueChain(
            farm_id=persisted_trigger.farm_id,
            chain_id=_chain_id(persisted_trigger),
            session_id=persisted_trigger.session_id,
            trigger_turn_id=persisted_trigger.id,
            context_turn_ids=[context.id],
            result_turn_ids=[],
            status="needs_evidence",
            severity="P1",
            dominant_signal="context_analyzer",
            final_labels=[],
            source_label_ids=[],
            missing_evidence=["router_decision"],
        )
    )
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            "/admin/data-flywheel/daily-review/inbox",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["highest_risk_chain"]["chain_id"] == _chain_id(persisted_trigger)
    assert item["highest_risk_chain"]["trigger_turn_id"] == persisted_trigger.id
    assert item["highest_risk_chain"]["context_turn_ids"] == [context.id]
    assert item["status"] == "needs_evidence"
    assert item["next_action"] == "collect_evidence"


def test_daily_review_inbox_includes_new_risk_sessions_when_persisted_chains_exist(
    db_session, tmp_path
) -> None:
    persisted_trigger = _seed_turn(db_session, tmp_path)
    persisted_trigger.risk_score = 0.48
    persisted_trigger.risk_severity = "P1"
    persisted_trigger.risk_dominant_signal = "context_analyzer"
    new_risk_trigger = _seed_turn(db_session, tmp_path)
    new_risk_trigger.session_id = "playground-new-risk"
    new_risk_trigger.request_id = "newrisk"
    new_risk_trigger.risk_score = 0.93
    new_risk_trigger.risk_severity = "P0"
    new_risk_trigger.risk_dominant_signal = "rule"
    db_session.add(
        AgentReviewIssueChain(
            farm_id=persisted_trigger.farm_id,
            chain_id=_chain_id(persisted_trigger),
            session_id=persisted_trigger.session_id,
            trigger_turn_id=persisted_trigger.id,
            context_turn_ids=[],
            result_turn_ids=[],
            status="needs_evidence",
            severity="P1",
            dominant_signal="context_analyzer",
            final_labels=[],
            source_label_ids=[],
            missing_evidence=["router_decision"],
        )
    )
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            "/admin/data-flywheel/daily-review/inbox",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    chain_ids = [item["highest_risk_chain"]["chain_id"] for item in data["items"]]
    assert data["total"] == 2
    assert chain_ids == [_chain_id(new_risk_trigger), _chain_id(persisted_trigger)]


def test_daily_review_inbox_status_group_filters_open_and_handled(
    db_session, tmp_path
) -> None:
    open_trigger = _seed_turn(db_session, tmp_path)
    accepted_trigger = _seed_turn(db_session, tmp_path)
    rejected_trigger = _seed_turn(db_session, tmp_path)
    for trigger, status in [
        (open_trigger, "needs_evidence"),
        (accepted_trigger, "accepted"),
        (rejected_trigger, "rejected"),
    ]:
        trigger.risk_score = 0.8
        trigger.risk_severity = "P1"
        db_session.add(
            AgentReviewIssueChain(
                farm_id=trigger.farm_id,
                chain_id=_chain_id(trigger),
                session_id=trigger.session_id,
                trigger_turn_id=trigger.id,
                context_turn_ids=[],
                result_turn_ids=[],
                status=status,
                severity="P1",
                dominant_signal="manual_triage",
                final_labels=[],
                source_label_ids=[],
                missing_evidence=["router_decision"] if status == "needs_evidence" else [],
            )
        )
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        open_resp = client.get(
            "/admin/data-flywheel/daily-review/inbox?status=open",
            headers=admin_headers(),
        )
        handled_resp = client.get(
            "/admin/data-flywheel/daily-review/inbox?status=handled",
            headers=admin_headers(),
        )

    assert open_resp.status_code == 200
    open_ids = {
        item["highest_risk_chain"]["chain_id"] for item in open_resp.json()["items"]
    }
    assert _chain_id(open_trigger) in open_ids
    assert _chain_id(accepted_trigger) not in open_ids
    assert _chain_id(rejected_trigger) not in open_ids

    assert handled_resp.status_code == 200
    handled_ids = {
        item["highest_risk_chain"]["chain_id"] for item in handled_resp.json()["items"]
    }
    assert _chain_id(open_trigger) not in handled_ids
    assert _chain_id(accepted_trigger) in handled_ids
    assert _chain_id(rejected_trigger) in handled_ids


def test_daily_review_inbox_excludes_judge_only_greeting_false_positive(
    db_session, tmp_path
) -> None:
    risk_turn = _seed_turn(db_session, tmp_path)
    risk_turn.risk_score = 0.75
    risk_turn.risk_severity = "P1"
    risk_turn.risk_dominant_signal = "rule"
    greeting = _seed_chitchat_turn(db_session)
    greeting.risk_score = 0.95
    greeting.rule_score = 0.0
    greeting.rule_hits = []
    greeting.risk_severity = "P0"
    greeting.risk_dominant_signal = "judge"
    greeting.judge_bad_prob = 0.95
    greeting.judge_issue_type = "not_actionable"
    greeting.judge_suggested_label = "not_actionable"
    db_session.add(
        AgentReviewIssueChain(
            farm_id=greeting.farm_id,
            chain_id=_chain_id(greeting),
            session_id=greeting.session_id,
            trigger_turn_id=greeting.id,
            context_turn_ids=[],
            result_turn_ids=[],
            status="needs_evidence",
            severity="P0",
            dominant_signal="judge",
            final_labels=[],
            source_label_ids=[],
            missing_evidence=["router_decision"],
        )
    )
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            "/admin/data-flywheel/daily-review/inbox",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    chain_ids = [item["highest_risk_chain"]["chain_id"] for item in resp.json()["items"]]
    assert _chain_id(risk_turn) in chain_ids
    assert _chain_id(greeting) not in chain_ids


def test_create_review_issue_chain_candidate_from_turn_enters_daily_review_inbox(
    db_session, tmp_path
) -> None:
    context = _seed_turn(db_session, tmp_path)
    trigger = _seed_turn(db_session, tmp_path)
    trigger.risk_score = 0.0
    trigger.risk_severity = None
    trigger.rule_hits = ["bulk_intent_narrowed_to_single_entity"]
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        create_resp = client.post(
            "/admin/data-flywheel/review-issue-chains/candidates",
            json={
                "trigger_turn_id": trigger.id,
                "context_turn_ids": [context.id],
                "result_turn_ids": [],
                "severity": "P0",
                "dominant_signal": "context_analyzer",
                "suggested_labels": [
                    "tool_parameter_mismatch",
                    "needs_regression",
                ],
                "missing_evidence": ["router_decision"],
            },
            headers=admin_headers(),
        )
        inbox_resp = client.get(
            "/admin/data-flywheel/daily-review/inbox",
            headers=admin_headers(),
        )
        detail_resp = client.get(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}",
            headers=admin_headers(),
        )
        review_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/review",
            json={
                "status": "needs_evidence",
                "context_turn_ids": [context.id],
                "result_turn_ids": [],
                "missing_evidence": ["router_decision", "tool_result"],
                "reviewer_comment": "需要补 router 和 tool result。",
            },
            headers=admin_headers(),
        )

    assert create_resp.status_code == 200
    created_chain = create_resp.json()["chain"]
    assert created_chain["chain_id"] == _chain_id(trigger)
    assert created_chain["status"] == "needs_evidence"
    assert created_chain["context_turn_ids"] == [context.id]
    assert created_chain["human_review"]["missing_evidence"] == ["router_decision"]
    assert inbox_resp.status_code == 200
    inbox_item = inbox_resp.json()["items"][0]
    assert inbox_item["highest_risk_chain"]["chain_id"] == _chain_id(trigger)
    assert inbox_item["dominant_signal"] == "context_analyzer"
    assert inbox_item["candidate_chain_count"] == 1
    assert detail_resp.status_code == 200
    assert detail_resp.json()["chain"]["trigger_turn_id"] == trigger.id
    assert review_resp.status_code == 200
    assert review_resp.json()["chain"]["human_review"]["missing_evidence"] == [
        "router_decision",
        "tool_result",
    ]
    assert review_resp.json()["chain"]["human_review"]["reviewer_comment"] == (
        "需要补 router 和 tool result。"
    )


def test_daily_review_inbox_overlays_saved_review_status(db_session, tmp_path) -> None:
    first = _seed_turn(db_session, tmp_path)
    trigger = _seed_turn(db_session, tmp_path)
    trigger.risk_score = 0.92
    trigger.risk_severity = "P0"
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        review_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/review",
            json={
                "status": "accepted",
                "context_turn_ids": [first.id],
                "result_turn_ids": [],
                "final_labels": ["needs_regression", "wrong_tool_selection"],
                "root_cause": "参数抽取收窄了批量作用域",
                "expected_behavior": "应保留所有待处理对象。",
                "fix_target": "router",
                "reviewer_comment": "采纳规则和 AI 预判，需修 router 作用域。",
            },
            headers=admin_headers(),
        )
        inbox_resp = client.get(
            "/admin/data-flywheel/daily-review/inbox",
            headers=admin_headers(),
        )

    assert review_resp.status_code == 200
    assert inbox_resp.status_code == 200
    item = inbox_resp.json()["items"][0]
    assert item["status"] == "accepted"
    assert item["next_action"] == "done"
    assert item["highest_risk_chain"]["status"] == "accepted"
    assert item["highest_risk_chain"]["context_turn_ids"] == [first.id]
    assert item["highest_risk_chain"]["human_review"]["expected_behavior"] == (
        "应保留所有待处理对象。"
    )
    assert item["highest_risk_chain"]["human_review"]["fix_target"] == "router"
    assert item["highest_risk_chain"]["human_review"]["reviewer_comment"] == (
        "采纳规则和 AI 预判，需修 router 作用域。"
    )
    assert item["highest_risk_chain"]["repair"]["fix_target"] == "router"


def test_daily_review_inbox_only_reads_events_for_current_page_sessions(
    db_session, tmp_path, monkeypatch
) -> None:
    page_turn = _seed_turn(db_session, tmp_path)
    page_turn.risk_score = 0.95
    page_turn.risk_severity = "P0"
    offpage_turn = _seed_turn(db_session, tmp_path)
    offpage_turn.session_id = "sess-offpage-risk"
    offpage_turn.request_id = "offpage"
    offpage_turn.risk_score = 0.75
    offpage_turn.risk_severity = "P1"
    db_session.commit()
    seen_sessions: list[str] = []
    original_events_for_turn = review_chain_service._events_for_turn

    def tracking_events_for_turn(turn):
        seen_sessions.append(turn.session_id)
        return original_events_for_turn(turn)

    monkeypatch.setattr(
        review_chain_service,
        "_events_for_turn",
        tracking_events_for_turn,
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            "/admin/data-flywheel/daily-review/inbox",
            params={"limit": 1},
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert [item["session_id"] for item in data["items"]] == [page_turn.session_id]
    assert seen_sessions
    assert set(seen_sessions) == {page_turn.session_id}


def test_review_issue_chain_detail_returns_virtual_context_and_results(
    db_session, tmp_path
) -> None:
    turns = [_seed_turn(db_session, tmp_path) for _ in range(5)]
    trigger = turns[3]
    trigger.risk_score = 0.95
    trigger.risk_severity = "P0"
    trigger.risk_dominant_signal = "rule"
    trigger.rule_hits = ["bulk_intent_narrowed_to_single_entity"]
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    chain = data["chain"]
    assert chain["chain_id"] == _chain_id(trigger)
    assert chain["trigger_turn_id"] == trigger.id
    assert chain["context_turn_ids"] == [turn.id for turn in turns[:3]]
    assert chain["result_turn_ids"] == [turns[4].id]
    assert set(chain) >= {
        "chain_id",
        "session_id",
        "trigger_turn_id",
        "context_turn_ids",
        "result_turn_ids",
        "status",
        "severity",
        "dominant_signal",
        "diagnosis",
        "ai_judge",
        "human_review",
        "regression",
        "repair",
    }
    timeline_roles = {item["turn_id"]: item["chain_role"] for item in data["timeline"]}
    assert timeline_roles[trigger.id] == "trigger"
    assert timeline_roles[turns[0].id] == "context"
    assert timeline_roles[turns[4].id] == "result"
    assert data["turn_debug_summaries"][str(trigger.id)]["event_log_status"] == (
        "available"
    )
    assert data["existing_labels"] == []
    assert data["ai_judge"]["issue_type"] is None


def test_review_issue_chain_ai_judge_persists_chain_advice(
    db_session, tmp_path, monkeypatch
) -> None:
    turns = [_seed_turn(db_session, tmp_path) for _ in range(3)]
    trigger = turns[1]
    trigger.risk_score = 0.92
    trigger.risk_severity = "P0"
    trigger.risk_dominant_signal = "rule"
    db_session.commit()
    judge_client = FakeJudgeClient()
    judge_client.prompt_version = "data-flywheel-chain-judge-v1"
    monkeypatch.setattr(
        review_chain_api,
        "build_data_flywheel_judge_client",
        lambda: judge_client,
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        judge_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/ai-judge",
            headers=admin_headers(),
        )
        detail_resp = client.get(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}",
            headers=admin_headers(),
        )

    assert judge_resp.status_code == 200
    assert judge_client.calls
    evidence_pack = judge_client.calls[0]
    assert evidence_pack["task"] == "judge_review_issue_chain"
    assert evidence_pack["chain"]["chain_id"] == _chain_id(trigger)
    assert evidence_pack["trigger_turn"]["turn_id"] == trigger.id
    assert [turn["turn_id"] for turn in evidence_pack["context_turns"]] == [
        turns[0].id
    ]
    assert [turn["turn_id"] for turn in evidence_pack["result_turns"]] == [
        turns[2].id
    ]
    chain = judge_resp.json()["chain"]
    assert chain["ai_judge"]["suggested_label"] == "bad_reply"
    assert chain["ai_judge"]["bad_prob"] == 0.91
    assert chain["ai_judge"]["root_cause"] == "缺少 pending 确认"
    assert chain["ai_judge"]["judge_model"] == "fake-judge"
    assert chain["ai_judge"]["prompt_version"] == "data-flywheel-chain-judge-v1"
    assert detail_resp.status_code == 200
    assert detail_resp.json()["chain"]["ai_judge"]["reason"] == (
        "回复声称已安排，但证据中缺少写操作确认链路。"
    )
    stored_chain = (
        db_session.query(AgentReviewIssueChain)
        .filter_by(chain_id=_chain_id(trigger))
        .one()
    )
    assert stored_chain.dominant_signal == "judge"


def test_review_issue_chain_detail_excludes_followup_without_result_evidence(
    db_session, tmp_path
) -> None:
    turns = [_seed_turn(db_session, tmp_path) for _ in range(3)]
    trigger = turns[1]
    followup = turns[2]
    trigger.risk_score = 0.9
    trigger.risk_severity = "P0"
    followup.event_file = None
    followup.event_seq_start = None
    followup.event_seq_end = None
    followup.tool_calls_count = 0
    followup.pending_plan_id = None
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["chain"]["context_turn_ids"] == [turns[0].id]
    assert data["chain"]["result_turn_ids"] == []
    timeline_roles = {item["turn_id"]: item["chain_role"] for item in data["timeline"]}
    assert timeline_roles[followup.id] == "unrelated"


def test_review_issue_chain_detail_rejects_low_risk_trigger(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.0
    turn.risk_severity = None
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}",
            headers=admin_headers(),
        )

    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "CHAIN_NOT_FOUND"


def test_review_issue_chain_detail_marks_missing_evidence(db_session, tmp_path) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.event_file = None
    turn.event_seq_start = None
    turn.event_seq_end = None
    turn.risk_score = 0.88
    turn.risk_severity = "P1"
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["chain"]["status"] == "needs_evidence"
    assert data["evidence_status"] == "needs_evidence"
    checklist = data["evidence_checklist"]
    assert {"key": "event_log", "status": "missing", "turn_id": turn.id} in checklist
    assert data["chain"]["repair"]["export_blocked_reason"] == "needs_evidence"


def test_review_issue_chain_detail_distinguishes_required_evidence_keys(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.88
    turn.risk_severity = "P1"
    db_session.query(TraceRecord).filter_by(
        farm_id=turn.farm_id,
        session_id=turn.session_id,
        request_id=turn.request_id,
    ).delete()
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    checklist = {item["key"]: item["status"] for item in data["evidence_checklist"]}
    assert set(checklist) == {
        "event_log",
        "chat_messages",
        "router_decision",
        "tool_result",
        "pending_lifecycle",
        "trace",
        "db_diff",
        "backfilled_event",
    }
    assert checklist["trace"] == "missing"
    assert checklist["db_diff"] == "needs_human"
    assert checklist["event_log"] == "present"
    assert "tool_or_pending_evidence" not in checklist
    assert data["evidence_status"] == "needs_evidence"


def test_review_issue_chain_detail_marks_backfilled_event_from_payload_and_meta(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.88
    turn.risk_severity = "P1"
    user_msg = save_message(db_session, turn.conversation_id, "user", "补录消息")
    user_msg.turn_id = turn.id
    user_msg.meta_json = {"event_backfilled": True}
    writer = AgentEventWriter(base_dir=tmp_path)
    write = writer.write(
        event_type="message.user",
        farm_id=turn.farm_id,
        user_id=ADMIN_USER_ID,
        session_id=turn.session_id,
        turn_id=turn.id,
        request_id=turn.request_id,
        payload={"content": "补录消息", "backfilled": True},
    )
    turn.event_seq_end = write.seq
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.get(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}",
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    checklist = {item["key"]: item["status"] for item in data["evidence_checklist"]}
    assert checklist["backfilled_event"] == "present"
    trigger_summary = data["turn_debug_summaries"][str(turn.id)]
    assert trigger_summary["backfilled_event"] is True


def test_review_issue_chain_review_accepts_and_overrides_related_turns(
    db_session, tmp_path
) -> None:
    turns = [_seed_turn(db_session, tmp_path) for _ in range(5)]
    trigger = turns[3]
    trigger.risk_score = 0.95
    trigger.risk_severity = "P0"
    trigger.risk_dominant_signal = "judge"
    trigger.judge_issue_type = "tool_parameter_mismatch"
    db_session.commit()

    payload = {
        "status": "accepted",
        "context_turn_ids": [turns[0].id, turns[2].id],
        "result_turn_ids": [turns[4].id],
        "final_labels": ["needs_regression", "wrong_tool_selection"],
        "root_cause": "批量结算意图被参数抽取收窄为单人",
        "expected_behavior": "确认批量结算时应保留所有待结算工人。",
    }

    auth_scope, client = _admin_client()
    with auth_scope:
        review_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/review",
            json=payload,
            headers=admin_headers(),
        )
        detail_resp = client.get(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}",
            headers=admin_headers(),
        )

    assert review_resp.status_code == 200
    saved = review_resp.json()["chain"]
    assert saved["status"] == "accepted"
    assert saved["context_turn_ids"] == [turns[0].id, turns[2].id]
    assert saved["result_turn_ids"] == [turns[4].id]
    assert saved["human_review"]["status"] == "accepted"
    assert saved["human_review"]["final_labels"] == [
        "needs_regression",
        "wrong_tool_selection",
    ]
    assert saved["human_review"]["root_cause"] == "批量结算意图被参数抽取收窄为单人"
    assert saved["human_review"]["expected_behavior"] == (
        "确认批量结算时应保留所有待结算工人。"
    )
    assert saved["regression"]["needs_regression"] is True
    assert saved["regression"]["regression_ready"] is True
    assert saved["repair"]["regression_ready"] is True
    assert saved["repair"]["export_blocked_reason"] is None
    assert detail_resp.status_code == 200
    detail_chain = detail_resp.json()["chain"]
    assert detail_chain["context_turn_ids"] == [turns[0].id, turns[2].id]
    assert detail_chain["result_turn_ids"] == [turns[4].id]
    assert detail_chain["human_review"]["expected_behavior"] == (
        "确认批量结算时应保留所有待结算工人。"
    )
    labels = (
        db_session.query(AgentDataFlywheelLabel)
        .filter_by(sample_id=_sample_id(trigger))
        .order_by(AgentDataFlywheelLabel.label.asc())
        .all()
    )
    assert [row.label for row in labels] == [
        "needs_regression",
        "wrong_tool_selection",
    ]
    stored_chain = (
        db_session.query(AgentReviewIssueChain)
        .filter_by(chain_id=_chain_id(trigger))
        .one()
    )
    assert stored_chain.source_label_ids == [row.id for row in labels]


def test_review_issue_chain_review_does_not_call_committing_label_service(
    db_session, tmp_path, monkeypatch
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.9
    db_session.commit()

    def forbidden_add_sample_label(*args, **kwargs):
        raise AssertionError("chain review must not call committing add_sample_label")

    monkeypatch.setattr(
        review_chain_repo,
        "add_sample_label",
        forbidden_add_sample_label,
        raising=False,
    )

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "accepted",
                "final_labels": ["needs_regression"],
                "root_cause": "参数作用域丢失",
                "expected_behavior": "应保留批量作用域",
            },
            headers=admin_headers(),
        )

    assert resp.status_code == 200
    assert db_session.query(AgentDataFlywheelLabel).count() == 1


def test_review_issue_chain_review_rolls_back_when_final_commit_fails(
    db_session, tmp_path, monkeypatch
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.9
    db_session.commit()

    original_commit = db_session.commit

    def failing_commit():
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    try:
        review_chain_service.save_review_issue_chain_review(
            db_session,
            farm_id=turn.farm_id,
            chain_id=_chain_id(turn),
            status="accepted",
            final_labels=["needs_regression", "wrong_tool_selection"],
            root_cause="参数作用域丢失",
            expected_behavior="应保留批量作用域",
            reviewer_id=ADMIN_USER_ID,
        )
    except RuntimeError as exc:
        assert str(exc) == "commit failed"
    else:
        raise AssertionError("commit failure should bubble up")
    finally:
        monkeypatch.setattr(db_session, "commit", original_commit)

    assert db_session.query(AgentReviewIssueChain).count() == 0
    assert db_session.query(AgentDataFlywheelLabel).count() == 0


def test_review_issue_chain_review_requires_accepted_fields(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.9
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        missing_expected = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "accepted",
                "root_cause": "参数作用域丢失",
                "final_labels": ["needs_regression"],
            },
            headers=admin_headers(),
        )
        missing_labels = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "accepted",
                "root_cause": "参数作用域丢失",
                "expected_behavior": "应保留批量作用域",
            },
            headers=admin_headers(),
        )

    assert missing_expected.status_code == 400
    assert missing_expected.json()["detail"]["code"] == (
        "CHAIN_REVIEW_EXPECTED_BEHAVIOR_REQUIRED"
    )
    assert missing_labels.status_code == 400
    assert missing_labels.json()["detail"]["code"] == (
        "CHAIN_REVIEW_FINAL_LABELS_REQUIRED"
    )


def test_review_issue_chain_review_rejects_with_reason_without_labels(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.9
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        missing_reason = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={"status": "rejected"},
            headers=admin_headers(),
        )
        review_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "rejected",
                "false_positive_reason": "规则误把正常确认流程判为参数错配",
            },
            headers=admin_headers(),
        )

    assert missing_reason.status_code == 400
    assert missing_reason.json()["detail"]["code"] == (
        "CHAIN_REVIEW_FALSE_POSITIVE_REASON_REQUIRED"
    )
    assert review_resp.status_code == 200
    chain = review_resp.json()["chain"]
    assert chain["status"] == "rejected"
    assert chain["human_review"]["false_positive_reason"] == (
        "规则误把正常确认流程判为参数错配"
    )
    assert db_session.query(AgentDataFlywheelLabel).count() == 0


def test_review_issue_chain_review_records_final_labels_for_non_accepted_without_training_labels(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.9
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        rejected_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "rejected",
                "final_labels": ["needs_regression"],
                "false_positive_reason": "规则误报",
            },
            headers=admin_headers(),
        )
        evidence_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "needs_evidence",
                "final_labels": ["needs_regression"],
                "missing_evidence": ["trace"],
                "reviewer_comment": "需要补 trace 证据。",
            },
            headers=admin_headers(),
        )

    assert rejected_resp.status_code == 200
    assert rejected_resp.json()["chain"]["human_review"]["final_labels"] == [
        "needs_regression"
    ]
    assert evidence_resp.status_code == 200
    assert evidence_resp.json()["chain"]["human_review"]["final_labels"] == [
        "needs_regression"
    ]
    assert db_session.query(AgentReviewIssueChain).count() == 1
    assert db_session.query(AgentDataFlywheelLabel).count() == 0


def test_review_issue_chain_review_transition_from_accepted_resolves_chain_labels(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.9
    sample_id = _sample_id(turn)
    existing_label = AgentDataFlywheelLabel(
        farm_id=turn.farm_id,
        sample_id=sample_id,
        sample_type="session_turn",
        session_id=turn.session_id,
        turn_id=turn.id,
        request_id=turn.request_id,
        label="bad_reply",
        status="open",
        annotator_id="manual-admin",
    )
    db_session.add(existing_label)
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        accepted_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "accepted",
                "final_labels": ["needs_regression"],
                "root_cause": "参数作用域丢失",
                "expected_behavior": "应保留批量作用域",
            },
            headers=admin_headers(),
        )
        rejected_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "rejected",
                "false_positive_reason": "人工复核为正常流程",
            },
            headers=admin_headers(),
        )
        detail_resp = client.get(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}",
            headers=admin_headers(),
        )

    assert accepted_resp.status_code == 200
    assert rejected_resp.status_code == 200
    assert detail_resp.status_code == 200
    labels = (
        db_session.query(AgentDataFlywheelLabel)
        .filter_by(sample_id=sample_id)
        .order_by(AgentDataFlywheelLabel.label.asc())
        .all()
    )
    assert [(row.label, row.status) for row in labels] == [
        ("bad_reply", "open"),
        ("needs_regression", "resolved"),
    ]
    stored_chain = (
        db_session.query(AgentReviewIssueChain)
        .filter_by(chain_id=_chain_id(turn))
        .one()
    )
    assert stored_chain.status == "rejected"
    assert stored_chain.final_labels == []
    assert stored_chain.source_label_ids == [labels[1].id]
    assert detail_resp.json()["chain"]["human_review"]["final_labels"] == []


def test_review_issue_chain_review_resolves_removed_source_labels_on_accepted_update(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.9
    sample_id = _sample_id(turn)
    manual_label = AgentDataFlywheelLabel(
        farm_id=turn.farm_id,
        sample_id=sample_id,
        sample_type="session_turn",
        session_id=turn.session_id,
        turn_id=turn.id,
        request_id=turn.request_id,
        label="bad_reply",
        status="open",
        annotator_id="manual-admin",
    )
    db_session.add(manual_label)
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        first_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "accepted",
                "final_labels": ["needs_regression", "wrong_tool_selection"],
                "root_cause": "参数作用域丢失",
                "expected_behavior": "应保留批量作用域",
            },
            headers=admin_headers(),
        )
        second_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "accepted",
                "final_labels": ["wrong_tool_selection"],
                "root_cause": "参数作用域丢失",
                "expected_behavior": "应保留批量作用域",
            },
            headers=admin_headers(),
        )
        rejected_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "rejected",
                "false_positive_reason": "人工复核为正常流程",
            },
            headers=admin_headers(),
        )

    assert first_resp.status_code == 200
    assert second_resp.status_code == 200
    assert rejected_resp.status_code == 200
    labels = (
        db_session.query(AgentDataFlywheelLabel)
        .filter_by(sample_id=sample_id)
        .order_by(AgentDataFlywheelLabel.label.asc())
        .all()
    )
    assert [(row.label, row.status) for row in labels] == [
        ("bad_reply", "open"),
        ("needs_regression", "resolved"),
        ("wrong_tool_selection", "resolved"),
    ]


def test_review_issue_chain_review_requires_missing_evidence(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.9
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        missing_payload = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={"status": "needs_evidence"},
            headers=admin_headers(),
        )
        review_resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "needs_evidence",
                "missing_evidence": ["event", "trace", "db_diff", "context"],
                "reviewer_comment": "需要补 event/trace/db_diff/context 证据。",
            },
            headers=admin_headers(),
        )

    assert missing_payload.status_code == 400
    assert missing_payload.json()["detail"]["code"] == (
        "CHAIN_REVIEW_MISSING_EVIDENCE_REQUIRED"
    )
    assert review_resp.status_code == 200
    chain = review_resp.json()["chain"]
    assert chain["status"] == "needs_evidence"
    assert chain["human_review"]["missing_evidence"] == [
        "event",
        "trace",
        "db_diff",
        "context",
    ]
    assert chain["human_review"]["reviewer_comment"] == (
        "需要补 event/trace/db_diff/context 证据。"
    )
    assert db_session.query(AgentDataFlywheelLabel).count() == 0


def test_review_issue_chain_review_requires_evidence_comment(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.9
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(turn)}/review",
            json={
                "status": "needs_evidence",
                "missing_evidence": ["trace"],
            },
            headers=admin_headers(),
        )

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "CHAIN_REVIEW_EVIDENCE_COMMENT_REQUIRED"


def test_review_issue_chain_review_validates_related_turn_scope(
    db_session, tmp_path
) -> None:
    trigger = _seed_turn(db_session, tmp_path)
    other_session_turn = _seed_turn(db_session, tmp_path)
    trigger.risk_score = 0.9
    other_session_turn.session_id = "sess-other-review"
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/review",
            json={
                "status": "not_actionable",
                "context_turn_ids": [other_session_turn.id],
            },
            headers=admin_headers(),
        )

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "CHAIN_REVIEW_RELATED_TURN_NOT_FOUND"
    assert resp.json()["detail"]["chain_id"] == _chain_id(trigger)
    assert resp.json()["detail"]["status"] == "not_actionable"
    assert db_session.query(AgentReviewIssueChain).count() == 0


def test_review_issue_chain_review_rejects_overlapping_related_turns(
    db_session, tmp_path
) -> None:
    related = _seed_turn(db_session, tmp_path)
    trigger = _seed_turn(db_session, tmp_path)
    trigger.risk_score = 0.9
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        resp = client.post(
            f"/admin/data-flywheel/review-issue-chains/{_chain_id(trigger)}/review",
            json={
                "status": "not_actionable",
                "context_turn_ids": [related.id],
                "result_turn_ids": [related.id],
            },
            headers=admin_headers(),
        )

    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "CHAIN_REVIEW_RELATED_TURN_OVERLAP"
    assert db_session.query(AgentReviewIssueChain).count() == 0


def test_review_issue_chain_respects_current_farm_boundary(
    db_session, tmp_path
) -> None:
    turn = _seed_turn(db_session, tmp_path)
    turn.risk_score = 0.9
    turn.risk_severity = "P0"
    forbidden_chain_id = f"chain:{turn.farm_id + 1}:{turn.session_id}:{turn.id}"
    db_session.commit()

    auth_scope, client = _admin_client()
    with auth_scope:
        detail_resp = client.get(
            f"/admin/data-flywheel/review-issue-chains/{forbidden_chain_id}",
            headers=admin_headers(),
        )
        inbox_resp = client.get(
            "/admin/data-flywheel/daily-review/inbox",
            params={"session_id": turn.session_id, "min_risk": 0.1},
            headers=admin_headers(),
        )

    assert detail_resp.status_code == 404
    assert detail_resp.json()["detail"]["code"] == "CHAIN_NOT_FOUND"
    assert inbox_resp.status_code == 200
    assert inbox_resp.json()["items"][0]["session_id"] == turn.session_id
    assert inbox_resp.json()["items"][0]["highest_risk_chain"]["chain_id"] == (
        _chain_id(turn)
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
    assert data["case_json"]["metadata"]["asset_path"] == "compatibility_debug"
    assert data["case_json"]["metadata"]["formal_review_required"] is True


def test_sample_case_draft_marks_compatibility_debug_path(db_session, tmp_path) -> None:
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
    assert data["case_json"]["metadata"]["source"] == "data_flywheel"
    assert data["case_json"]["metadata"]["asset_path"] == "compatibility_debug"
    assert data["case_json"]["metadata"]["formal_review_required"] is True
    assert data["case_json"]["metadata"]["asset_path"] == "compatibility_debug"
    assert data["case_json"]["metadata"]["formal_review_required"] is True


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
            "reason": "router 选择了写操作工具「create_operation_work_order」，但 pending lifecycle 中没有对应的确认计划",
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


def test_create_repair_pack_rejects_mixed_fix_targets(db_session, tmp_path) -> None:
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
    assert {case["fix_target"] for case in data["payload"]["cases_jsonl"]} == {"router"}


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
