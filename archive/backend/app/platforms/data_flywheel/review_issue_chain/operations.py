"""ReviewIssueChain 详情、人工审核与 AI judge 操作。"""

from typing import Any

from sqlalchemy.orm import Session

from app.platforms.shared.judge_service import (
    DataFlywheelJudgeClient,
    normalize_judge_output,
)
from app.platforms.data_flywheel.review_issue_chain.builders import (
    _chain_ai_judge_result,
    _chain_for_turn,
    _chain_judge_input,
)
from app.platforms.data_flywheel.review_issue_chain.cards import (
    _issue_repository_projection,
)
from app.platforms.data_flywheel.review_issue_chain.constants import (
    MIN_REVIEW_CHAIN_RISK,
)
from app.platforms.data_flywheel.review_issue_chain.helpers import (
    evidence_status,
    parse_chain_id,
    public_chain,
    timeline_turn,
    turn_debug_summary,
    virtual_related_turns,
)
from app.platforms.data_flywheel.review_issue_chain.queries import (
    _related_turns_from_chain,
    _session_turns,
    _turn_by_id,
    _turn_by_id_any_session,
)
from app.platforms.data_flywheel.review_issue_chain_repository import (
    get_saved_review_issue_chain,
    overlay_saved_review,
    save_review_issue_chain,
    save_review_issue_chain_ai_judge,
)


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
    saved = get_saved_review_issue_chain(db, farm_id=farm_id, chain_id=chain_id)
    if saved is None and (trigger.risk_score or 0.0) < MIN_REVIEW_CHAIN_RISK:
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
        **_issue_repository_projection(db, saved=saved, trigger=trigger),
    }


def create_review_issue_chain_candidate(
    db: Session,
    *,
    farm_id: int,
    trigger_turn_id: int,
    context_turn_ids: list[int] | None = None,
    result_turn_ids: list[int] | None = None,
    severity: str | None = None,
    dominant_signal: str | None = None,
    missing_evidence: list[str] | None = None,
    reviewer_id: str | None = None,
) -> dict[str, Any]:
    """从 raw turn 创建或更新每日质检候选链。"""
    trigger = _turn_by_id_any_session(db, farm_id=farm_id, turn_id=trigger_turn_id)
    session_turns = _session_turns(db, farm_id=farm_id, session_id=trigger.session_id)
    default_context, default_result = virtual_related_turns(session_turns, trigger)
    chain = _chain_for_turn(
        db,
        farm_id=farm_id,
        trigger=trigger,
        context_turns=default_context,
        result_turns=default_result,
    )
    chain["severity"] = severity or chain["severity"]
    chain["dominant_signal"] = dominant_signal or chain["dominant_signal"]
    row = save_review_issue_chain(
        db,
        farm_id=farm_id,
        chain_id=str(chain["chain_id"]),
        trigger=trigger,
        base_chain=chain,
        status="needs_evidence",
        context_turn_ids=context_turn_ids,
        result_turn_ids=result_turn_ids,
        missing_evidence=missing_evidence or ["evidence"],
        reviewer_comment="从高级搜索创建候选链，等待人工补齐证据。",
        reviewer_id=reviewer_id,
    )
    chain = overlay_saved_review(chain, row)
    return {"chain": public_chain(chain)}


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
    fix_target: str | None = None,
    reviewer_comment: str | None = None,
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
    saved = get_saved_review_issue_chain(db, farm_id=farm_id, chain_id=chain_id)
    if saved is None and (trigger.risk_score or 0.0) < MIN_REVIEW_CHAIN_RISK:
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
        fix_target=fix_target,
        reviewer_comment=reviewer_comment,
        false_positive_reason=false_positive_reason,
        missing_evidence=missing_evidence,
        reviewer_id=reviewer_id,
    )
    chain = overlay_saved_review(chain, row)
    return {"chain": public_chain(chain)}


def run_review_issue_chain_ai_judge(
    db: Session,
    *,
    farm_id: int,
    chain_id: str,
    judge_client: DataFlywheelJudgeClient,
) -> dict[str, Any]:
    """为 ReviewIssueChain 构造 evidence pack 并保存 AI 预判。"""
    parsed = parse_chain_id(chain_id)
    if parsed["farm_id"] != farm_id:
        raise ValueError("CHAIN_NOT_FOUND")
    trigger = _turn_by_id(
        db,
        farm_id=farm_id,
        session_id=str(parsed["session_id"]),
        turn_id=int(parsed["turn_id"]),
    )
    saved = get_saved_review_issue_chain(db, farm_id=farm_id, chain_id=chain_id)
    if saved is None and (trigger.risk_score or 0.0) < MIN_REVIEW_CHAIN_RISK:
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
    chain = overlay_saved_review(chain, saved)
    related = _related_turns_from_chain(session_turns, chain)
    evidence_pack = _chain_judge_input(
        db,
        chain=chain,
        trigger=trigger,
        context_turns=related["context_turns"],
        result_turns=related["result_turns"],
    )
    normalized = normalize_judge_output(judge_client.judge(evidence_pack))
    ai_judge_result = _chain_ai_judge_result(
        normalized=normalized,
        judge_client=judge_client,
        chain_id=chain_id,
        evidence_status_value=evidence_status(chain["evidence_checklist"]),
    )
    row = save_review_issue_chain_ai_judge(
        db,
        farm_id=farm_id,
        chain_id=chain_id,
        trigger=trigger,
        base_chain=chain,
        ai_judge=ai_judge_result,
    )
    chain = overlay_saved_review(chain, row)
    return {"chain": public_chain(chain)}
