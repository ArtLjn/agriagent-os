"""ReviewIssueChain 人工审核持久化服务。"""

from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.repository_runtime import (
    get_data_flywheel_repository,
    run_maybe_awaitable,
)
from app.models.agent_turn import AgentTurn
from app.models.data_flywheel import AgentDataFlywheelLabel, AgentReviewIssueChain
from app.platforms.data_flywheel.service import (
    ALLOWED_LABELS,
    LABEL_STATUS_OPEN,
    LABEL_STATUS_RESOLVED,
    SAMPLE_TYPE_SESSION_TURN,
    _sample_id,
    _upsert_sample_label_row,
)

CHAIN_REVIEW_STATUSES = {
    "accepted",
    "rejected",
    "not_actionable",
    "needs_evidence",
}


def get_saved_review_issue_chain(
    db: Session, *, farm_id: int, chain_id: str
) -> AgentReviewIssueChain | None:
    """按当前 farm 和 chain_id 读取已保存的问题链。"""
    return _repo_call(
        _review_chain_repo(db).get_by_chain_id,
        farm_id=farm_id,
        chain_id=chain_id,
    )


def save_review_issue_chain(
    db: Session,
    *,
    farm_id: int,
    chain_id: str,
    trigger: AgentTurn,
    base_chain: dict[str, Any],
    status: str,
    context_turn_ids: list[int] | None = None,
    result_turn_ids: list[int] | None = None,
    final_labels: list[str] | None = None,
    root_cause: str | None = None,
    expected_behavior: str | None = None,
    fix_target: str | None = None,
    reviewer_comment: str | None = None,
    false_positive_reason: str | None = None,
    missing_evidence: list[str] | None = None,
    reviewer_id: str | None = None,
) -> AgentReviewIssueChain:
    """保存或更新人工审核结论。"""
    for attempt in range(2):
        try:
            return _save_review_issue_chain(
                db,
                farm_id=farm_id,
                chain_id=chain_id,
                trigger=trigger,
                base_chain=base_chain,
                status=status,
                context_turn_ids=context_turn_ids,
                result_turn_ids=result_turn_ids,
                final_labels=final_labels,
                root_cause=root_cause,
                expected_behavior=expected_behavior,
                fix_target=fix_target,
                reviewer_comment=reviewer_comment,
                false_positive_reason=false_positive_reason,
                missing_evidence=missing_evidence,
                reviewer_id=reviewer_id,
            )
        except IntegrityError:
            db.rollback()
            if attempt == 0:
                continue
            raise ValueError("CHAIN_REVIEW_CONFLICT") from None
        except Exception:
            db.rollback()
            raise
    raise ValueError("CHAIN_REVIEW_CONFLICT")


