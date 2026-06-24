"""DataFlywheel 每日质检虚拟问题链服务。"""

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent_turn import AgentTurn
from app.modules.data_flywheel.service import (
    _events_for_turn,
    _labels_by_sample,
    _prelabels_by_sample,
    _sample_id,
    _sample_row,
)
from app.modules.data_flywheel.review_issue_chain_helpers import (
    ai_judge,
    chain_id,
    diagnosis,
    dominant_signal,
    evidence_checklist,
    evidence_status,
    human_review,
    next_action,
    parse_chain_id,
    public_chain,
    regression_status,
    repair_status,
    session_summary,
    severity,
    timeline_turn,
    turn_debug_summary,
    virtual_related_turns,
)
from app.modules.data_flywheel.review_issue_chain_repository import (
    get_saved_review_issue_chain,
    overlay_saved_review,
    save_review_issue_chain,
)

MIN_REVIEW_CHAIN_RISK = 0.1


def list_daily_review_inbox(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None = None,
    min_risk: float = 0.1,
    severity: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """按 session 聚合风险 turn，返回每日质检 inbox 卡片。"""
    min_risk = max(min_risk, MIN_REVIEW_CHAIN_RISK)
    total = _risk_session_total(
        db,
        farm_id=farm_id,
        session_id=session_id,
        min_risk=min_risk,
        severity=severity,
    )
    triggers = _paged_highest_risk_triggers(
        db,
        farm_id=farm_id,
        session_id=session_id,
        min_risk=min_risk,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    cards = [_session_card(db, farm_id=farm_id, highest=turn) for turn in triggers]
    return {"items": cards, "total": total}


def get_review_issue_chain_detail(
    db: Session, *, farm_id: int, chain_id: str
) -> dict[str, Any]:
    """返回虚拟 ReviewIssueChain 详情和完整 session timeline。"""
    parsed = parse_chain_id(chain_id)
    if parsed["farm_id"] != farm_id:
        raise ValueError("CHAIN_NOT_FOUND")
    trigger = _turn_by_id(
        db,
        farm_id=farm_id,
        session_id=str(parsed["session_id"]),
        turn_id=int(parsed["turn_id"]),
    )
    if (trigger.risk_score or 0.0) < MIN_REVIEW_CHAIN_RISK:
        raise ValueError("CHAIN_NOT_FOUND")
    session_turns = _session_turns(db, farm_id=farm_id, session_id=trigger.session_id)
    context_turns, result_turns = virtual_related_turns(session_turns, trigger)
    chain = _chain_for_turn(
        db,
        farm_id=farm_id,
        trigger=trigger,
        context_turns=context_turns,
        result_turns=result_turns,
    )
    saved = get_saved_review_issue_chain(db, farm_id=farm_id, chain_id=chain_id)
    chain = overlay_saved_review(chain, saved)
    related = _related_turns_from_chain(session_turns, chain)
    timeline = [timeline_turn(db, turn, chain=chain) for turn in session_turns]
    evidence = chain["evidence_checklist"]
    return {
        "chain": public_chain(chain),
        "session_id": trigger.session_id,
        "timeline": timeline,
        "trigger_turn": timeline_turn(db, trigger, chain=chain),
        "context_turns": [
            timeline_turn(db, turn, chain=chain) for turn in related["context_turns"]
        ],
        "result_turns": [
            timeline_turn(db, turn, chain=chain) for turn in related["result_turns"]
        ],
        "turn_debug_summaries": {
            turn.id: turn_debug_summary(db, turn) for turn in session_turns
        },
        "evidence_checklist": evidence,
        "evidence_status": evidence_status(evidence),
        "existing_labels": chain["human_review"]["labels"],
        "ai_judge": chain["ai_judge"],
    }


def save_review_issue_chain_review(
    db: Session,
    *,
    farm_id: int,
    chain_id: str,
    status: str,
    context_turn_ids: list[int] | None = None,
    result_turn_ids: list[int] | None = None,
    final_labels: list[str] | None = None,
    root_cause: str | None = None,
    expected_behavior: str | None = None,
    false_positive_reason: str | None = None,
    missing_evidence: list[str] | None = None,
    reviewer_id: str | None = None,
) -> dict[str, Any]:
    """保存 ReviewIssueChain 人工审核结论。"""
    parsed = parse_chain_id(chain_id)
    if parsed["farm_id"] != farm_id:
        raise ValueError("CHAIN_NOT_FOUND")
    trigger = _turn_by_id(
        db,
        farm_id=farm_id,
        session_id=str(parsed["session_id"]),
        turn_id=int(parsed["turn_id"]),
    )
    if (trigger.risk_score or 0.0) < MIN_REVIEW_CHAIN_RISK:
        raise ValueError("CHAIN_NOT_FOUND")
    session_turns = _session_turns(db, farm_id=farm_id, session_id=trigger.session_id)
    context_turns, result_turns = virtual_related_turns(session_turns, trigger)
    chain = _chain_for_turn(
        db,
        farm_id=farm_id,
        trigger=trigger,
        context_turns=context_turns,
        result_turns=result_turns,
    )
    row = save_review_issue_chain(
        db,
        farm_id=farm_id,
        chain_id=chain_id,
        trigger=trigger,
        base_chain=chain,
        status=status,
        context_turn_ids=context_turn_ids,
        result_turn_ids=result_turn_ids,
        final_labels=final_labels,
        root_cause=root_cause,
        expected_behavior=expected_behavior,
        false_positive_reason=false_positive_reason,
        missing_evidence=missing_evidence,
        reviewer_id=reviewer_id,
    )
    chain = overlay_saved_review(chain, row)
    return {"chain": public_chain(chain)}


def _risk_filter(
    query: Any,
    *,
    farm_id: int,
    session_id: str | None,
    min_risk: float,
    severity: str,
) -> Any:
    query = query.filter(
        AgentTurn.farm_id == farm_id,
        AgentTurn.risk_score >= min_risk,
    )
    if session_id:
        query = query.filter(AgentTurn.session_id == session_id)
    if severity != "all":
        query = query.filter(AgentTurn.risk_severity == severity)
    return query


def _risk_session_total(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    min_risk: float,
    severity: str,
) -> int:
    query = _risk_filter(
        db.query(AgentTurn.session_id),
        farm_id=farm_id,
        session_id=session_id,
        min_risk=min_risk,
        severity=severity,
    )
    return query.distinct().count()


def _paged_highest_risk_triggers(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    min_risk: float,
    severity: str,
    limit: int,
    offset: int,
) -> list[AgentTurn]:
    max_risk_query = _risk_filter(
        db.query(
            AgentTurn.session_id.label("session_id"),
            func.max(AgentTurn.risk_score).label("max_risk"),
        ),
        farm_id=farm_id,
        session_id=session_id,
        min_risk=min_risk,
        severity=severity,
    ).group_by(AgentTurn.session_id)
    max_risk = max_risk_query.subquery()
    max_id_query = (
        _risk_filter(
            db.query(
                AgentTurn.session_id.label("session_id"),
                func.max(AgentTurn.id).label("max_id"),
            ),
            farm_id=farm_id,
            session_id=session_id,
            min_risk=min_risk,
            severity=severity,
        )
        .join(
            max_risk,
            (AgentTurn.session_id == max_risk.c.session_id)
            & (AgentTurn.risk_score == max_risk.c.max_risk),
        )
        .group_by(AgentTurn.session_id)
    )
    max_id = max_id_query.subquery()
    return (
        db.query(AgentTurn)
        .join(max_id, AgentTurn.id == max_id.c.max_id)
        .order_by(
            AgentTurn.risk_score.desc(),
            AgentTurn.created_at.desc(),
            AgentTurn.id.desc(),
        )
        .offset(max(offset, 0))
        .limit(max(limit, 0))
        .all()
    )


def _session_card(db: Session, *, farm_id: int, highest: AgentTurn) -> dict[str, Any]:
    session_turns = _session_turns(db, farm_id=farm_id, session_id=highest.session_id)
    context_turns, result_turns = virtual_related_turns(session_turns, highest)
    candidate_chain_count = _candidate_chain_count(
        db, farm_id=farm_id, session_id=highest.session_id
    )
    chain = _chain_for_turn(
        db,
        farm_id=farm_id,
        trigger=highest,
        context_turns=context_turns,
        result_turns=result_turns,
    )
    saved = get_saved_review_issue_chain(
        db, farm_id=farm_id, chain_id=str(chain["chain_id"])
    )
    chain = overlay_saved_review(chain, saved)
    evidence_status_value = evidence_status(chain["evidence_checklist"])
    return {
        "session_id": highest.session_id,
        "session_card": {
            "session_id": highest.session_id,
            "summary": session_summary(highest),
            "latest_turn_id": max(turn.id for turn in session_turns),
            "risk_score": highest.risk_score,
            "severity": chain["severity"],
        },
        "highest_risk_chain": public_chain(chain),
        "candidate_chain_count": candidate_chain_count,
        "evidence_status": evidence_status_value,
        "next_action": _next_action_for_chain(
            status=str(chain["status"]),
            evidence_status_value=evidence_status_value,
        ),
        "status": chain["status"],
        "dominant_signal": chain["dominant_signal"],
        "updated_at": highest.created_at.isoformat() if highest.created_at else None,
    }


def _next_action_for_chain(*, status: str, evidence_status_value: str) -> str:
    if status in {"accepted", "rejected", "not_actionable"}:
        return "done"
    if status == "needs_evidence":
        return "collect_evidence"
    return next_action(evidence_status_value)


def _candidate_chain_count(db: Session, *, farm_id: int, session_id: str) -> int:
    return (
        db.query(AgentTurn.id)
        .filter(
            AgentTurn.farm_id == farm_id,
            AgentTurn.session_id == session_id,
            AgentTurn.risk_score >= MIN_REVIEW_CHAIN_RISK,
        )
        .count()
    )


def _chain_for_turn(
    db: Session,
    *,
    farm_id: int,
    trigger: AgentTurn,
    context_turns: list[AgentTurn],
    result_turns: list[AgentTurn],
) -> dict[str, Any]:
    sample_id = _sample_id(trigger)
    labels = _labels_by_sample(db, [sample_id]).get(sample_id, [])
    prelabels = _prelabels_by_sample(db, farm_id=farm_id, sample_ids=[sample_id]).get(
        sample_id, []
    )
    events = _events_for_turn(trigger)
    sample = _sample_row(trigger, labels, events, prelabels=prelabels)
    evidence = evidence_checklist(db, trigger, events)
    status = (
        "needs_evidence"
        if evidence_status(evidence) == "needs_evidence"
        else "ready_for_review"
    )
    return {
        "chain_id": chain_id(trigger),
        "session_id": trigger.session_id,
        "trigger_turn_id": trigger.id,
        "context_turn_ids": [turn.id for turn in context_turns],
        "result_turn_ids": [turn.id for turn in result_turns],
        "status": status,
        "severity": severity(sample),
        "dominant_signal": dominant_signal(sample),
        "diagnosis": diagnosis(sample),
        "ai_judge": ai_judge(sample),
        "human_review": human_review(labels),
        "regression": regression_status(sample, labels),
        "repair": repair_status(status, sample),
        "evidence_checklist": evidence,
        "sample": sample,
    }


def _turn_by_id(
    db: Session, *, farm_id: int, session_id: str, turn_id: int
) -> AgentTurn:
    turn = (
        db.query(AgentTurn)
        .filter(
            AgentTurn.farm_id == farm_id,
            AgentTurn.session_id == session_id,
            AgentTurn.id == turn_id,
        )
        .first()
    )
    if turn is None:
        raise ValueError("CHAIN_NOT_FOUND")
    return turn


def _session_turns(db: Session, *, farm_id: int, session_id: str) -> list[AgentTurn]:
    return (
        db.query(AgentTurn)
        .filter(AgentTurn.farm_id == farm_id, AgentTurn.session_id == session_id)
        .order_by(AgentTurn.created_at.asc(), AgentTurn.id.asc())
        .all()
    )


def _related_turns_from_chain(
    session_turns: list[AgentTurn], chain: dict[str, Any]
) -> dict[str, list[AgentTurn]]:
    by_id = {turn.id: turn for turn in session_turns}
    return {
        "context_turns": [
            by_id[turn_id] for turn_id in chain["context_turn_ids"] if turn_id in by_id
        ],
        "result_turns": [
            by_id[turn_id] for turn_id in chain["result_turn_ids"] if turn_id in by_id
        ],
    }


def _chain_id(turn: AgentTurn) -> str:
    return f"chain:{turn.farm_id}:{turn.session_id}:{turn.id}"
