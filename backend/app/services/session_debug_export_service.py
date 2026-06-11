"""Session debug export v2 组装服务。"""

from typing import Any

from sqlalchemy.orm import Session

from app.infra.agent_events import read_event_segment
from app.models.pending_plan import AgentPendingPlan
from app.services.agent_turn_service import get_turns_for_session
from app.services.conversation_service import (
    get_conversation_by_session,
    get_conversation_messages,
)


def build_session_debug_export(
    db: Session,
    *,
    farm_id: int,
    session_id: str,
) -> dict[str, Any]:
    """组装包含热数据和事件证据的调试 JSON。"""
    conversation = get_conversation_by_session(db, session_id, farm_id=farm_id)
    messages = get_conversation_messages(db, session_id, farm_id=farm_id)
    turns = get_turns_for_session(db, farm_id=farm_id, session_id=session_id)
    pending_plans = (
        db.query(AgentPendingPlan)
        .filter(
            AgentPendingPlan.farm_id == farm_id,
            AgentPendingPlan.session_id == session_id,
        )
        .order_by(AgentPendingPlan.id.asc())
        .all()
    )
    events: list[dict[str, Any]] = []
    missing_segments: list[dict[str, Any]] = []
    for turn in turns:
        if not turn.event_file:
            continue
        rows = read_event_segment(
            turn.event_file, turn.event_seq_start, turn.event_seq_end
        )
        if rows:
            events.extend(rows)
        else:
            missing_segments.append(
                {
                    "turn_id": turn.id,
                    "event_file": turn.event_file,
                    "event_seq_start": turn.event_seq_start,
                    "event_seq_end": turn.event_seq_end,
                }
            )
    return {
        "format": "farm-manager.chat-session-debug.v2",
        "session": {
            "id": conversation.id if conversation else None,
            "farm_id": farm_id,
            "session_id": session_id,
            "status": conversation.status if conversation else None,
            "summary": conversation.summary if conversation else None,
            "created_at": (
                conversation.created_at.isoformat()
                if conversation and conversation.created_at
                else None
            ),
            "last_active_at": (
                conversation.last_active_at.isoformat()
                if conversation and conversation.last_active_at
                else None
            ),
        },
        "messages": [
            {
                "id": message.id,
                "turn_id": message.turn_id,
                "role": message.role,
                "content": message.content,
                "meta": message.meta_json,
                "created_at": message.created_at.isoformat()
                if message.created_at
                else None,
            }
            for message in messages
        ],
        "turns": [
            {
                "id": turn.id,
                "request_id": turn.request_id,
                "input_preview": turn.input_preview,
                "reply_preview": turn.reply_preview,
                "selected_tools_count": turn.selected_tools_count,
                "tool_calls_count": turn.tool_calls_count,
                "token_total": turn.token_total,
                "latency_ms": turn.latency_ms,
                "status": turn.status,
                "pending_plan_id": turn.pending_plan_id,
                "event_file": turn.event_file,
                "event_seq_start": turn.event_seq_start,
                "event_seq_end": turn.event_seq_end,
                "event_write_status": turn.event_write_status,
            }
            for turn in turns
        ],
        "pending_plans": [_pending_plan_to_dict(plan) for plan in pending_plans],
        "events": events,
        "missing_event_segments": missing_segments,
    }


def _pending_plan_to_dict(plan: AgentPendingPlan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "plan_id": plan.plan_id,
        "farm_id": plan.farm_id,
        "session_id": plan.session_id,
        "status": plan.status,
        "current_step_index": plan.current_step_index,
        "raw_user_input": plan.raw_user_input,
        "router_decision": plan.router_decision_json,
        "expires_at": plan.expires_at.isoformat() if plan.expires_at else None,
        "steps": [
            {
                "id": step.id,
                "step_index": step.step_index,
                "skill_name": step.skill_name,
                "params": step.params_json,
                "status": step.status,
                "requires_confirmation": step.requires_confirmation,
                "confirmation_text": step.confirmation_text,
                "result": step.result_json,
                "error_message": step.error_message,
            }
            for step in plan.steps
        ],
    }
