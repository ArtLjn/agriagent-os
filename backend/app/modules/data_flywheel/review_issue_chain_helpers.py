"""DataFlywheel 虚拟问题链纯 helper。"""

from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.agent_turn import AgentTurn
from app.models.conversation import ConversationMessage
from app.models.trace import TraceRecord
from app.modules.data_flywheel.service import (
    _events_for_turn,
    _label_to_dict,
    _messages_for_turn,
    _open_quality_labels,
    _pending_lifecycle,
    _router_decision,
    _source_to_dict,
    _tool_events,
)


def public_chain(chain: dict[str, Any]) -> dict[str, Any]:
    return {
        key: chain[key]
        for key in (
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
        )
    }


def virtual_related_turns(
    session_turns: list[AgentTurn], trigger: AgentTurn
) -> tuple[list[AgentTurn], list[AgentTurn]]:
    index = next(
        (idx for idx, turn in enumerate(session_turns) if turn.id == trigger.id),
        None,
    )
    if index is None:
        return [], []
    followup_turns = session_turns[index + 1 : index + 3]
    result_turns = [turn for turn in followup_turns if has_result_evidence(turn)]
    return session_turns[max(0, index - 3) : index], result_turns


def has_result_evidence(turn: AgentTurn) -> bool:
    events = _events_for_turn(turn)
    return bool(_pending_lifecycle(events) or _tool_events(events))


def timeline_turn(
    db: Session, turn: AgentTurn, *, chain: dict[str, Any]
) -> dict[str, Any]:
    summary = turn_debug_summary(db, turn)
    summary["chain_role"] = chain_role(turn.id, chain)
    return summary


def turn_debug_summary(db: Session, turn: AgentTurn) -> dict[str, Any]:
    events = _events_for_turn(turn)
    router_decision = _router_decision(events)
    source = _source_to_dict(turn)
    backfilled = has_backfilled_event(db, turn, events)
    return {
        "turn_id": turn.id,
        "request_id": turn.request_id,
        "user_input_preview": turn.input_preview,
        "assistant_reply_preview": turn.reply_preview,
        "messages": _messages_for_turn(db, turn),
        "selected_tools": router_decision.get("selected_tools") or [],
        "tool_events": _tool_events(events),
        "pending_lifecycle": _pending_lifecycle(events),
        "router_decision": router_decision,
        "source": source,
        "event_log_status": source["event_log_status"],
        "backfilled_event": backfilled,
    }


def chain_role(turn_id: int, chain: dict[str, Any]) -> str:
    if turn_id == chain["trigger_turn_id"]:
        return "trigger"
    if turn_id in chain["context_turn_ids"]:
        return "context"
    if turn_id in chain["result_turn_ids"]:
        return "result"
    return "unrelated"


def evidence_checklist(
    db: Session, trigger: AgentTurn, events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    turn_id = trigger.id
    return [
        _evidence_item("event_log", _event_log_status(trigger), turn_id),
        _evidence_item(
            "chat_messages",
            "present" if _messages_for_turn(db, trigger) else "missing",
            turn_id,
        ),
        _evidence_item(
            "router_decision",
            "present" if _router_decision(events) else "missing",
            turn_id,
        ),
        _evidence_item(
            "tool_result",
            "present" if _tool_events(events) else "needs_human",
            turn_id,
        ),
        _evidence_item(
            "pending_lifecycle",
            "present" if _pending_lifecycle(events) else "needs_human",
            turn_id,
        ),
        _evidence_item(
            "trace",
            "present" if has_trace_record(db, trigger) else "missing",
            turn_id,
        ),
        _evidence_item("db_diff", "needs_human", turn_id),
        _evidence_item(
            "backfilled_event",
            "present" if has_backfilled_event(db, trigger, events) else "missing",
            turn_id,
        ),
    ]


def evidence_status(checklist: list[dict[str, Any]]) -> str:
    required_keys = {"event_log", "chat_messages", "router_decision", "trace"}
    if any(
        item["status"] == "missing" and item["key"] in required_keys
        for item in checklist
    ):
        return "needs_evidence"
    return "ready_for_review"


def _event_log_status(trigger: AgentTurn) -> str:
    source = _source_to_dict(trigger)
    return "present" if source["event_log_status"] == "available" else "missing"


def _evidence_item(key: str, status: str, turn_id: int | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"key": key, "status": status}
    if turn_id is not None:
        item["turn_id"] = turn_id
    return item


def has_trace_record(db: Session, turn: AgentTurn) -> bool:
    message_ids = [
        message_id
        for message_id in (turn.user_message_id, turn.assistant_message_id)
        if message_id is not None
    ]
    filters = [
        (
            (TraceRecord.session_id == turn.session_id)
            & (TraceRecord.request_id == turn.request_id)
        )
    ]
    if message_ids:
        filters.append(TraceRecord.conversation_message_id.in_(message_ids))
    return (
        db.query(TraceRecord.id)
        .filter(
            TraceRecord.farm_id == turn.farm_id,
            or_(*filters),
        )
        .first()
        is not None
    )


def has_backfilled_event(
    db: Session, turn: AgentTurn, events: list[dict[str, Any]]
) -> bool:
    if any(_event_is_backfilled(event) for event in events):
        return True
    return any(
        _message_meta_is_backfilled(message) for message in _message_rows(db, turn)
    )


def _event_is_backfilled(event: dict[str, Any]) -> bool:
    payload = event.get("payload") or {}
    meta = event.get("meta") or {}
    return (
        isinstance(payload, dict)
        and bool(payload.get("backfilled") or payload.get("event_backfilled"))
    ) or (
        isinstance(meta, dict)
        and bool(meta.get("backfilled") or meta.get("event_backfilled"))
    )


def _message_meta_is_backfilled(message: ConversationMessage) -> bool:
    meta_json = message.meta_json or {}
    return bool(
        isinstance(meta_json, dict)
        and (meta_json.get("event_backfilled") or meta_json.get("backfilled"))
    )


def _message_rows(db: Session, turn: AgentTurn) -> list[ConversationMessage]:
    message_ids = [
        message_id
        for message_id in (turn.user_message_id, turn.assistant_message_id)
        if message_id is not None
    ]
    if not message_ids:
        return []
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.id.in_(message_ids))
        .all()
    )