def _save_review_issue_chain(
    db: Session,
    *,
    farm_id: int,
    chain_id: str,
    trigger: AgentTurn,
    base_chain: dict[str, Any],
    status: str,
    context_turn_ids: list[int] | None,
    result_turn_ids: list[int] | None,
    final_labels: list[str] | None,
    root_cause: str | None,
    expected_behavior: str | None,
    fix_target: str | None,
    reviewer_comment: str | None,
    false_positive_reason: str | None,
    missing_evidence: list[str] | None,
    reviewer_id: str | None,
) -> AgentReviewIssueChain:
    _validate_status(status)
    final_labels = _clean_list(final_labels)
    root_cause = _clean_text(root_cause)
    expected_behavior = _clean_text(expected_behavior)
    fix_target = _clean_fix_target(fix_target) or str(
        base_chain["repair"]["fix_target"]
    )
    reviewer_comment = _clean_text(reviewer_comment)
    false_positive_reason = _clean_text(false_positive_reason)
    missing_evidence = _clean_list(missing_evidence)
    _validate_required_fields(
        status=status,
        final_labels=final_labels,
        root_cause=root_cause,
        expected_behavior=expected_behavior,
        reviewer_comment=reviewer_comment,
        false_positive_reason=false_positive_reason,
        missing_evidence=missing_evidence,
    )
    _validate_final_labels(final_labels=final_labels)

    context_ids, result_ids = _final_related_turn_ids(
        db,
        farm_id=farm_id,
        session_id=trigger.session_id,
        trigger_turn_id=trigger.id,
        context_turn_ids=context_turn_ids,
        result_turn_ids=result_turn_ids,
        base_chain=base_chain,
    )
    row = get_saved_review_issue_chain(db, farm_id=farm_id, chain_id=chain_id)
    now = datetime.now()
    if row is None:
        row = AgentReviewIssueChain(
            farm_id=farm_id,
            chain_id=chain_id,
            session_id=trigger.session_id,
            trigger_turn_id=trigger.id,
            created_at=now,
            source_label_ids=[],
        )
        db.add(row)

    row.context_turn_ids = context_ids
    row.result_turn_ids = result_ids
    row.status = status
    row.severity = str(base_chain["severity"])
    row.dominant_signal = str(base_chain["dominant_signal"])
    row.final_labels = final_labels
    row.root_cause = root_cause
    row.expected_behavior = expected_behavior
    row.fix_target = fix_target
    row.reviewer_comment = reviewer_comment
    row.false_positive_reason = false_positive_reason
    row.missing_evidence = missing_evidence or None
    row.reviewer_id = reviewer_id
    row.reviewed_at = now
    row.updated_at = now

    if status == "accepted":
        old_source_label_ids = row.source_label_ids or []
        current_source_label_ids = _upsert_final_labels(
            db,
            row=row,
            farm_id=farm_id,
            trigger=trigger,
            final_labels=final_labels,
            reviewer_id=reviewer_id,
        )
        removed_source_label_ids = sorted(
            set(old_source_label_ids) - set(current_source_label_ids)
        )
        _resolve_source_labels(
            db,
            row=row,
            trigger=trigger,
            source_label_ids=removed_source_label_ids,
        )
        row.source_label_ids = _merge_label_ids(
            old_source_label_ids,
            current_source_label_ids,
        )
    else:
        _resolve_source_labels(db, row=row, trigger=trigger)

    return _repo_call(_review_chain_repo(db).save, row)


