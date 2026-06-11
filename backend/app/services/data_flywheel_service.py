"""Agent 数据飞轮样本、标注与用例草稿服务。"""

import json
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.agent_events import read_event_segment
from app.models.agent_turn import AgentTurn
from app.models.conversation import ConversationMessage
from app.models.data_flywheel import AgentCaseDraft, AgentDataFlywheelLabel
from app.services.session_debug_export_service import build_session_debug_export

ALLOWED_LABELS = {
    "good_reply",
    "bad_reply",
    "wrong_tool_selection",
    "pending_missed",
    "hallucinated_execution",
    "missing_wage",
    "disabled_worker_used",
    "needs_regression",
    "not_actionable",
}
SAMPLE_TYPE_SESSION_TURN = "session_turn"
_ALLOWED_TARGET_TYPES = {"simulation", "evaluation_replay"}


def _sample_id(turn: AgentTurn) -> str:
    return f"turn:{turn.farm_id}:{turn.session_id}:{turn.id}"


def _parse_sample_id(sample_id: str) -> dict[str, int | str]:
    parts = sample_id.split(":")
    if len(parts) != 4 or parts[0] != "turn" or not parts[2]:
        raise ValueError("INVALID_SAMPLE_ID")
    try:
        farm_id = int(parts[1])
        turn_id = int(parts[3])
    except ValueError as exc:
        raise ValueError("INVALID_SAMPLE_ID") from exc
    return {"farm_id": farm_id, "session_id": parts[2], "turn_id": turn_id}


def _events_for_turn(turn: AgentTurn) -> list[dict[str, Any]]:
    if not turn.event_file:
        return []
    return read_event_segment(turn.event_file, turn.event_seq_start, turn.event_seq_end)


def _labels_by_sample(
    db: Session, sample_ids: list[str]
) -> dict[str, list[AgentDataFlywheelLabel]]:
    if not sample_ids:
        return {}
    rows = (
        db.query(AgentDataFlywheelLabel)
        .filter(AgentDataFlywheelLabel.sample_id.in_(sample_ids))
        .order_by(
            AgentDataFlywheelLabel.created_at.asc(),
            AgentDataFlywheelLabel.id.asc(),
        )
        .all()
    )
    grouped: dict[str, list[AgentDataFlywheelLabel]] = defaultdict(list)
    for row in rows:
        grouped[row.sample_id].append(row)
    return dict(grouped)


def _router_decision(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event in events:
        if event.get("event_type") == "router.decision":
            payload = event.get("payload") or {}
            return payload if isinstance(payload, dict) else {}
    return {}


def _selected_tools(router_decision: dict[str, Any]) -> list[str]:
    tools = router_decision.get("selected_tools") or []
    if not isinstance(tools, list):
        return []
    return [str(tool) for tool in tools if tool]


def _actual_tools(events: list[dict[str, Any]]) -> list[str]:
    tools: list[str] = []
    for event in events:
        if event.get("event_type") not in {"tool.call.finished", "tool.call.failed"}:
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        tool_name = payload.get("tool_name")
        if tool_name:
            tools.append(str(tool_name))
    return tools


def _tool_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if str(event.get("event_type") or "").startswith("tool.call.")
    ]


def _pending_lifecycle(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if str(event.get("event_type") or "").startswith("pending.")
    ]


