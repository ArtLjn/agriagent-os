"""Agent turn 聚合记录服务。"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.agent_turn import AgentTurn
from app.models.conversation import Conversation, ConversationMessage

_PREVIEW_LIMIT = 120


def _preview(text: str | None) -> str | None:
    if text is None:
        return None
    clean = " ".join(text.split()).strip()
    if len(clean) <= _PREVIEW_LIMIT:
        return clean
    return f"{clean[:_PREVIEW_LIMIT]}..."


def create_turn(
    db: Session,
    *,
    farm_id: int,
    session_id: str,
    conversation_id: int | None,
    request_id: str,
    user_message_id: int | None,
    input_text: str,
) -> AgentTurn:
    """创建一轮对话聚合记录。"""
    turn = AgentTurn(
        farm_id=farm_id,
        session_id=session_id,
        conversation_id=conversation_id,
        request_id=request_id,
        user_message_id=user_message_id,
        input_preview=_preview(input_text),
        status="running",
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    if conversation_id is not None:
        db.query(Conversation).filter(Conversation.id == conversation_id).update(
            {"last_turn_id": turn.id}
        )
        db.commit()
    return turn


def finish_turn(
    db: Session,
    turn_id: int,
    *,
    reply_text: str,
    assistant_message_id: int | None,
    selected_tools_count: int | None = None,
    tool_calls_count: int | None = None,
    token_total: int | None = None,
    latency_ms: int | None = None,
    status: str = "success",
    pending_plan_id: str | None = None,
) -> AgentTurn:
    """补全一轮对话结果。"""
    turn = db.query(AgentTurn).filter(AgentTurn.id == turn_id).one()
    turn.reply_preview = _preview(reply_text)
    turn.assistant_message_id = _existing_message_id(db, assistant_message_id)
    turn.selected_tools_count = selected_tools_count
    turn.tool_calls_count = tool_calls_count
    turn.token_total = token_total
    turn.latency_ms = latency_ms
    turn.status = status
    turn.pending_plan_id = pending_plan_id
    db.commit()
    db.refresh(turn)
    return turn


def _existing_message_id(db: Session, message_id: int | None) -> int | None:
    if message_id is None:
        return None
    exists = (
        db.query(ConversationMessage.id)
        .filter(ConversationMessage.id == message_id)
        .first()
    )
    return message_id if exists else None


def mark_event_range(
    db: Session,
    turn_id: int,
    *,
    event_file: str | None,
    seq_start: int | None,
    seq_end: int | None,
    write_status: str,
) -> AgentTurn:
    """记录 turn 对应的事件文件范围。"""
    turn = db.query(AgentTurn).filter(AgentTurn.id == turn_id).one()
    turn.event_file = event_file
    turn.event_seq_start = seq_start
    turn.event_seq_end = seq_end
    turn.event_write_status = write_status
    db.commit()
    db.refresh(turn)
    if turn.conversation_id is not None and seq_end is not None:
        db.query(Conversation).filter(Conversation.id == turn.conversation_id).update(
            {"last_event_seq": seq_end, "last_active_at": datetime.now()}
        )
        db.commit()
    return turn


def get_turns_for_session(db: Session, *, farm_id: int, session_id: str) -> list[AgentTurn]:
    """按创建顺序返回会话 turn。"""
    return (
        db.query(AgentTurn)
        .filter(AgentTurn.farm_id == farm_id, AgentTurn.session_id == session_id)
        .order_by(AgentTurn.id.asc())
        .all()
    )
