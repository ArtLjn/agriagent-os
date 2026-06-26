"""Agent 数据飞轮样本、标注与用例草稿服务。"""

import json
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.infra.agent_events import read_event_segment
from app.infra.repository_runtime import (
    get_data_flywheel_repository,
    run_maybe_awaitable,
)
from app.models.agent_turn import AgentTurn
from app.models.conversation import ConversationMessage
from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelLabel,
    AgentDataFlywheelPrelabel,
)
from app.modules.data_flywheel.case_builder import build_case_json
from app.modules.data_flywheel.issue_detector import detect_issue_candidates
from app.modules.data_flywheel.judge_service import (
    DataFlywheelJudgeClient,
    build_judge_input,
    normalize_judge_output,
)
from app.services.session_debug_export_service import build_session_debug_export

ALLOWED_LABELS = {
    "good_reply",
    "bad_reply",
    "wrong_tool_selection",
    "tool_parameter_mismatch",
    "pending_missed",
    "hallucinated_execution",
    "tool_error_ignored",
    "missing_wage",
    "disabled_worker_used",
    "needs_regression",
    "off_topic",
    "sensitive_info_leak",
    "unclear_intent",
    "not_actionable",
}
COMPATIBILITY_DEBUG_ASSET_PATH = "compatibility_debug"
SAMPLE_TYPE_SESSION_TURN = "session_turn"
SAMPLE_TYPE_SESSION = "session"
LABEL_STATUS_OPEN = "open"
LABEL_STATUS_RESOLVED = "resolved"
PRELABEL_STATUS_PENDING = "pending"
PRELABEL_STATUS_ACCEPTED = "accepted"
PRELABEL_STATUS_REJECTED = "rejected"
PRELABEL_SOURCE_LLM_JUDGE = "llm_judge"
_ALLOWED_TARGET_TYPES = {"simulation", "evaluation_replay"}
CHAT_RECORD_SOURCE_MYSQL = "mysql_conversation_messages"
EVENT_LOG_STATUS_AVAILABLE = "available"
EVENT_LOG_STATUS_MISSING = "missing"
EVENT_LOG_STATUS_UNBOUND = "unbound"


def _sample_id(turn: AgentTurn) -> str:
    return f"turn:{turn.farm_id}:{turn.session_id}:{turn.id}"


def session_sample_id(*, farm_id: int, session_id: str) -> str:
    return f"session:{farm_id}:{session_id}"


def _parse_sample_id(sample_id: str) -> dict[str, int | str]:
    prefix, separator, tail = sample_id.rpartition(":")
    if not separator:
        raise ValueError("INVALID_SAMPLE_ID")
    parts = prefix.split(":", 2)
    if len(parts) != 3 or parts[0] != "turn" or not parts[2]:
        raise ValueError("INVALID_SAMPLE_ID")
    try:
        farm_id = int(parts[1])
        turn_id = int(tail)
    except ValueError as exc:
        raise ValueError("INVALID_SAMPLE_ID") from exc
    return {"farm_id": farm_id, "session_id": parts[2], "turn_id": turn_id}


def _parse_session_sample_id(sample_id: str) -> dict[str, int | str]:
    prefix, separator, session_id = sample_id.partition(":")
    if prefix != "session" or not separator or not session_id:
        raise ValueError("INVALID_SAMPLE_ID")
    farm_id_text, separator, session_tail = session_id.partition(":")
    if not separator or not session_tail:
        raise ValueError("INVALID_SAMPLE_ID")
    try:
        farm_id = int(farm_id_text)
    except ValueError as exc:
        raise ValueError("INVALID_SAMPLE_ID") from exc
    return {"farm_id": farm_id, "session_id": session_tail}


def _events_for_turn(turn: AgentTurn) -> list[dict[str, Any]]:
    if not turn.event_file:
        return []
    return read_event_segment(turn.event_file, turn.event_seq_start, turn.event_seq_end)


def _event_log_status(
    turn: AgentTurn, events: list[dict[str, Any]] | None = None
) -> str:
    if not turn.event_file:
        return EVENT_LOG_STATUS_UNBOUND
    if not Path(turn.event_file).exists():
        return EVENT_LOG_STATUS_MISSING
    if events is not None and not events:
        return EVENT_LOG_STATUS_MISSING
    return EVENT_LOG_STATUS_AVAILABLE


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