def list_samples(
    db: Session,
    *,
    farm_id: int,
    sample_type: str = SAMPLE_TYPE_SESSION_TURN,
    label: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    unannotated_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """分页列出轻量样本行，只读取当前页 turn 对应事件片段。"""
    if sample_type != SAMPLE_TYPE_SESSION_TURN:
        return {"items": [], "total": 0}
    if label is not None and label not in ALLOWED_LABELS:
        raise ValueError("INVALID_LABEL")

    query = db.query(AgentTurn).filter(AgentTurn.farm_id == farm_id)
    if session_id:
        query = query.filter(AgentTurn.session_id == session_id)
    if request_id:
        query = query.filter(AgentTurn.request_id == request_id)
    if label:
        label_turn_ids = select(AgentDataFlywheelLabel.turn_id).where(
            AgentDataFlywheelLabel.farm_id == farm_id,
            AgentDataFlywheelLabel.sample_type == sample_type,
            AgentDataFlywheelLabel.label == label,
            AgentDataFlywheelLabel.turn_id.isnot(None),
        )
        query = query.filter(AgentTurn.id.in_(label_turn_ids))
    if unannotated_only:
        annotated_turn_ids = select(AgentDataFlywheelLabel.turn_id).where(
            AgentDataFlywheelLabel.farm_id == farm_id,
            AgentDataFlywheelLabel.sample_type == sample_type,
            AgentDataFlywheelLabel.turn_id.isnot(None),
        )
        query = query.filter(~AgentTurn.id.in_(annotated_turn_ids))

    total = query.count()
    turns = (
        query.order_by(AgentTurn.created_at.desc(), AgentTurn.id.desc())
        .offset(max(offset, 0))
        .limit(max(limit, 0))
        .all()
    )
    sample_ids = [_sample_id(turn) for turn in turns]
    labels = _labels_by_sample(db, sample_ids)
    items = [
        _sample_row(turn, labels.get(_sample_id(turn), []), _events_for_turn(turn))
        for turn in turns
    ]
    return {"items": items, "total": total}


def add_sample_label(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    label: str,
    sample_type: str = SAMPLE_TYPE_SESSION_TURN,
    session_id: str | None = None,
    turn_id: int | None = None,
    request_id: str | None = None,
    comment: str | None = None,
    annotator_id: str | None = None,
) -> dict[str, Any]:
    """保存管理员样本标注。"""
    if label not in ALLOWED_LABELS:
        raise ValueError("INVALID_LABEL")
    if sample_type != SAMPLE_TYPE_SESSION_TURN:
        raise ValueError("INVALID_SAMPLE_TYPE")

    turn = _turn_for_sample(db, farm_id=farm_id, sample_id=sample_id)
    if session_id is not None and session_id != turn.session_id:
        raise ValueError("SAMPLE_NOT_FOUND")
    if turn_id is not None and turn_id != turn.id:
        raise ValueError("SAMPLE_NOT_FOUND")
    if request_id is not None and request_id != turn.request_id:
        raise ValueError("SAMPLE_NOT_FOUND")

    existing = (
        db.query(AgentDataFlywheelLabel)
        .filter(
            AgentDataFlywheelLabel.farm_id == farm_id,
            AgentDataFlywheelLabel.sample_id == sample_id,
            AgentDataFlywheelLabel.sample_type == sample_type,
            AgentDataFlywheelLabel.label == label,
        )
        .first()
    )
    if existing:
        existing.session_id = turn.session_id
        existing.turn_id = turn.id
        existing.request_id = turn.request_id
        existing.comment = comment
        existing.annotator_id = annotator_id
        row = existing
    else:
        row = AgentDataFlywheelLabel(
            farm_id=farm_id,
            sample_id=sample_id,
            sample_type=sample_type,
            session_id=turn.session_id,
            turn_id=turn.id,
            request_id=turn.request_id,
            label=label,
            comment=comment,
            annotator_id=annotator_id,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return _label_to_dict(row)


def get_sample_detail(db: Session, *, farm_id: int, sample_id: str) -> dict[str, Any]:
    """返回单个样本的事件证据、消息和调试导出。"""
    turn = _turn_for_sample(db, farm_id=farm_id, sample_id=sample_id)
    events = _events_for_turn(turn)
    labels = _labels_by_sample(db, [sample_id]).get(sample_id, [])
    user_message = _message_by_id(db, turn.user_message_id)
    assistant_message = _message_by_id(db, turn.assistant_message_id)
    return {
        "sample": _sample_row(turn, labels, events),
        "quality_labels": _quality_labels(labels),
        "labels": [_label_to_dict(row) for row in labels],
        "messages": {
            "user": _message_to_dict(user_message),
            "assistant": _message_to_dict(assistant_message),
        },
        "turn": _turn_to_dict(turn),
        "router_decision": _router_decision(events),
        "tool_events": _tool_events(events),
        "pending_lifecycle": _pending_lifecycle(events),
        "debug_export": build_session_debug_export(
            db, farm_id=farm_id, session_id=turn.session_id
        ),
        "source": _source_to_dict(turn),
    }


def export_sample_jsonl(db: Session, *, farm_id: int, sample_id: str) -> dict[str, str]:
    """导出单条可序列化 JSONL 样本。"""
    detail = get_sample_detail(db, farm_id=farm_id, sample_id=sample_id)
    sample = detail["sample"]
    user_message = detail["messages"]["user"] or {}
    assistant_message = detail["messages"]["assistant"] or {}
    payload = {
        "sample_id": sample_id,
        "sample_type": SAMPLE_TYPE_SESSION_TURN,
        "quality_labels": detail["quality_labels"],
        "session_id": sample["session_id"],
        "turn_id": sample["turn_id"],
        "request_id": sample["request_id"],
        "user_input": user_message.get("content") or sample.get("user_input_preview"),
        "assistant_reply": assistant_message.get("content")
        or sample.get("assistant_reply_preview"),
        "selected_tools": sample["selected_tools"],
        "actual_tools": sample["actual_tools"],
        "router_decision": detail["router_decision"],
        "tool_events": detail["tool_events"],
        "pending_lifecycle": detail["pending_lifecycle"],
        "source": detail["source"],
    }
    filename = (
        "data-flywheel-sample-"
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{sample['turn_id']}.jsonl"
    )
    return {
        "filename": filename,
        "content": json.dumps(payload, ensure_ascii=False, default=str) + "\n",
    }


def build_case_draft(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    target_type: str,
    created_by: str | None = None,
) -> dict[str, Any]:
    """从数据飞轮样本生成仿真/回放评测用例草稿。"""
    if target_type not in _ALLOWED_TARGET_TYPES:
        raise ValueError("INVALID_TARGET_TYPE")

    detail = get_sample_detail(db, farm_id=farm_id, sample_id=sample_id)
    sample = detail["sample"]
    user_message = detail["messages"]["user"] or {}
    assistant_message = detail["messages"]["assistant"] or {}
    quality_labels = detail["quality_labels"]
    label_text = ", ".join(quality_labels) if quality_labels else "unlabeled"
    case_json = {
        "case_id": f"regression-{sample['session_id']}-{sample['turn_id']}",
        "description": f"Data flywheel regression sample {sample_id} ({label_text})",
        "user_input": user_message.get("content")
        or sample.get("user_input_preview")
        or "",
        "category": quality_labels[0] if quality_labels else "data_flywheel",
        "expected_skills": [
            {"name": tool_name} for tool_name in sample["selected_tools"]
        ],
        "expected_pending_action": None,
        "confirmation_flow": [],
        "expected_database_diff": [],
        "reply_assertions": _reply_assertions(assistant_message, sample),
        "metadata": {
            "source": "data_flywheel",
            "source_sample_id": sample_id,
            "source_session_id": sample["session_id"],
            "source_request_id": sample["request_id"],
            "quality_labels": quality_labels,
        },
    }
    case_json["expected_pending_action"] = _expected_pending_action(
        detail["pending_lifecycle"], quality_labels, sample["selected_tools"]
    )

    draft = AgentCaseDraft(
        farm_id=farm_id,
        draft_id=f"draft-{uuid.uuid4().hex[:12]}",
        source_sample_id=sample_id,
        target_type=target_type,
        status="draft",
        case_json=case_json,
        created_by=created_by,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _draft_to_dict(draft)


def _turn_for_sample(db: Session, *, farm_id: int, sample_id: str) -> AgentTurn:
    parsed = _parse_sample_id(sample_id)
    if parsed["farm_id"] != farm_id:
        raise ValueError("SAMPLE_NOT_FOUND")
    turn = (
        db.query(AgentTurn)
        .filter(
            AgentTurn.id == parsed["turn_id"],
            AgentTurn.farm_id == farm_id,
            AgentTurn.session_id == parsed["session_id"],
        )
        .first()
    )
    if not turn:
        raise ValueError("SAMPLE_NOT_FOUND")
    return turn


def _sample_row(
    turn: AgentTurn,
    labels: list[AgentDataFlywheelLabel],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    router_decision = _router_decision(events)
    quality_labels = _quality_labels(labels)
    return {
        "sample_id": _sample_id(turn),
        "sample_type": SAMPLE_TYPE_SESSION_TURN,
        "farm_id": turn.farm_id,
        "session_id": turn.session_id,
        "turn_id": turn.id,
        "request_id": turn.request_id,
        "user_input_preview": turn.input_preview,
        "assistant_reply_preview": turn.reply_preview,
        "source_type": "agent_event_log" if turn.event_file else "agent_turns",
        "selected_tools": _selected_tools(router_decision),
        "actual_tools": _actual_tools(events),
        "quality_labels": quality_labels,
        "annotation_status": "labeled" if quality_labels else "unlabeled",
    }


def _quality_labels(labels: list[AgentDataFlywheelLabel]) -> list[str]:
    return [row.label for row in labels]


def _message_by_id(db: Session, message_id: int | None) -> ConversationMessage | None:
    if message_id is None:
        return None
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.id == message_id)
        .first()
    )


def _message_to_dict(message: ConversationMessage | None) -> dict[str, Any] | None:
    if message is None:
        return None
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
    }


def _turn_to_dict(turn: AgentTurn) -> dict[str, Any]:
    return {
        "id": turn.id,
        "request_id": turn.request_id,
        "token_total": turn.token_total,
        "latency_ms": turn.latency_ms,
        "status": turn.status,
    }


def _source_to_dict(turn: AgentTurn) -> dict[str, Any]:
    return {
        "event_file": turn.event_file,
        "event_seq_start": turn.event_seq_start,
        "event_seq_end": turn.event_seq_end,
    }


def _label_to_dict(row: AgentDataFlywheelLabel) -> dict[str, Any]:
    return {
        "id": row.id,
        "sample_id": row.sample_id,
        "label": row.label,
        "comment": row.comment,
        "annotator_id": row.annotator_id,
    }


def _draft_to_dict(draft: AgentCaseDraft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "draft_id": draft.draft_id,
        "source_sample_id": draft.source_sample_id,
        "target_type": draft.target_type,
        "status": draft.status,
        "case_json": draft.case_json,
        "created_by": draft.created_by,
    }


def _reply_assertions(
    assistant_message: dict[str, Any] | None,
    sample: dict[str, Any],
) -> list[dict[str, str]]:
    reply = (assistant_message or {}).get("content") or sample.get(
        "assistant_reply_preview"
    )
    return [{"contains": reply}] if reply else []


def _expected_pending_action(
    pending_lifecycle: list[dict[str, Any]],
    quality_labels: list[str],
    selected_tools: list[str],
) -> dict[str, Any] | None:
    if not pending_lifecycle and "pending_missed" not in quality_labels:
        return None
    skill_name = _pending_skill_name(pending_lifecycle) or (
        selected_tools[0] if selected_tools else ""
    )
    return {
        "skill_name": skill_name,
        "params": {},
        "status": "created",
        "confirmation_required": True,
    }


def _pending_skill_name(pending_lifecycle: list[dict[str, Any]]) -> str | None:
    for event in pending_lifecycle:
        payload = event.get("payload") or {}
        steps = payload.get("steps") if isinstance(payload, dict) else None
        if isinstance(steps, list) and steps:
            skill_name = steps[0].get("skill_name")
            if skill_name:
                return str(skill_name)
    return None
