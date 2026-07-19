"""ReviewIssueChain inbox 卡片组装。"""

from typing import Any

from sqlalchemy.orm import Session

from app.agent.turn_models import AgentTurn
from app.platforms.data_flywheel.models import AgentReviewIssueChain
from app.platforms.data_flywheel.issue_repository import (
    build_issue_repository_entry,
    build_rule_candidate_package,
)
from app.platforms.data_flywheel.review_issue_chain.builders import _chain_for_turn
from app.platforms.data_flywheel.review_issue_chain.constants import (
    MIN_REVIEW_CHAIN_RISK,
)
from app.platforms.data_flywheel.review_issue_chain.helpers import (
    evidence_status,
    next_action,
    public_chain,
    session_summary,
    turn_debug_summary,
    virtual_related_turns,
)
from app.platforms.data_flywheel.review_issue_chain.queries import (
    _session_turns,
    _turn_by_id,
)
from app.platforms.data_flywheel.review_issue_chain.support import (
    repo_call as _repo_call,
    review_chain_repo as _review_chain_repo,
)
from app.platforms.data_flywheel.review_issue_chain_repository import (
    get_saved_review_issue_chain,
    overlay_saved_review,
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


def _session_card_from_saved_chain(
    db: Session, row: AgentReviewIssueChain
) -> dict[str, Any]:
    trigger = _turn_by_id(
        db,
        farm_id=row.farm_id,
        session_id=row.session_id,
        turn_id=row.trigger_turn_id,
    )
    session_turns = _session_turns(db, farm_id=row.farm_id, session_id=row.session_id)
    context_turns, result_turns = virtual_related_turns(session_turns, trigger)
    chain = _chain_for_turn(
        db,
        farm_id=row.farm_id,
        trigger=trigger,
        context_turns=context_turns,
        result_turns=result_turns,
    )
    chain = overlay_saved_review(chain, row)
    evidence_status_value = evidence_status(chain["evidence_checklist"])
    return {
        "session_id": row.session_id,
        "session_card": {
            "session_id": row.session_id,
            "summary": session_summary(trigger),
            "latest_turn_id": max(turn.id for turn in session_turns),
            "risk_score": trigger.risk_score,
            "severity": chain["severity"],
        },
        "highest_risk_chain": public_chain(chain),
        "candidate_chain_count": _persisted_session_chain_count(
            db, farm_id=row.farm_id, session_id=row.session_id
        ),
        "evidence_status": evidence_status_value,
        "next_action": _next_action_for_chain(
            status=str(chain["status"]),
            evidence_status_value=evidence_status_value,
        ),
        "status": chain["status"],
        "dominant_signal": chain["dominant_signal"],
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
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


def _persisted_session_chain_count(
    db: Session, *, farm_id: int, session_id: str
) -> int:
    page = _repo_call(
        _review_chain_repo(db).list_by_session,
        farm_id=farm_id,
        session_id=session_id,
        limit=1,
        offset=0,
    )
    return page.total


def _issue_repository_projection(
    db: Session,
    *,
    saved: AgentReviewIssueChain | None,
    trigger: AgentTurn,
) -> dict[str, Any]:
    if saved is None or saved.status != "accepted":
        return {
            "issue_repository_entry": None,
            "rule_candidate_package": None,
        }
    summary = turn_debug_summary(db, trigger)
    issue_entry = build_issue_repository_entry(
        saved,
        user_input=trigger.input_preview,
        assistant_reply=trigger.reply_preview,
        actual_skill=_actual_skill(summary),
        expected_skill=_expected_skill(saved=saved, trigger=trigger),
        source="manual_test",
    )
    return {
        "issue_repository_entry": issue_entry,
        "rule_candidate_package": build_rule_candidate_package(issue_entry),
    }


def _actual_skill(summary: dict[str, Any]) -> str | None:
    selected_tools = summary.get("selected_tools") or []
    if not selected_tools:
        return None
    return str(selected_tools[0])


def _expected_skill(
    *,
    saved: AgentReviewIssueChain,
    trigger: AgentTurn,
) -> str | None:
    text = " ".join(
        item
        for item in (trigger.input_preview, saved.expected_behavior)
        if isinstance(item, str)
    )
    if _looks_like_crop_inventory_issue(text):
        return "get_crop_cycles"
    return None


def _looks_like_crop_inventory_issue(text: str) -> bool:
    inventory_terms = (
        "我的作物",
        "作物栽种",
        "种了哪些作物",
        "种植哪些作物",
        "地里都种",
        "茬口列表",
        "茬口",
    )
    return any(term in text for term in inventory_terms)
