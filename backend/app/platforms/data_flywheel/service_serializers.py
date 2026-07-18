"""DataFlywheel service response serializers."""

from typing import Any

from app.models.agent_turn import AgentTurn
from app.models.conversation import ConversationMessage
from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelLabel,
    AgentDataFlywheelPrelabel,
)
from app.platforms.data_flywheel.issue_detector import detect_issue_candidates

CHAT_RECORD_SOURCE_MYSQL = "mysql_conversation_messages"
EVENT_LOG_STATUS_AVAILABLE = "available"
EVENT_LOG_STATUS_MISSING = "missing"
EVENT_LOG_STATUS_UNBOUND = "unbound"
LABEL_STATUS_OPEN = "open"
LABEL_STATUS_RESOLVED = "resolved"


def sample_row(
    turn: AgentTurn,
    labels: list[AgentDataFlywheelLabel],
    events: list[dict[str, Any]],
    *,
    selected_tools: list[str],
    actual_tools: list[str],
    pending_lifecycle: list[dict[str, Any]],
    event_log_status: str,
    session_labels: list[AgentDataFlywheelLabel] | None = None,
    prelabels: list[AgentDataFlywheelPrelabel] | None = None,
) -> dict[str, Any]:
    session_labels = session_labels or []
    prelabels = prelabels or []
    quality_labels = open_quality_labels(labels)
    session_quality_labels = open_quality_labels(session_labels)
    return {
        "sample_id": f"turn:{turn.farm_id}:{turn.session_id}:{turn.id}",
        "sample_type": "session_turn",
        "session_id": turn.session_id,
        "turn_id": turn.id,
        "request_id": turn.request_id,
        "user_input_preview": turn.input_preview,
        "assistant_reply_preview": turn.reply_preview,
        "source_type": source_type_for_event_status(event_log_status),
        "event_log_status": event_log_status,
        "chat_record_source": CHAT_RECORD_SOURCE_MYSQL,
        "selected_tools": selected_tools,
        "actual_tools": actual_tools,
        "issue_candidates": issue_candidates_for_turn(
            turn=turn,
            selected_tools=selected_tools,
            events=events,
            pending_lifecycle=pending_lifecycle,
        ),
        "risk_score": turn.risk_score,
        "rule_score": turn.rule_score,
        "risk_dominant_signal": turn.risk_dominant_signal,
        "risk_severity": turn.risk_severity,
        "rule_hits": turn.rule_hits or [],
        "judge_bad_prob": turn.judge_bad_prob,
        "judge_issue_type": turn.judge_issue_type,
        "judge_suggested_label": turn.judge_suggested_label,
        "quality_labels": quality_labels,
        "annotation_status": "labeled" if quality_labels else "unlabeled",
        "prelabels": [prelabel_to_dict(row) for row in prelabels],
        "latest_prelabel": prelabel_to_dict(prelabels[0]) if prelabels else None,
        "session_quality_labels": session_quality_labels,
        "session_annotation_status": (
            "labeled" if session_quality_labels else "unlabeled"
        ),
        "session_labels": [label_to_dict(row) for row in session_labels],
        "token_total": turn.token_total,
        "latency_ms": turn.latency_ms,
        "created_at": turn.created_at.isoformat() if turn.created_at else None,
    }


def issue_candidates_for_turn(
    *,
    turn: AgentTurn,
    selected_tools: list[str],
    events: list[dict[str, Any]],
    pending_lifecycle: list[dict[str, Any]],
) -> list[dict[str, str]]:
    detected = detect_issue_candidates(
        user_input=turn.input_preview,
        assistant_reply=turn.reply_preview,
        selected_tools=selected_tools,
        events=events,
        pending_lifecycle=pending_lifecycle,
    )
    rule_candidates = [
        rule_hit_candidate(rule_hit)
        for rule_hit in turn.rule_hits or []
        if rule_hit in CHAIN_RULE_HIT_EXPECTED
    ]
    merged: list[dict[str, str]] = []
    for candidate in [*rule_candidates, *detected]:
        if not any(item.get("type") == candidate.get("type") for item in merged):
            merged.append(candidate)
    return merged


