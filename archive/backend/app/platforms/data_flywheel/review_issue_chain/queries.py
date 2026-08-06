"""ReviewIssueChain turn 查询与风险候选筛选。"""

from typing import Any

from sqlalchemy.orm import Session

from app.agent.turn_models import AgentTurn


def _reverse_sort_text(value: str) -> str:
    return "".join(chr(255 - ord(char)) for char in value)


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
