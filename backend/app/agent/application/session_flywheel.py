"""会话热路径与事件日志协调工具。"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.infra.agent_events import AgentEventWriter
from app.services.agent_turn_service import create_turn, finish_turn, mark_event_range
from app.services.conversation_service import save_message


@dataclass(frozen=True)
class StartedTurn:
    turn_id: int
    user_message_id: int | None
    event_file: str | None
    event_seq_start: int | None
    last_event_seq: int | None


@dataclass(frozen=True)
class FinishedTurn:
    turn_id: int
    user_message_id: int | None
    assistant_message_id: int | None
    event_file: str | None
    event_seq_start: int | None
    event_seq_end: int | None


def build_message_meta(
    *,
    skills: list[str] | None = None,
    pending_action: dict[str, Any] | None = None,
    trace_request_id: str | None = None,
    event_file: str | None = None,
    event_seq_range: tuple[int | None, int | None] | None = None,
) -> dict[str, Any]:
    """构造消息轻量 meta。"""
    meta: dict[str, Any] = {}
    if skills:
        meta["skills"] = skills
    if pending_action:
        meta["pending_action"] = pending_action
    if trace_request_id:
        meta["trace_request_id"] = trace_request_id
    if event_file:
        meta["event_file"] = event_file
    if event_seq_range is not None:
        meta["event_seq_range"] = [event_seq_range[0], event_seq_range[1]]
    return meta


class SessionFlywheelRecorder:
    """记录消息、turn 聚合和 JSONL 事件。"""

    def __init__(self, event_base_dir: str | Path = "data/agent-events") -> None:
        self._writer = AgentEventWriter(event_base_dir)

    def start_turn(
        self,
        db: Session,
        *,
        farm_id: int,
        user_id: str | None,
        session_id: str,
        conversation_id: int | None,
        request_id: str,
        user_message: str,
    ) -> StartedTurn:
        user_row = None
        if conversation_id is not None:
            user_row = save_message(
                db,
                conversation_id,
                "user",
                user_message,
                meta=None,
            )
        turn = create_turn(
            db,
            farm_id=farm_id,
            session_id=session_id,
            conversation_id=conversation_id,
            request_id=request_id,
            user_message_id=user_row.id if user_row else None,
            input_text=user_message,
        )
        if user_row is not None:
            user_row.turn_id = turn.id
            db.commit()
        event = self._writer.write(
            event_type="message.user",
            farm_id=farm_id,
            user_id=user_id,
            session_id=session_id,
            turn_id=turn.id,
            request_id=request_id,
            payload={
                "content": user_message,
                "message_id": user_row.id if user_row else None,
            },
        )
        return StartedTurn(
            turn_id=turn.id,
            user_message_id=user_row.id if user_row else None,
            event_file=event.event_file,
            event_seq_start=event.seq,
            last_event_seq=event.seq,
        )

    def finish_turn(
        self,
        db: Session,
        started: StartedTurn,
        *,
        assistant_reply: str,
        skills: list[str] | None,
        pending_action: dict[str, Any] | None,
        selected_tools_count: int | None,
        tool_calls_count: int | None,
        token_total: int | None,
        latency_ms: int | None,
        status: str,
    ) -> FinishedTurn:
        turn = finish_turn(
            db,
            started.turn_id,
            reply_text=assistant_reply,
            assistant_message_id=None,
            selected_tools_count=selected_tools_count,
            tool_calls_count=tool_calls_count,
            token_total=token_total,
            latency_ms=latency_ms,
            status=status,
        )
        assistant_row = None
        if turn.conversation_id is not None:
            meta = build_message_meta(
                skills=skills,
                pending_action=pending_action,
                trace_request_id=turn.request_id,
                event_file=started.event_file,
                event_seq_range=(started.event_seq_start, started.last_event_seq),
            )
            assistant_row = save_message(
                db,
                turn.conversation_id,
                "assistant",
                assistant_reply,
                meta=None,
            )
            assistant_row.meta_json = meta
            db.commit()
            db.refresh(assistant_row)
        event = self._writer.write(
            event_type="message.assistant",
            farm_id=turn.farm_id,
            user_id=None,
            session_id=turn.session_id,
            turn_id=turn.id,
            request_id=turn.request_id,
            payload={
                "content": assistant_reply,
                "message_id": assistant_row.id if assistant_row else None,
                "skills": skills or [],
                "pending_action": pending_action,
            },
        )
        seq_start = started.event_seq_start or event.seq
        seq_end = event.seq or started.last_event_seq
        mark_event_range(
            db,
            turn.id,
            event_file=event.event_file or started.event_file,
            seq_start=seq_start,
            seq_end=seq_end,
            write_status=event.status,
        )
        if assistant_row is not None:
            assistant_row.turn_id = turn.id
            if assistant_row.meta_json is None:
                assistant_row.meta_json = {}
            assistant_row.meta_json["event_file"] = (
                event.event_file or started.event_file
            )
            assistant_row.meta_json["event_seq_range"] = [seq_start, seq_end]
            db.commit()
        finish_turn(
            db,
            turn.id,
            reply_text=assistant_reply,
            assistant_message_id=assistant_row.id if assistant_row else None,
            selected_tools_count=selected_tools_count,
            tool_calls_count=tool_calls_count,
            token_total=token_total,
            latency_ms=latency_ms,
            status=status,
        )
        return FinishedTurn(
            turn_id=turn.id,
            user_message_id=started.user_message_id,
            assistant_message_id=assistant_row.id if assistant_row else None,
            event_file=event.event_file or started.event_file,
            event_seq_start=seq_start,
            event_seq_end=seq_end,
        )