def next_action(evidence_status_value: str) -> str:
    return (
        "collect_evidence"
        if evidence_status_value == "needs_evidence"
        else "review_chain"
    )


def diagnosis(sample: dict[str, Any]) -> dict[str, Any]:
    candidates = sample.get("issue_candidates") or []
    primary = candidates[0] if candidates else {}
    return {
        "title": primary.get("type") or sample.get("judge_issue_type") or "risk_turn",
        "summary": primary.get("reason") or "该 turn 被风险评分纳入每日质检。",
        "candidate_type": primary.get("type"),
        "suggested_labels": suggested_labels(sample, primary),
    }


def ai_judge(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "bad_prob": sample.get("judge_bad_prob"),
        "issue_type": sample.get("judge_issue_type"),
        "suggested_label": sample.get("judge_suggested_label"),
        "dominant_signal": sample.get("risk_dominant_signal"),
    }


def human_review(labels: list[Any]) -> dict[str, Any]:
    return {
        "status": "unreviewed",
        "labels": [_label_to_dict(row) for row in labels],
        "quality_labels": _open_quality_labels(labels),
        "expected_behavior": None,
        "root_cause": None,
    }


def regression_status(sample: dict[str, Any], labels: list[Any]) -> dict[str, Any]:
    quality_labels = _open_quality_labels(labels)
    return {
        "needs_regression": "needs_regression" in quality_labels,
        "regression_ready": False,
        "source_sample_id": sample["sample_id"],
    }


def repair_status(status: str, sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "fix_target": fix_target(sample),
        "regression_ready": False,
        "export_blocked_reason": (
            "needs_evidence" if status == "needs_evidence" else "needs_human_review"
        ),
    }


def fix_target(sample: dict[str, Any]) -> str:
    candidate_types = {
        item.get("type") for item in sample.get("issue_candidates") or []
    }
    candidate_types.add(sample.get("judge_issue_type"))
    if candidate_types & {
        "tool_parameter_mismatch",
        "bulk_intent_narrowed_to_single_entity",
    }:
        return "router"
    if "pending_missed" in candidate_types:
        return "pending_plan"
    return "manual_triage"


def suggested_labels(sample: dict[str, Any], primary: dict[str, Any]) -> list[str]:
    labels = [
        primary.get("suggested_label"),
        sample.get("judge_suggested_label"),
    ]
    return [str(label) for label in labels if label]


def severity(sample: dict[str, Any]) -> str:
    sample_severity = sample.get("risk_severity")
    if sample_severity in {"P0", "P1"}:
        return sample_severity
    return "P0" if (sample.get("risk_score") or 0.0) >= 0.8 else "P1"


def dominant_signal(sample: dict[str, Any]) -> str:
    return sample.get("risk_dominant_signal") or "rule"


def session_summary(turn: AgentTurn) -> str:
    return turn.input_preview or turn.reply_preview or f"session {turn.session_id}"


def parse_chain_id(chain_id: str) -> dict[str, int | str]:
    prefix, separator, tail = chain_id.rpartition(":")
    if not separator:
        raise ValueError("INVALID_CHAIN_ID")
    parts = prefix.split(":", 2)
    if len(parts) != 3 or parts[0] != "chain" or not parts[2]:
        raise ValueError("INVALID_CHAIN_ID")
    try:
        farm_id = int(parts[1])
        turn_id = int(tail)
    except ValueError as exc:
        raise ValueError("INVALID_CHAIN_ID") from exc
    return {"farm_id": farm_id, "session_id": parts[2], "turn_id": turn_id}


def chain_id(turn: AgentTurn) -> str:
    return f"chain:{turn.farm_id}:{turn.session_id}:{turn.id}"