def _prelabels_by_sample(
    db: Session, *, farm_id: int, sample_ids: list[str]
) -> dict[str, list[AgentDataFlywheelPrelabel]]:
    if not sample_ids:
        return {}
    rows = _repo_call(
        _prelabel_repo(db).list_by_samples,
        farm_id=farm_id,
        sample_ids=sample_ids,
    )
    grouped: dict[str, list[AgentDataFlywheelPrelabel]] = defaultdict(list)
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
    q: str | None = None,
    unannotated_only: bool = False,
    sort_by: str = "risk",
    min_risk: float = 0.0,
    severity: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """分页列出轻量样本行，只读取当前页 turn 对应事件片段。"""
    if sample_type != SAMPLE_TYPE_SESSION_TURN:
        return {"items": [], "total": 0}
    if label is not None and label not in ALLOWED_LABELS:
        raise ValueError("INVALID_LABEL")
    if sort_by not in {"risk", "time"}:
        raise ValueError("INVALID_SORT_BY")
    if severity not in {"P0", "P1", "all"}:
        raise ValueError("INVALID_SEVERITY")

    query = db.query(AgentTurn).filter(AgentTurn.farm_id == farm_id)
    if session_id:
        query = query.filter(AgentTurn.session_id == session_id)
    if request_id:
        query = query.filter(AgentTurn.request_id == request_id)
    if q:
        keyword = q.strip()
        if keyword:
            query = query.filter(
                or_(
                    AgentTurn.session_id.contains(keyword),
                    AgentTurn.request_id.contains(keyword),
                    AgentTurn.input_preview.contains(keyword),
                    AgentTurn.reply_preview.contains(keyword),
                )
            )
    if label:
        label_turn_ids = select(AgentDataFlywheelLabel.turn_id).where(
            AgentDataFlywheelLabel.farm_id == farm_id,
            AgentDataFlywheelLabel.sample_type == sample_type,
            AgentDataFlywheelLabel.label == label,
            AgentDataFlywheelLabel.status != LABEL_STATUS_RESOLVED,
            AgentDataFlywheelLabel.turn_id.isnot(None),
        )
        query = query.filter(AgentTurn.id.in_(label_turn_ids))
    if unannotated_only:
        annotated_turn_ids = select(AgentDataFlywheelLabel.turn_id).where(
            AgentDataFlywheelLabel.farm_id == farm_id,
            AgentDataFlywheelLabel.sample_type == sample_type,
            AgentDataFlywheelLabel.status != LABEL_STATUS_RESOLVED,
            AgentDataFlywheelLabel.turn_id.isnot(None),
        )
        query = query.filter(~AgentTurn.id.in_(annotated_turn_ids))
    if min_risk > 0:
        query = query.filter(AgentTurn.risk_score >= min_risk)
    if severity != "all":
        query = query.filter(AgentTurn.risk_severity == severity)

    total = query.count()
    ordering = (
        (
            AgentTurn.risk_score.desc(),
            AgentTurn.created_at.desc(),
            AgentTurn.id.desc(),
        )
        if sort_by == "risk"
        else (AgentTurn.created_at.desc(), AgentTurn.id.desc())
    )
    turns = query.order_by(*ordering).offset(max(offset, 0)).limit(max(limit, 0)).all()
    sample_ids = [_sample_id(turn) for turn in turns]
    labels = _labels_by_sample(db, sample_ids)
    prelabels = _prelabels_by_sample(db, farm_id=farm_id, sample_ids=sample_ids)
    session_sample_ids = [
        session_sample_id(farm_id=turn.farm_id, session_id=turn.session_id)
        for turn in turns
    ]
    session_labels = _labels_by_sample(db, session_sample_ids)
    items = [
        _sample_row(
            turn,
            labels.get(_sample_id(turn), []),
            _events_for_turn(turn),
            session_labels=session_labels.get(
                session_sample_id(farm_id=turn.farm_id, session_id=turn.session_id),
                [],
            ),
            prelabels=prelabels.get(_sample_id(turn), []),
        )
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
    if sample_type not in {SAMPLE_TYPE_SESSION_TURN, SAMPLE_TYPE_SESSION}:
        raise ValueError("INVALID_SAMPLE_TYPE")

    if sample_type == SAMPLE_TYPE_SESSION:
        return _add_session_label(
            db,
            farm_id=farm_id,
            sample_id=sample_id,
            label=label,
            session_id=session_id,
            comment=comment,
            annotator_id=annotator_id,
        )

    row = _upsert_sample_label_row(
        db,
        farm_id=farm_id,
        sample_id=sample_id,
        label=label,
        sample_type=sample_type,
        session_id=session_id,
        turn_id=turn_id,
        request_id=request_id,
        comment=comment,
        annotator_id=annotator_id,
    )
    db.commit()
    db.refresh(row)
    return _label_to_dict(row)


def _add_session_label(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    label: str,
    session_id: str | None,
    comment: str | None,
    annotator_id: str | None,
) -> dict[str, Any]:
    parsed = _parse_session_sample_id(sample_id)
    if parsed["farm_id"] != farm_id:
        raise ValueError("SAMPLE_NOT_FOUND")
    parsed_session_id = str(parsed["session_id"])
    if session_id is not None and session_id != parsed_session_id:
        raise ValueError("SAMPLE_NOT_FOUND")
    if not _session_exists(db, farm_id=farm_id, session_id=parsed_session_id):
        raise ValueError("SAMPLE_NOT_FOUND")

    existing = (
        db.query(AgentDataFlywheelLabel)
        .filter(
            AgentDataFlywheelLabel.farm_id == farm_id,
            AgentDataFlywheelLabel.sample_id == sample_id,
            AgentDataFlywheelLabel.sample_type == SAMPLE_TYPE_SESSION,
            AgentDataFlywheelLabel.label == label,
        )
        .first()
    )
    if existing:
        existing.session_id = parsed_session_id
        existing.turn_id = None
        existing.request_id = None
        existing.comment = comment
        existing.annotator_id = annotator_id
        existing.status = LABEL_STATUS_OPEN
        row = existing
    else:
        row = AgentDataFlywheelLabel(
            farm_id=farm_id,
            sample_id=sample_id,
            sample_type=SAMPLE_TYPE_SESSION,
            session_id=parsed_session_id,
            turn_id=None,
            request_id=None,
            label=label,
            status=LABEL_STATUS_OPEN,
            comment=comment,
            annotator_id=annotator_id,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return _label_to_dict(row)


def _upsert_sample_label_row(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    label: str,
    sample_type: str,
    session_id: str | None = None,
    turn_id: int | None = None,
    request_id: str | None = None,
    comment: str | None = None,
    annotator_id: str | None = None,
) -> AgentDataFlywheelLabel:
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
        existing.status = LABEL_STATUS_OPEN
        return existing

    row = AgentDataFlywheelLabel(
        farm_id=farm_id,
        sample_id=sample_id,
        sample_type=sample_type,
        session_id=turn.session_id,
        turn_id=turn.id,
        request_id=turn.request_id,
        label=label,
        status=LABEL_STATUS_OPEN,
        comment=comment,
        annotator_id=annotator_id,
    )
    db.add(row)
    return row


def delete_sample_label(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    label_id: int,
) -> dict[str, int | bool]:
    """删除当前农场某个样本的一条人工标注。"""
    row = (
        db.query(AgentDataFlywheelLabel)
        .filter(
            AgentDataFlywheelLabel.id == label_id,
            AgentDataFlywheelLabel.farm_id == farm_id,
            AgentDataFlywheelLabel.sample_id == sample_id,
        )
        .first()
    )
    if row is None:
        raise ValueError("LABEL_NOT_FOUND")
    db.delete(row)
    db.commit()
    return {"deleted": True, "id": label_id}


def resolve_sample_label(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    label_id: int,
) -> dict[str, Any]:
    """将当前农场某个样本的一条人工标注标记为已解决。"""
    row = (
        db.query(AgentDataFlywheelLabel)
        .filter(
            AgentDataFlywheelLabel.id == label_id,
            AgentDataFlywheelLabel.farm_id == farm_id,
            AgentDataFlywheelLabel.sample_id == sample_id,
        )
        .first()
    )
    if row is None:
        raise ValueError("LABEL_NOT_FOUND")
    row.status = LABEL_STATUS_RESOLVED
    db.commit()
    db.refresh(row)
    return _label_to_dict(row)


def get_session_annotation_detail(
    db: Session, *, farm_id: int, session_id: str
) -> dict[str, Any]:
    """返回会话级人工标注。"""
    if not _session_exists(db, farm_id=farm_id, session_id=session_id):
        raise ValueError("SAMPLE_NOT_FOUND")
    sample_id = session_sample_id(farm_id=farm_id, session_id=session_id)
    labels = _labels_by_sample(db, [sample_id]).get(sample_id, [])
    return {
        "sample_id": sample_id,
        "sample_type": SAMPLE_TYPE_SESSION,
        "session_id": session_id,
        "quality_labels": _open_quality_labels(labels),
        "labels": [_label_to_dict(row) for row in labels],
    }


def get_sample_detail(db: Session, *, farm_id: int, sample_id: str) -> dict[str, Any]:
    """返回单个样本的事件证据、消息和调试导出。"""
    turn = _turn_for_sample(db, farm_id=farm_id, sample_id=sample_id)
    events = _events_for_turn(turn)
    labels = _labels_by_sample(db, [sample_id]).get(sample_id, [])
    prelabels = _prelabels_by_sample(db, farm_id=farm_id, sample_ids=[sample_id]).get(
        sample_id, []
    )
    sample = _sample_row(turn, labels, events, prelabels=prelabels)
    return {
        "sample": sample,
        "quality_labels": _open_quality_labels(labels),
        "labels": [_label_to_dict(row) for row in labels],
        "prelabels": [_prelabel_to_dict(row) for row in prelabels],
        "latest_prelabel": _prelabel_to_dict(prelabels[0]) if prelabels else None,
        "messages": _messages_for_turn(db, turn),
        "turn": _turn_to_dict(turn),
        "router_decision": _router_decision(events),
        "tool_events": _tool_events(events),
        "pending_lifecycle": _pending_lifecycle(events),
        "debug_export": build_session_debug_export(
            db, farm_id=farm_id, session_id=turn.session_id
        ),
        "source": _source_to_dict(turn),
        "issue_candidates": sample["issue_candidates"],
    }


def create_sample_prelabel(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    judge_client: DataFlywheelJudgeClient,
) -> dict[str, Any]:
    """调用 LLM judge 为样本创建 pending 预标注。"""
    detail = get_sample_detail(db, farm_id=farm_id, sample_id=sample_id)
    sample = detail["sample"]
    payload = build_judge_input(detail)
    raw = judge_client.judge(payload)
    normalized = normalize_judge_output(raw)

    row = AgentDataFlywheelPrelabel(
        farm_id=farm_id,
        sample_id=sample_id,
        sample_type=SAMPLE_TYPE_SESSION_TURN,
        session_id=sample["session_id"],
        turn_id=sample["turn_id"],
        request_id=sample["request_id"],
        source=PRELABEL_SOURCE_LLM_JUDGE,
        status=PRELABEL_STATUS_PENDING,
        labels=normalized["labels"],
        root_cause=normalized["root_cause"],
        severity=normalized["severity"],
        confidence=normalized["confidence"],
        reason=normalized["reason"],
        recommended_fix=normalized["recommended_fix"],
        judge_model=judge_client.judge_model,
        prompt_version=judge_client.prompt_version,
        raw_response=raw,
    )
    row = _repo_call(_prelabel_repo(db).create, row)
    return _prelabel_to_dict(row)


def accept_sample_prelabel(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    prelabel_id: int,
    labels: list[str] | None = None,
    comment: str | None = None,
    annotator_id: str | None = None,
) -> dict[str, Any]:
    """采纳预标注并写入人工标签。"""
    row = _prelabel_for_sample(
        db, farm_id=farm_id, sample_id=sample_id, prelabel_id=prelabel_id
    )
    if row.status != PRELABEL_STATUS_PENDING:
        raise ValueError("PRELABEL_ALREADY_REVIEWED")
    selected_labels = _unique_labels(
        labels if labels is not None else list(row.labels or [])
    )
    if not selected_labels:
        raise ValueError("INVALID_LABEL")
    if any(label not in ALLOWED_LABELS for label in selected_labels):
        raise ValueError("INVALID_LABEL")

    accepted_label_ids: list[int] = []
    for label in selected_labels:
        label_row = _upsert_sample_label_row(
            db,
            farm_id=farm_id,
            sample_id=sample_id,
            sample_type=SAMPLE_TYPE_SESSION_TURN,
            label=label,
            comment=comment,
            annotator_id=annotator_id,
        )
        db.flush()
        accepted_label_ids.append(int(label_row.id))

    row = _repo_call(
        _prelabel_repo(db).update_review_fields,
        farm_id=farm_id,
        prelabel_id=prelabel_id,
        sample_id=sample_id,
        status=PRELABEL_STATUS_ACCEPTED,
        reviewed_by=annotator_id,
        reviewed_at=datetime.now(),
        accepted_label_ids=accepted_label_ids,
    )
    if row is None:
        raise ValueError("PRELABEL_NOT_FOUND")
    return _prelabel_to_dict(row)


def reject_sample_prelabel(
    db: Session,
    *,
    farm_id: int,
    sample_id: str,
    prelabel_id: int,
    annotator_id: str | None = None,
) -> dict[str, Any]:
    """拒绝预标注，不写入人工标签。"""
    row = _prelabel_for_sample(
        db, farm_id=farm_id, sample_id=sample_id, prelabel_id=prelabel_id
    )
    if row.status != PRELABEL_STATUS_PENDING:
        raise ValueError("PRELABEL_ALREADY_REVIEWED")
    row = _repo_call(
        _prelabel_repo(db).update_review_fields,
        farm_id=farm_id,
        prelabel_id=prelabel_id,
        sample_id=sample_id,
        status=PRELABEL_STATUS_REJECTED,
        reviewed_by=annotator_id,
        reviewed_at=datetime.now(),
        accepted_label_ids=None,
    )
    if row is None:
        raise ValueError("PRELABEL_NOT_FOUND")
    return _prelabel_to_dict(row)


def export_sample_jsonl(db: Session, *, farm_id: int, sample_id: str) -> dict[str, str]:
    """导出单条可序列化 JSONL 样本。"""
    detail = get_sample_detail(db, farm_id=farm_id, sample_id=sample_id)
    sample = detail["sample"]
    payload = {
        "sample_id": sample_id,
        "sample_type": SAMPLE_TYPE_SESSION_TURN,
        "quality_labels": detail["quality_labels"],
        "session_id": sample["session_id"],
        "turn_id": sample["turn_id"],
        "request_id": sample["request_id"],
        "user_input": _message_content(detail, "user")
        or sample.get("user_input_preview"),
        "assistant_reply": _message_content(detail, "assistant")
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
    case_json = build_case_json(sample_id=sample_id, sample=sample, detail=detail)
    case_json["metadata"] = {
        **(case_json.get("metadata") or {}),
        "asset_path": COMPATIBILITY_DEBUG_ASSET_PATH,
        "formal_review_required": True,
    }

    draft = AgentCaseDraft(
        farm_id=farm_id,
        draft_id=f"draft-{uuid.uuid4().hex[:12]}",
        source_sample_id=sample_id,
        target_type=target_type,
        status="draft",
        case_json=case_json,
        created_by=created_by,
    )
    draft = _repo_call(_case_draft_repo(db).create, draft)
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


def _prelabel_for_sample(
    db: Session, *, farm_id: int, sample_id: str, prelabel_id: int
) -> AgentDataFlywheelPrelabel:
    row = _repo_call(
        _prelabel_repo(db).get_by_id_and_sample,
        farm_id=farm_id,
        prelabel_id=prelabel_id,
        sample_id=sample_id,
    )
    if row is None:
        raise ValueError("PRELABEL_NOT_FOUND")
    return row


def _prelabel_repo(db: Session):
    return get_data_flywheel_repository(db, "prelabels")


def _case_draft_repo(db: Session):
    return get_data_flywheel_repository(db, "case_drafts")


def _repo_call(method, *args, **kwargs):
    return run_maybe_awaitable(method(*args, **kwargs))


def _session_exists(db: Session, *, farm_id: int, session_id: str) -> bool:
    return (
        db.query(AgentTurn.id)
        .filter(AgentTurn.farm_id == farm_id, AgentTurn.session_id == session_id)
        .first()
        is not None
    )


def _sample_row(
    turn: AgentTurn,
    labels: list[AgentDataFlywheelLabel],
    events: list[dict[str, Any]],
    *,
    session_labels: list[AgentDataFlywheelLabel] | None = None,
    prelabels: list[AgentDataFlywheelPrelabel] | None = None,
) -> dict[str, Any]:
    router_decision = _router_decision(events)
    selected_tools = _selected_tools(router_decision)
    pending_lifecycle = _pending_lifecycle(events)
    session_labels = session_labels or []
    prelabels = prelabels or []
    quality_labels = _open_quality_labels(labels)
    session_quality_labels = _open_quality_labels(session_labels)
    event_log_status = _event_log_status(turn, events)
    return {
        "sample_id": _sample_id(turn),
        "sample_type": SAMPLE_TYPE_SESSION_TURN,
        "session_id": turn.session_id,
        "turn_id": turn.id,
        "request_id": turn.request_id,
        "user_input_preview": turn.input_preview,
        "assistant_reply_preview": turn.reply_preview,
        "source_type": _source_type_for_event_status(event_log_status),
        "event_log_status": event_log_status,
        "chat_record_source": CHAT_RECORD_SOURCE_MYSQL,
        "selected_tools": selected_tools,
        "actual_tools": _actual_tools(events),
        "issue_candidates": _issue_candidates_for_turn(
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
        "prelabels": [_prelabel_to_dict(row) for row in prelabels],
        "latest_prelabel": _prelabel_to_dict(prelabels[0]) if prelabels else None,
        "session_quality_labels": session_quality_labels,
        "session_annotation_status": (
            "labeled" if session_quality_labels else "unlabeled"
        ),
        "session_labels": [_label_to_dict(row) for row in session_labels],
        "token_total": turn.token_total,
        "latency_ms": turn.latency_ms,
        "created_at": turn.created_at.isoformat() if turn.created_at else None,
    }


def _messages_for_turn(db: Session, turn: AgentTurn) -> list[dict[str, Any]]:
    return [
        item
        for item in (
            _message_dict(db, turn.user_message_id),
            _message_dict(db, turn.assistant_message_id),
        )
        if item is not None
    ]


def _issue_candidates_for_turn(
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
        _rule_hit_candidate(rule_hit)
        for rule_hit in turn.rule_hits or []
        if rule_hit in _CHAIN_RULE_HIT_EXPECTED
    ]
    merged: list[dict[str, str]] = []
    for candidate in [*rule_candidates, *detected]:
        if not any(item.get("type") == candidate.get("type") for item in merged):
            merged.append(candidate)
    return merged


_CHAIN_RULE_HIT_EXPECTED = {
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


def _rule_hit_candidate(rule_hit: str) -> dict[str, str]:
    meta = _CHAIN_RULE_HIT_EXPECTED[rule_hit]
    return {
        "type": rule_hit,
        "severity": "high",
        "reason": meta["reason"],
        "evidence": meta["evidence"],
        "suggested_label": meta["suggested_label"],
    }


def _message_dict(db: Session, message_id: int | None) -> dict[str, Any] | None:
    if message_id is None:
        return None
    message = db.query(ConversationMessage).filter_by(id=message_id).first()
    if not message:
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


def _source_to_dict(turn: AgentTurn) -> dict[str, Any]:
    events = _events_for_turn(turn)
    return {
        "event_file": turn.event_file,
        "event_seq_start": turn.event_seq_start,
        "event_seq_end": turn.event_seq_end,
        "event_log_status": _event_log_status(turn, events),
        "chat_record_source": CHAT_RECORD_SOURCE_MYSQL,
    }


def _source_type_for_event_status(event_log_status: str) -> str:
    if event_log_status == EVENT_LOG_STATUS_AVAILABLE:
        return "agent_event_log"
    if event_log_status == EVENT_LOG_STATUS_MISSING:
        return "missing_event_log"
    return "agent_turns"


def _label_to_dict(row: AgentDataFlywheelLabel) -> dict[str, Any]:
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


def _prelabel_to_dict(row: AgentDataFlywheelPrelabel) -> dict[str, Any]:
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


def _unique_labels(labels: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for label in labels:
        if label in seen:
            continue
        seen.add(label)
        unique.append(label)
    return unique


def _open_quality_labels(
    labels: list[AgentDataFlywheelLabel],
) -> list[str]:
    return [
        row.label
        for row in labels
        if (row.status or LABEL_STATUS_OPEN) != LABEL_STATUS_RESOLVED
    ]


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


def _message_content(detail: dict[str, Any], role: str) -> str | None:
    for message in detail["messages"]:
        if message.get("role") == role:
            return message.get("content")
    return None