CHAIN_RULE_HIT_EXPECTED = {
    "tool_parameter_mismatch": {
        "reason": "工具参数与用户表达的对象或作用域不一致",
        "evidence": "router parameter extraction",
        "suggested_label": "wrong_tool_selection",
    },
    "bulk_intent_narrowed_to_single_entity": {
        "reason": "批量意图在参数抽取或确认流程中被收窄为单个实体",
        "evidence": "bulk scope narrowed",
        "suggested_label": "wrong_tool_selection",
    },
}


def rule_hit_candidate(rule_hit: str) -> dict[str, str]:
    meta = CHAIN_RULE_HIT_EXPECTED[rule_hit]
    return {
        "type": rule_hit,
        "severity": "high",
        "reason": meta["reason"],
        "evidence": meta["evidence"],
        "suggested_label": meta["suggested_label"],
    }


def message_to_dict(message: ConversationMessage) -> dict[str, Any]:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
    }


def turn_to_dict(turn: AgentTurn) -> dict[str, Any]:
    return {
        "id": turn.id,
        "request_id": turn.request_id,
        "token_total": turn.token_total,
        "latency_ms": turn.latency_ms,
        "risk_score": turn.risk_score,
        "rule_score": turn.rule_score,
        "risk_dominant_signal": turn.risk_dominant_signal,
        "risk_severity": turn.risk_severity,
        "rule_hits": turn.rule_hits or [],
        "judge_bad_prob": turn.judge_bad_prob,
        "judge_issue_type": turn.judge_issue_type,
        "judge_suggested_label": turn.judge_suggested_label,
        "status": turn.status,
    }


def source_to_dict(turn: AgentTurn, event_log_status: str) -> dict[str, Any]:
    return {
        "event_file": turn.event_file,
        "event_seq_start": turn.event_seq_start,
        "event_seq_end": turn.event_seq_end,
        "event_log_status": event_log_status,
        "chat_record_source": CHAT_RECORD_SOURCE_MYSQL,
    }


def source_type_for_event_status(event_log_status: str) -> str:
    if event_log_status == EVENT_LOG_STATUS_AVAILABLE:
        return "agent_event_log"
    if event_log_status == EVENT_LOG_STATUS_MISSING:
        return "missing_event_log"
    return "agent_turns"


def label_to_dict(row: AgentDataFlywheelLabel) -> dict[str, Any]:
    return {
        "id": row.id,
        "sample_id": row.sample_id,
        "sample_type": row.sample_type,
        "session_id": row.session_id,
        "turn_id": row.turn_id,
        "request_id": row.request_id,
        "label": row.label,
        "status": row.status,
        "comment": row.comment,
        "annotator_id": row.annotator_id,
    }


def prelabel_to_dict(row: AgentDataFlywheelPrelabel) -> dict[str, Any]:
    return {
        "id": row.id,
        "sample_id": row.sample_id,
        "sample_type": row.sample_type,
        "session_id": row.session_id,
        "turn_id": row.turn_id,
        "request_id": row.request_id,
        "source": row.source,
        "status": row.status,
        "labels": row.labels or [],
        "root_cause": row.root_cause,
        "severity": row.severity,
        "confidence": row.confidence,
        "reason": row.reason,
        "recommended_fix": row.recommended_fix,
        "judge_model": row.judge_model,
        "prompt_version": row.prompt_version,
        "accepted_label_ids": row.accepted_label_ids or [],
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def open_quality_labels(
    labels: list[AgentDataFlywheelLabel],
) -> list[str]:
    return [
        row.label
        for row in labels
        if (row.status or LABEL_STATUS_OPEN) != LABEL_STATUS_RESOLVED
    ]


def draft_to_dict(draft: AgentCaseDraft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "draft_id": draft.draft_id,
        "source_sample_id": draft.source_sample_id,
        "target_type": draft.target_type,
        "status": draft.status,
        "case_json": draft.case_json,
        "created_by": draft.created_by,
    }


def message_content(detail: dict[str, Any], role: str) -> str | None:
    for message in detail["messages"]:
        if message.get("role") == role:
            return message.get("content")
    return None
