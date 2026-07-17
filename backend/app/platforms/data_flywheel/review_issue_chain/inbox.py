"""ReviewIssueChain 每日质检 inbox 服务。"""

from typing import Any

from sqlalchemy.orm import Session

from app.models.data_flywheel import AgentReviewIssueChain
from app.platforms.data_flywheel.review_issue_chain.cards import (
    _session_card,
    _session_card_from_saved_chain,
)
from app.platforms.data_flywheel.review_issue_chain.constants import (
    MIN_REVIEW_CHAIN_RISK,
)
from app.platforms.data_flywheel.review_issue_chain.queries import (
    _is_benign_chitchat_turn,
    _paged_highest_risk_triggers,
    _reverse_sort_text,
    _risk_session_total,
    _turn_by_id,
)
from app.platforms.data_flywheel.review_issue_chain.support import (
    repo_call as _repo_call,
    review_chain_repo as _review_chain_repo,
)


def list_daily_review_inbox(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None = None,
    min_risk: float = 0.1,
    severity: str = "all",
    status: str = "all",
    evidence_status_value: str = "all",
    dominant_signal_value: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """返回每日质检 inbox 卡片，合并已持久问题链和新风险会话。"""
    min_risk = max(min_risk, MIN_REVIEW_CHAIN_RISK)
    has_card_filters = _has_card_filters(
        status=status,
        evidence_status_value=evidence_status_value,
        dominant_signal_value=dominant_signal_value,
    )
    if has_card_filters:
        return _merged_inbox(
            db,
            farm_id=farm_id,
            session_id=session_id,
            min_risk=min_risk,
            severity=severity,
            status=status,
            evidence_status_value=evidence_status_value,
            dominant_signal_value=dominant_signal_value,
            limit=limit,
            offset=offset,
        )

    persisted_total = _persisted_chain_total(
        db,
        farm_id=farm_id,
        session_id=session_id,
        severity=severity,
    )
    if persisted_total:
        return _merged_inbox(
            db,
            farm_id=farm_id,
            session_id=session_id,
            min_risk=min_risk,
            severity=severity,
            status="all",
            evidence_status_value="all",
            dominant_signal_value="all",
            limit=limit,
            offset=offset,
        )

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


def _has_card_filters(
    *, status: str, evidence_status_value: str, dominant_signal_value: str
) -> bool:
    return (
        status != "all"
        or evidence_status_value != "all"
        or dominant_signal_value != "all"
    )


def _merged_inbox(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    min_risk: float,
    severity: str,
    status: str,
    evidence_status_value: str,
    dominant_signal_value: str,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    rows = _all_persisted_chains(
        db, farm_id=farm_id, session_id=session_id, severity=severity
    )
    persisted_sessions = {row.session_id for row in rows}
    cards = [_session_card_from_saved_chain(db, row) for row in rows]
    virtual_triggers = _paged_highest_risk_triggers(
        db,
        farm_id=farm_id,
        session_id=session_id,
        min_risk=min_risk,
        severity=severity,
        limit=1000,
        offset=0,
    )
    cards.extend(
        _session_card(db, farm_id=farm_id, highest=turn)
        for turn in virtual_triggers
        if turn.session_id not in persisted_sessions
    )
    cards = _filter_cards(
        _sort_inbox_cards(cards),
        status=status,
        evidence_status_value=evidence_status_value,
        dominant_signal_value=dominant_signal_value,
    )
    return _page_cards(cards, limit=limit, offset=offset)


def _filter_cards(
    cards: list[dict[str, Any]],
    *,
    status: str,
    evidence_status_value: str,
    dominant_signal_value: str,
) -> list[dict[str, Any]]:
    return [
        card
        for card in cards
        if _matches_card_filters(
            card,
            status=status,
            evidence_status_value=evidence_status_value,
            dominant_signal_value=dominant_signal_value,
        )
    ]


def _page_cards(
    cards: list[dict[str, Any]], *, limit: int, offset: int
) -> dict[str, Any]:
    start = max(offset, 0)
    end = start + max(limit, 0)
    return {"items": cards[start:end], "total": len(cards)}


def _sort_inbox_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(cards, key=_inbox_card_sort_key)


def _inbox_card_sort_key(card: dict[str, Any]) -> tuple[int, float, str]:
    severity_rank = 0 if card["highest_risk_chain"].get("severity") == "P0" else 1
    risk_score = card.get("session_card", {}).get("risk_score") or 0.0
    updated_at = str(card.get("updated_at") or "")
    return (severity_rank, -float(risk_score), _reverse_sort_text(updated_at))


def _persisted_chain_total(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    severity: str,
) -> int:
    return len(
        _all_persisted_chains(
            db, farm_id=farm_id, session_id=session_id, severity=severity
        )
    )


def _paged_persisted_chains(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    severity: str,
    limit: int,
    offset: int,
) -> list[AgentReviewIssueChain]:
    rows = _all_persisted_chains(
        db, farm_id=farm_id, session_id=session_id, severity=severity
    )
    start = max(offset, 0)
    end = start + max(limit, 0)
    return rows[start:end]


def _all_persisted_chains(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    severity: str,
) -> list[AgentReviewIssueChain]:
    page = _repo_call(
        _review_chain_repo(db).list,
        farm_id=farm_id,
        session_id=session_id,
        severity=severity,
        limit=1000,
        offset=0,
    )
    rows = page.items
    return [row for row in rows if not _is_saved_chain_benign_chitchat(db, row)]


def _persisted_chain_filter(
    query: Any,
    *,
    farm_id: int,
    session_id: str | None,
    severity: str,
) -> Any:
    query = query.filter(
        AgentReviewIssueChain.farm_id == farm_id,
    )
    if session_id:
        query = query.filter(AgentReviewIssueChain.session_id == session_id)
    if severity != "all":
        query = query.filter(AgentReviewIssueChain.severity == severity)
    return query


def _is_saved_chain_benign_chitchat(db: Session, row: AgentReviewIssueChain) -> bool:
    trigger = _turn_by_id(
        db,
        farm_id=row.farm_id,
        session_id=row.session_id,
        turn_id=row.trigger_turn_id,
    )
    return _is_benign_chitchat_turn(trigger)


def _matches_card_filters(
    card: dict[str, Any],
    *,
    status: str,
    evidence_status_value: str,
    dominant_signal_value: str,
) -> bool:
    card_status = str(card.get("status") or "")
    if status == "open" and _is_handled_status(card_status):
        return False
    if status == "handled" and not _is_handled_status(card_status):
        return False
    if status not in {"all", "open", "handled"} and card_status != status:
        return False
    if (
        evidence_status_value != "all"
        and card.get("evidence_status") != evidence_status_value
    ):
        return False
    if (
        dominant_signal_value != "all"
        and card.get("dominant_signal") != dominant_signal_value
    ):
        return False
    return True


def _is_handled_status(status: str) -> bool:
    return status in {"accepted", "rejected", "not_actionable"}
