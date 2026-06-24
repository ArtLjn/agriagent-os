"""DataFlywheel 虚拟问题链纯 helper。"""

from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_turn import AgentTurn
from app.services.data_flywheel_service import (
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


def timeline_turn(db: Session, turn: AgentTurn, *, chain: dict[str, Any]) -> dict[str, Any]:
    summary = turn_debug_summary(db, turn)
    summary["chain_role"] = chain_role(turn.id, chain)
    return summary


def turn_debug_summary(db: Session, turn: AgentTurn) -> dict[str, Any]:
    events = _events_for_turn(turn)
    router_decision = _router_decision(events)
    source = _source_to_dict(turn)
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
    trigger: AgentTurn, events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    source = _source_to_dict(trigger)
    event_status = source["event_log_status"]
    return [
        {
            "key": "event_log",
            "status": "present" if event_status == "available" else "missing",
            "turn_id": trigger.id,
        },
        {"key": "chat_messages", "status": "present", "turn_id": trigger.id},
        {
            "key": "router_decision",
            "status": "present" if _router_decision(events) else "missing",
            "turn_id": trigger.id,
        },
        {
            "key": "tool_or_pending_evidence",
            "status": (
                "present"
                if _tool_events(events) or _pending_lifecycle(events)
                else "needs_human"
            ),
            "turn_id": trigger.id,
        },
    ]


def evidence_status(checklist: list[dict[str, Any]]) -> str:
    if any(item["status"] == "missing" for item in checklist):
        return "needs_evidence"
    return "ready_for_review"


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
    candidate_types = {item.get("type") for item in sample.get("issue_candidates") or []}
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
