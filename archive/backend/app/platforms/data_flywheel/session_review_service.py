"""Agent 数据飞轮会话审阅服务。"""

from typing import Any

from sqlalchemy.orm import Session

from app.agent.turn_models import AgentTurn
from app.platforms.data_flywheel.service import (
    _actual_tools,
    _event_log_status,
    _events_for_turn,
    _labels_by_sample,
    _messages_for_turn,
    _pending_lifecycle,
    _router_decision,
    _sample_id,
    _selected_tools,
    _tool_events,
)
from app.platforms.data_flywheel.service_serializers import sample_row, source_to_dict


def get_session_review(db: Session, *, farm_id: int, session_id: str) -> dict[str, Any]:
    """返回单个会话的完整 turn 审阅时间线。"""
    turns = (
        db.query(AgentTurn)
        .filter(
            AgentTurn.farm_id == farm_id,
            AgentTurn.session_id == session_id,
        )
        .order_by(AgentTurn.created_at.asc(), AgentTurn.id.asc())
        .all()
    )
    sample_ids = [_sample_id(turn) for turn in turns]
    labels = _labels_by_sample(db, sample_ids)
    return {
        "session_id": session_id,
        "turns": [
            _turn_review_row(db, turn, labels.get(_sample_id(turn), []))
            for turn in turns
        ],
    }


def _turn_review_row(db: Session, turn: AgentTurn, labels: list[Any]) -> dict[str, Any]:
    events = _events_for_turn(turn)
    return {
        "sample": sample_row(
            turn,
            labels,
            events,
            selected_tools=_selected_tools(_router_decision(events)),
            actual_tools=_actual_tools(events),
            pending_lifecycle=_pending_lifecycle(events),
            event_log_status=_event_log_status(turn, events),
        ),
        "messages": _messages_for_turn(db, turn),
        "router_decision": _router_decision(events),
        "tool_events": _tool_events(events),
        "pending_lifecycle": _pending_lifecycle(events),
        "source": source_to_dict(turn, _event_log_status(turn, events)),
    }
