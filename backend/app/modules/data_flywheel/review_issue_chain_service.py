"""DataFlywheel 每日质检虚拟问题链服务。"""

from typing import Any

from sqlalchemy.orm import Session

from app.infra.repository_runtime import (
    get_data_flywheel_repository,
    run_maybe_awaitable,
)
from app.models.agent_turn import AgentTurn
from app.models.data_flywheel import AgentReviewIssueChain
from app.modules.data_flywheel.service import (
    _events_for_turn,
    _labels_by_sample,
    _prelabels_by_sample,
    _sample_id,
    _sample_row,
)
from app.modules.data_flywheel.judge_service import (
    DataFlywheelJudgeClient,
    LABEL_DEFINITIONS,
    LABEL_SELECTION_RULES,
    normalize_judge_output,
)
from app.modules.data_flywheel.issue_repository import (
    build_issue_repository_entry,
    build_rule_candidate_package,
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
    risk_context,
    session_summary,
    severity,
    timeline_turn,
    turn_debug_summary,
    virtual_related_turns,
)
from app.modules.data_flywheel.review_issue_chain_repository import (
    get_saved_review_issue_chain,
    overlay_saved_review,
    save_review_issue_chain_ai_judge,
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


def _reverse_sort_text(value: str) -> str:
    return "".join(chr(255 - ord(char)) for char in value)


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


def _is_benign_chitchat_turn(turn: AgentTurn) -> bool:
    text = (turn.input_preview or "").strip().lower()
    return (
        (turn.rule_score or 0.0) <= 0
        and (turn.selected_tools_count or 0) == 0
        and (turn.tool_calls_count or 0) == 0
        and text in {"hi", "hello", "hey", "你好", "您好", "嗨", "哈喽"}
    )


def _risk_session_total(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    min_risk: float,
    severity: str,
) -> int:
    return len(
        {
            turn.session_id
            for turn in _risk_candidate_turns(
                db,
                farm_id=farm_id,
                session_id=session_id,
                min_risk=min_risk,
                severity=severity,
            )
        }
    )


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
    turns_by_session: dict[str, AgentTurn] = {}
    for turn in _risk_candidate_turns(
        db,
        farm_id=farm_id,
        session_id=session_id,
        min_risk=min_risk,
        severity=severity,
    ):
        existing = turns_by_session.get(turn.session_id)
        if existing is None or _risk_turn_sort_key(turn) < _risk_turn_sort_key(
            existing
        ):
            turns_by_session[turn.session_id] = turn
    turns = sorted(turns_by_session.values(), key=_risk_turn_sort_key)
    start = max(offset, 0)
    end = start + max(limit, 0)
    return turns[start:end]


def _risk_candidate_turns(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    min_risk: float,
    severity: str,
) -> list[AgentTurn]:
    query = _risk_filter(
        db.query(AgentTurn),
        farm_id=farm_id,
        session_id=session_id,
        min_risk=min_risk,
        severity=severity,
    )
    return [turn for turn in query.all() if not _is_benign_chitchat_turn(turn)]


def _risk_turn_sort_key(turn: AgentTurn) -> tuple[float, str, int]:
    risk_score = turn.risk_score or 0.0
    created_at = turn.created_at.isoformat() if turn.created_at else ""
    return (-float(risk_score), _reverse_sort_text(created_at), -turn.id)


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
        "risk_context": risk_context(sample),
        "diagnosis": diagnosis(sample),
        "ai_judge": ai_judge(sample),
        "human_review": human_review(labels),
        "regression": regression_status(sample, labels),
        "repair": repair_status(status, sample),
        "evidence_checklist": evidence,
        "sample": sample,
    }


def _chain_judge_input(
    db: Session,
    *,
    chain: dict[str, Any],
    trigger: AgentTurn,
    context_turns: list[AgentTurn],
    result_turns: list[AgentTurn],
) -> dict[str, Any]:
    return {
        "task": "judge_review_issue_chain",
        "prompt_version": "data-flywheel-chain-judge-v1",
        "judge_instructions": (
            "请基于完整 ReviewIssueChain evidence pack 给出 AI 预判。"
            "只能输出建议标签、根因草稿、置信度、理由和修复建议；"
            "不能输出最终人工结论。所有自然语言字段必须使用简体中文。"
        ),
        "label_definitions": LABEL_DEFINITIONS,
        "label_selection_rules": LABEL_SELECTION_RULES,
        "chain": {
            "chain_id": chain["chain_id"],
            "session_id": chain["session_id"],
            "trigger_turn_id": chain["trigger_turn_id"],
            "status": chain["status"],
            "severity": chain["severity"],
            "dominant_signal": chain["dominant_signal"],
            "diagnosis": chain["diagnosis"],
            "evidence_status": evidence_status(chain["evidence_checklist"]),
            "evidence_checklist": chain["evidence_checklist"],
        },
        "trigger_turn": turn_debug_summary(db, trigger),
        "context_turns": [turn_debug_summary(db, turn) for turn in context_turns],
        "result_turns": [turn_debug_summary(db, turn) for turn in result_turns],
        "output_schema": {
            "type": "object",
            "required": [
                "labels",
                "root_cause",
                "severity",
                "confidence",
                "reason",
                "recommended_fix",
            ],
            "properties": {
                "labels": {"type": "array", "items": {"type": "string"}},
                "root_cause": {"type": ["string", "null"]},
                "severity": {"type": "string"},
                "confidence": {"type": "number"},
                "reason": {"type": "string"},
                "recommended_fix": {"type": ["string", "null"]},
                "missing_evidence": {"type": "array", "items": {"type": "string"}},
            },
        },
    }


def _chain_ai_judge_result(
    *,
    normalized: dict[str, Any],
    judge_client: DataFlywheelJudgeClient,
    chain_id: str,
    evidence_status_value: str,
) -> dict[str, Any]:
    labels = [str(label) for label in normalized.get("labels") or []]
    return {
        "judge_id": f"chain-judge:{chain_id}",
        "chain_id": chain_id,
        "bad_prob": normalized.get("confidence", 0.0),
        "confidence": normalized.get("confidence", 0.0),
        "severity": normalized.get("severity"),
        "issue_type": labels[0] if labels else "not_actionable",
        "suggested_label": labels[0] if labels else "not_actionable",
        "suggested_labels": labels,
        "root_cause": normalized.get("root_cause") or None,
        "reason": normalized.get("reason"),
        "recommended_fix": normalized.get("recommended_fix") or None,
        "missing_evidence": normalized.get("missing_evidence") or [],
        "evidence_status": evidence_status_value,
        "judge_model": judge_client.judge_model,
        "prompt_version": judge_client.prompt_version,
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


def _turn_by_id_any_session(db: Session, *, farm_id: int, turn_id: int) -> AgentTurn:
    turn = (
        db.query(AgentTurn)
        .filter(
            AgentTurn.farm_id == farm_id,
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


def _review_chain_repo(db: Session):
    return get_data_flywheel_repository(db, "review_issue_chains")


def _repo_call(method, *args, **kwargs):
    return run_maybe_awaitable(method(*args, **kwargs))
