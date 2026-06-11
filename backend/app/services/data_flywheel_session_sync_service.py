"""数据库会话到 Agent 事件日志的补齐同步服务。"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.infra.agent_events import AgentEventWriter, read_event_segment
from app.models.agent_turn import AgentTurn
from app.models.conversation import Conversation, ConversationMessage
from app.services.agent_turn_service import create_turn, finish_turn, mark_event_range


@dataclass
class SessionSyncResult:
    """会话事件同步统计结果。"""

    scanned_sessions: int = 0
    created_turns: int = 0
    synced_turns: int = 0
    skipped_turns: int = 0
    failed_turns: int = 0
    failures: list[dict[str, str | int | None]] = field(default_factory=list)

    def to_dict(self) -> dict[str, int | list[dict[str, str | int | None]]]:
        """转换为 API 友好的字典。"""
        return {
            "scanned_sessions": self.scanned_sessions,
            "created_turns": self.created_turns,
            "synced_turns": self.synced_turns,
            "skipped_turns": self.skipped_turns,
            "failed_turns": self.failed_turns,
            "failures": self.failures,
        }


def sync_session_events(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None = None,
    only_missing: bool = True,
    event_base_dir: str | Path = "data/agent-events",
    limit: int = 100,
) -> dict[str, int | list[dict[str, str | int | None]]]:
    """将数据库中已有会话补齐为 JSONL 事件日志。"""
    conversations = _query_conversations(
        db,
        farm_id=farm_id,
        session_id=session_id,
        limit=limit,
    )
    result = SessionSyncResult(scanned_sessions=len(conversations))
    writer = AgentEventWriter(event_base_dir)

    for conversation in conversations:
        _sync_conversation(
            db,
            conversation=conversation,
            writer=writer,
            only_missing=only_missing,
            result=result,
        )
    return result.to_dict()


def _query_conversations(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    limit: int,
) -> list[Conversation]:
    query = db.query(Conversation).filter(Conversation.farm_id == farm_id)
    if session_id:
        query = query.filter(Conversation.session_id == session_id)
    return (
        query.order_by(Conversation.last_active_at.desc(), Conversation.id.desc())
        .limit(max(limit, 1))
        .all()
    )


def _sync_conversation(
    db: Session,
    *,
    conversation: Conversation,
    writer: AgentEventWriter,
    only_missing: bool,
    result: SessionSyncResult,
) -> None:
    turns = _turns_for_conversation(db, conversation)
    existing_turn_ids = {turn.id for turn in turns}
    for turn in turns:
        _sync_existing_turn(
            db,
            conversation=conversation,
            turn=turn,
            writer=writer,
            only_missing=only_missing,
            result=result,
        )

    messages = _messages_for_conversation(db, conversation)
    for user_msg, assistant_msg in _unlinked_pairs(messages, existing_turn_ids):
        turn = _create_turn_from_messages(
            db,
            conversation=conversation,
            user_msg=user_msg,
            assistant_msg=assistant_msg,
        )
        result.created_turns += 1
        _write_turn_events(
            db,
            conversation=conversation,
            turn=turn,
            user_msg=user_msg,
            assistant_msg=assistant_msg,
            writer=writer,
            result=result,
        )


def _create_turn_from_messages(
    db: Session,
    *,
    conversation: Conversation,
    user_msg: ConversationMessage,
    assistant_msg: ConversationMessage,
) -> AgentTurn:
    turn = create_turn(
        db,
        farm_id=conversation.farm_id,
        session_id=conversation.session_id,
        conversation_id=conversation.id,
        request_id=_backfill_request_id(conversation.id, user_msg.id),
        user_message_id=user_msg.id,
        input_text=user_msg.content,
    )
    user_msg.turn_id = turn.id
    db.commit()
    turn = finish_turn(
        db,
        turn.id,
        reply_text=assistant_msg.content,
        assistant_message_id=assistant_msg.id,
        status="success",
    )
    assistant_msg.turn_id = turn.id
    db.commit()
    return turn


def _sync_existing_turn(
    db: Session,
    *,
    conversation: Conversation,
    turn: AgentTurn,
    writer: AgentEventWriter,
    only_missing: bool,
    result: SessionSyncResult,
) -> None:
    if only_missing and _has_readable_event_range(turn):
        result.skipped_turns += 1
        return

    user_msg = _message_for_turn(db, turn, "user")
    assistant_msg = _message_for_turn(db, turn, "assistant")
    if user_msg is None or assistant_msg is None:
        result.failed_turns += 1
        result.failures.append(
            {
                "session_id": conversation.session_id,
                "turn_id": turn.id,
                "reason": "TURN_MESSAGES_INCOMPLETE",
            }
        )
        return

    _write_turn_events(
        db,
        conversation=conversation,
        turn=turn,
        user_msg=user_msg,
        assistant_msg=assistant_msg,
        writer=writer,
        result=result,
    )


def _turns_for_conversation(db: Session, conversation: Conversation) -> list[AgentTurn]:
    return (
        db.query(AgentTurn)
        .filter(
            AgentTurn.farm_id == conversation.farm_id,
            AgentTurn.session_id == conversation.session_id,
            AgentTurn.conversation_id == conversation.id,
        )
        .order_by(AgentTurn.id.asc())
        .all()
    )


def _messages_for_conversation(
    db: Session, conversation: Conversation
) -> list[ConversationMessage]:
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        .all()
    )


def _unlinked_pairs(
    messages: list[ConversationMessage],
    existing_turn_ids: set[int],
) -> list[tuple[ConversationMessage, ConversationMessage]]:
    pairs: list[tuple[ConversationMessage, ConversationMessage]] = []
    pending_user: ConversationMessage | None = None
    for message in messages:
        if message.turn_id in existing_turn_ids:
            pending_user = None if message.role == "user" else pending_user
            continue
        if message.role == "user":
            pending_user = message
            continue
        if message.role == "assistant" and pending_user is not None:
            pairs.append((pending_user, message))
            pending_user = None
    return pairs


def _message_for_turn(
    db: Session,
    turn: AgentTurn,
    role: str,
) -> ConversationMessage | None:
    message_id = turn.user_message_id if role == "user" else turn.assistant_message_id
    if message_id is not None:
        message = db.query(ConversationMessage).filter_by(id=message_id).first()
        if message is not None:
            return message
    return (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.conversation_id == turn.conversation_id,
            ConversationMessage.turn_id == turn.id,
            ConversationMessage.role == role,
        )
        .order_by(ConversationMessage.id.asc())
        .first()
    )


def _has_readable_event_range(turn: AgentTurn) -> bool:
    if not turn.event_file or turn.event_seq_start is None or turn.event_seq_end is None:
        return False
    return bool(
        read_event_segment(turn.event_file, turn.event_seq_start, turn.event_seq_end)
    )


def _write_turn_events(
    db: Session,
    *,
    conversation: Conversation,
    turn: AgentTurn,
    user_msg: ConversationMessage,
    assistant_msg: ConversationMessage,
    writer: AgentEventWriter,
    result: SessionSyncResult,
) -> None:
    user_event = _write_message_event(
        writer,
        conversation=conversation,
        turn=turn,
        message=user_msg,
    )
    assistant_event = _write_message_event(
        writer,
        conversation=conversation,
        turn=turn,
        message=assistant_msg,
    )
    if _event_write_failed(user_event, assistant_event):
        _record_failure(result, conversation, turn, "EVENT_WRITE_FAILED")
        return

    event_file = assistant_event.event_file or user_event.event_file
    turn = _mark_synced_range(
        db,
        turn=turn,
        event_file=event_file,
        seq_start=user_event.seq,
        seq_end=assistant_event.seq,
    )
    _attach_event_meta(db, message=user_msg, turn=turn)
    _attach_event_meta(db, message=assistant_msg, turn=turn)
    result.synced_turns += 1


def _write_message_event(
    writer: AgentEventWriter,
    *,
    conversation: Conversation,
    turn: AgentTurn,
    message: ConversationMessage,
):
    return writer.write(
        event_type=f"message.{message.role}",
        farm_id=conversation.farm_id,
        user_id=conversation.user_id,
        session_id=conversation.session_id,
        turn_id=turn.id,
        request_id=turn.request_id,
        payload={
            "content": message.content,
            "message_id": message.id,
            "backfilled": True,
        },
    )


def _event_write_failed(user_event, assistant_event) -> bool:
    return (
        user_event.status != "success"
        or assistant_event.status != "success"
        or user_event.seq is None
        or assistant_event.seq is None
    )


def _record_failure(
    result: SessionSyncResult,
    conversation: Conversation,
    turn: AgentTurn,
    reason: str,
) -> None:
    result.failed_turns += 1
    result.failures.append(
        {
            "session_id": conversation.session_id,
            "turn_id": turn.id,
            "reason": reason,
        }
    )


def _mark_synced_range(
    db: Session,
    *,
    turn: AgentTurn,
    event_file: str | None,
    seq_start: int | None,
    seq_end: int | None,
) -> AgentTurn:
    return mark_event_range(
        db,
        turn.id,
        event_file=event_file,
        seq_start=seq_start,
        seq_end=seq_end,
        write_status="success",
    )


def _attach_event_meta(
    db: Session,
    *,
    message: ConversationMessage,
    turn: AgentTurn,
) -> None:
    message.meta_json = {
        **(message.meta_json or {}),
        "event_file": turn.event_file,
        "event_seq_range": [turn.event_seq_start, turn.event_seq_end],
        "event_backfilled": True,
    }
    db.commit()


def _backfill_request_id(conversation_id: int, message_id: int) -> str:
    raw = f"{conversation_id}:{message_id}".encode("utf-8")
    return f"bf{hashlib.sha1(raw).hexdigest()[:8]}"


__all__ = ["sync_session_events"]