def chain_review_to_dict(row: AgentReviewIssueChain) -> dict[str, Any]:
    """返回 API 可序列化的问题链人工审核数据。"""
    return {
        "id": row.id,
        "chain_id": row.chain_id,
        "status": row.status,
        "final_labels": row.final_labels or [],
        "source_label_ids": row.source_label_ids or [],
        "root_cause": row.root_cause,
        "expected_behavior": row.expected_behavior,
        "fix_target": row.fix_target,
        "reviewer_comment": row.reviewer_comment,
        "false_positive_reason": row.false_positive_reason,
        "missing_evidence": row.missing_evidence or [],
        "reviewer_id": row.reviewer_id,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


def overlay_saved_review(
    chain: dict[str, Any], row: AgentReviewIssueChain | None
) -> dict[str, Any]:
    """用已保存结论覆盖虚拟链默认窗口和 readiness。"""
    if row is None:
        return chain
    chain["context_turn_ids"] = row.context_turn_ids or []
    chain["result_turn_ids"] = row.result_turn_ids or []
    chain["status"] = row.status
    chain["severity"] = row.severity
    chain["dominant_signal"] = row.dominant_signal
    chain["human_review"] = _human_review_from_row(chain, row)
    chain["regression"] = _regression_from_row(chain, row)
    chain["repair"] = _repair_from_row(chain, row)
    if isinstance(row.ai_judge, dict) and row.ai_judge:
        chain["ai_judge"] = dict(row.ai_judge)
    return chain


def save_review_issue_chain_ai_judge(
    db: Session,
    *,
    farm_id: int,
    chain_id: str,
    trigger: AgentTurn,
    base_chain: dict[str, Any],
    ai_judge: dict[str, Any],
) -> AgentReviewIssueChain:
    """保存问题链级 AI 预判，不写人工最终结论。"""
    row = get_saved_review_issue_chain(db, farm_id=farm_id, chain_id=chain_id)
    now = datetime.now()
    if row is None:
        row = AgentReviewIssueChain(
            farm_id=farm_id,
            chain_id=chain_id,
            session_id=trigger.session_id,
            trigger_turn_id=trigger.id,
            context_turn_ids=base_chain["context_turn_ids"],
            result_turn_ids=base_chain["result_turn_ids"],
            status=base_chain["status"],
            severity=str(base_chain["severity"]),
            dominant_signal="judge",
            final_labels=[],
            source_label_ids=[],
            created_at=now,
        )
        db.add(row)
    row.ai_judge = dict(ai_judge)
    row.dominant_signal = "judge"
    row.updated_at = now
    return _repo_call(_review_chain_repo(db).save, row)


def _validate_status(status: str) -> None:
    if status not in CHAIN_REVIEW_STATUSES:
        raise ValueError("INVALID_CHAIN_REVIEW_STATUS")


def _validate_required_fields(
    *,
    status: str,
    final_labels: list[str],
    root_cause: str | None,
    expected_behavior: str | None,
    reviewer_comment: str | None,
    false_positive_reason: str | None,
    missing_evidence: list[str],
) -> None:
    if status == "accepted":
        if not root_cause:
            raise ValueError("CHAIN_REVIEW_ROOT_CAUSE_REQUIRED")
        if not final_labels:
            raise ValueError("CHAIN_REVIEW_FINAL_LABELS_REQUIRED")
        if not expected_behavior:
            raise ValueError("CHAIN_REVIEW_EXPECTED_BEHAVIOR_REQUIRED")
    if status == "rejected" and not false_positive_reason:
        raise ValueError("CHAIN_REVIEW_FALSE_POSITIVE_REASON_REQUIRED")
    if status == "needs_evidence" and not missing_evidence:
        raise ValueError("CHAIN_REVIEW_MISSING_EVIDENCE_REQUIRED")
    if status == "needs_evidence" and not reviewer_comment:
        raise ValueError("CHAIN_REVIEW_EVIDENCE_COMMENT_REQUIRED")


def _validate_final_labels(*, final_labels: list[str]) -> None:
    if any(label not in ALLOWED_LABELS for label in final_labels):
        raise ValueError({"code": "INVALID_LABEL", "field": "final_labels"})


def _clean_fix_target(value: str | None) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    return text[:40]


def _final_related_turn_ids(
    db: Session,
    *,
    farm_id: int,
    session_id: str,
    trigger_turn_id: int,
    context_turn_ids: list[int] | None,
    result_turn_ids: list[int] | None,
    base_chain: dict[str, Any],
) -> tuple[list[int], list[int]]:
    context_ids = _unique_ints(
        context_turn_ids
        if context_turn_ids is not None
        else base_chain["context_turn_ids"]
    )
    result_ids = _unique_ints(
        result_turn_ids
        if result_turn_ids is not None
        else base_chain["result_turn_ids"]
    )
    if set(context_ids) & set(result_ids):
        raise ValueError("CHAIN_REVIEW_RELATED_TURN_OVERLAP")
    related_ids = context_ids + result_ids
    if trigger_turn_id in related_ids:
        raise ValueError("CHAIN_REVIEW_RELATED_TURN_INVALID")
    if not related_ids:
        return context_ids, result_ids
    found_ids = {
        turn_id
        for (turn_id,) in db.query(AgentTurn.id)
        .filter(
            AgentTurn.farm_id == farm_id,
            AgentTurn.session_id == session_id,
            AgentTurn.id.in_(related_ids),
        )
        .all()
    }
    if found_ids != set(related_ids):
        raise ValueError("CHAIN_REVIEW_RELATED_TURN_NOT_FOUND")
    return context_ids, result_ids


def _upsert_final_labels(
    db: Session,
    *,
    row: AgentReviewIssueChain,
    farm_id: int,
    trigger: AgentTurn,
    final_labels: list[str],
    reviewer_id: str | None,
) -> list[int]:
    sample_id = _sample_id(trigger)
    source_label_ids = set(row.source_label_ids or [])
    tracked_ids: list[int] = []
    for label in final_labels:
        existing = _find_sample_label(
            db,
            farm_id=farm_id,
            sample_id=sample_id,
            label=label,
        )
        label_row = _upsert_sample_label_row(
            db,
            farm_id=farm_id,
            sample_id=sample_id,
            label=label,
            sample_type=SAMPLE_TYPE_SESSION_TURN,
            session_id=trigger.session_id,
            turn_id=trigger.id,
            request_id=trigger.request_id,
            comment=None,
            annotator_id=reviewer_id,
        )
        db.flush()
        if existing is None or label_row.id in source_label_ids:
            tracked_ids.append(int(label_row.id))
    return tracked_ids


def _resolve_source_labels(
    db: Session,
    *,
    row: AgentReviewIssueChain,
    trigger: AgentTurn,
    source_label_ids: list[int] | None = None,
) -> None:
    label_ids = (
        source_label_ids if source_label_ids is not None else row.source_label_ids
    )
    if not label_ids:
        return
    sample_id = _sample_id(trigger)
    labels = (
        db.query(AgentDataFlywheelLabel)
        .filter(
            AgentDataFlywheelLabel.farm_id == row.farm_id,
            AgentDataFlywheelLabel.sample_id == sample_id,
            AgentDataFlywheelLabel.id.in_(label_ids),
            AgentDataFlywheelLabel.status == LABEL_STATUS_OPEN,
        )
        .all()
    )
    for label in labels:
        label.status = LABEL_STATUS_RESOLVED


def _merge_label_ids(*groups: list[int]) -> list[int]:
    merged: list[int] = []
    for group in groups:
        for label_id in group:
            if label_id not in merged:
                merged.append(label_id)
    return merged


def _find_sample_label(
    db: Session, *, farm_id: int, sample_id: str, label: str
) -> AgentDataFlywheelLabel | None:
    return (
        db.query(AgentDataFlywheelLabel)
        .filter(
            AgentDataFlywheelLabel.farm_id == farm_id,
            AgentDataFlywheelLabel.sample_id == sample_id,
            AgentDataFlywheelLabel.sample_type == SAMPLE_TYPE_SESSION_TURN,
            AgentDataFlywheelLabel.label == label,
        )
        .first()
    )


def _review_chain_repo(db: Session):
    return get_data_flywheel_repository(db, "review_issue_chains")


def _repo_call(method, *args, **kwargs):
    return run_maybe_awaitable(method(*args, **kwargs))


def _human_review_from_row(
    chain: dict[str, Any], row: AgentReviewIssueChain
) -> dict[str, Any]:
    human_review = dict(chain.get("human_review") or {})
    human_review.update(chain_review_to_dict(row))
    human_review["quality_labels"] = row.final_labels or []
    return human_review


def _regression_from_row(
    chain: dict[str, Any], row: AgentReviewIssueChain
) -> dict[str, Any]:
    regression = dict(chain.get("regression") or {})
    final_labels = row.final_labels or []
    regression["needs_regression"] = "needs_regression" in final_labels
    regression["regression_ready"] = bool(
        row.status == "accepted" and row.expected_behavior and final_labels
    )
    regression["expected_behavior"] = row.expected_behavior
    return regression


def _repair_from_row(
    chain: dict[str, Any], row: AgentReviewIssueChain
) -> dict[str, Any]:
    repair = dict(chain.get("repair") or {})
    regression_ready = bool(row.status == "accepted" and row.expected_behavior)
    if row.fix_target:
        repair["fix_target"] = row.fix_target
    repair["regression_ready"] = regression_ready
    repair["export_blocked_reason"] = _export_blocked_reason(row, regression_ready)
    return repair


def _export_blocked_reason(
    row: AgentReviewIssueChain, regression_ready: bool
) -> str | None:
    if row.status == "needs_evidence":
        return "needs_evidence"
    if row.status != "accepted":
        return row.status
    if not regression_ready:
        return "missing_expected_behavior"
    return None


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _clean_list(values: list[Any] | None) -> list[Any]:
    if not values:
        return []
    cleaned: list[Any] = []
    for value in values:
        if isinstance(value, str):
            value = value.strip()
        if value not in (None, ""):
            cleaned.append(value)
    return cleaned


def _unique_ints(values: list[int]) -> list[int]:
    result: list[int] = []
    for value in values:
        turn_id = int(value)
        if turn_id not in result:
            result.append(turn_id)
    return result
