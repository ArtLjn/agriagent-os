"""流式聊天关键收尾与后台收尾任务。"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.application.chat.helpers import (
    observe_chat_completion as _observe_chat_completion,
    stream_finish_turn as _stream_finish_turn,
)
from app.application.session.summary import schedule_session_summary
from app.application.chat.stream_persistence import (
    StreamReplyPersistencePayload,
    save_stream_reply_payload as _save_stream_reply_payload,
)
from app.application.chat.stream_types import (
    StreamMetadata,
    StreamReplyState,
    StreamTurnContext,
)
from app.application.chat.task_state_updater import (
    TaskStateTurn,
    update_task_state_after_turn,
)
from app.shared.database import SessionLocal
from app.memory.service import get_memory_service
from app.domains.farm.models import Farm
from app.domains.conversation.agent_schemas import ChatRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamTurnFinalizationPayload:
    """后台补全 turn 和会话消息所需的轻量字段。"""

    recorder: Any
    started_turn: Any
    conversation_id: int
    farm_id: int
    session_id: str | None
    full_reply: str
    skill_names: list[str]
    pending_action: dict[str, Any] | None
    pending_plan: dict[str, Any] | None
    pending_plan_id: str | None
    latency_ms: int


def build_stream_turn_finalization_payload(
    *,
    chat_request: ChatRequest,
    farm: Farm,
    turn_context: StreamTurnContext,
    reply_state: StreamReplyState,
    metadata: StreamMetadata,
) -> StreamTurnFinalizationPayload | None:
    """从请求上下文中提取后台 finish_turn 所需字段。"""
    if not (
        turn_context.conversation
        and turn_context.started_turn
        and reply_state.full_reply
    ):
        return None
    return StreamTurnFinalizationPayload(
        recorder=turn_context.recorder,
        started_turn=turn_context.started_turn,
        conversation_id=turn_context.conversation.id,
        farm_id=farm.id,
        session_id=chat_request.session_id,
        full_reply=reply_state.full_reply,
        skill_names=metadata.skill_names,
        pending_action=metadata.pending_action.model_dump(mode="json")
        if metadata.pending_action
        else None,
        pending_plan=metadata.pending_plan.model_dump(mode="json")
        if metadata.pending_plan
        else None,
        pending_plan_id=metadata.pending_plan.plan_id
        if metadata.pending_plan
        else None,
        latency_ms=int((time.perf_counter() - turn_context.started_at) * 1000),
    )


async def finish_stream_turn_if_needed(
    db: Session,
    *,
    chat_request: ChatRequest,
    farm: Farm,
    request_id: str,
    turn_context: StreamTurnContext,
    reply_state: StreamReplyState,
    metadata: StreamMetadata,
) -> None:
    """有会话和回复时写 assistant message、turn 聚合和摘要任务。"""
    if not (
        turn_context.conversation
        and turn_context.started_turn
        and reply_state.full_reply
    ):
        return

    started_at = time.perf_counter()
    await _stream_finish_turn(
        turn_context.recorder,
        db,
        turn_context.started_turn,
        assistant_reply=reply_state.full_reply,
        skills=metadata.skill_names,
        pending_action=metadata.pending_action.model_dump(mode="json")
        if metadata.pending_action
        else None,
        pending_plan=metadata.pending_plan.model_dump(mode="json")
        if metadata.pending_plan
        else None,
        pending_plan_id=metadata.pending_plan.plan_id
        if metadata.pending_plan
        else None,
        selected_tools_count=None,
        tool_calls_count=len(metadata.skill_names) or None,
        token_total=None,
        latency_ms=int((time.perf_counter() - turn_context.started_at) * 1000),
        status="success",
    )
    log_stream_stage(
        request_id,
        "finish_turn",
        started_at,
        extra="turn_id=%s" % turn_context.started_turn.turn_id,
    )
    schedule_session_summary(
        conversation_id=turn_context.conversation.id,
        farm_id=farm.id,
        session_id=chat_request.session_id,
        memory_service_provider=get_memory_service,
    )


def schedule_stream_background_finalization(
    payload: StreamReplyPersistencePayload,
    *,
    request_id: str,
    turn_payload: StreamTurnFinalizationPayload | None = None,
    create_task=asyncio.create_task,
) -> object | None:
    """调度不影响 SSE done 的后台持久化和 Memory observation。"""
    coro = run_stream_background_finalization(
        payload,
        request_id=request_id,
        turn_payload=turn_payload,
    )
    try:
        return create_task(coro)
    except RuntimeError:
        coro.close()
        logger.exception("[%s] stream 后台收尾任务调度失败", request_id)
        return None


async def run_stream_background_finalization(
    payload: StreamReplyPersistencePayload,
    *,
    request_id: str,
    turn_payload: StreamTurnFinalizationPayload | None = None,
    session_factory=SessionLocal,
) -> None:
    """使用独立 DB session 执行非关键收尾，避免拖慢 SSE done。"""
    total_started_at = time.perf_counter()
    db = session_factory()
    try:
        if turn_payload is not None:
            turn_started_at = time.perf_counter()
            await finish_stream_turn_payload(
                db,
                turn_payload,
                request_id=request_id,
            )
            log_stream_stage(request_id, "background_finish_turn", turn_started_at)
        save_started_at = time.perf_counter()
        await _save_stream_reply_payload(db, payload)
        log_stream_stage(request_id, "background_save_reply", save_started_at)
        await update_stream_task_state_payload(db, payload, request_id=request_id)
    except Exception:
        db.rollback()
        logger.exception("[%s] stream 后台保存回复失败", request_id)
    finally:
        db.close()

    observe_started_at = time.perf_counter()
    await _observe_chat_completion(
        user_id=payload.user_id,
        farm_id=payload.farm_id,
        session_id=payload.session_id,
        user_input=payload.user_input,
        assistant_reply=payload.full_reply,
        skills_called=payload.skill_names,
        request_id=request_id,
    )
    log_stream_stage(request_id, "background_observe_memory", observe_started_at)
    log_stream_stage(request_id, "background_total", total_started_at)


async def update_stream_task_state_payload(
    db: Session,
    payload: StreamReplyPersistencePayload,
    *,
    request_id: str,
) -> None:
    """在流式后台收尾阶段保守更新 TaskState。"""
    task_state_started_at = time.perf_counter()
    await update_task_state_after_turn(
        db,
        TaskStateTurn(
            farm_id=payload.farm_id,
            user_id=payload.user_id,
            session_id=payload.session_id,
            user_input=payload.user_input,
            assistant_reply=payload.full_reply,
            pending_action=payload.pending_action,
            pending_plan=payload.pending_plan,
            pending_decision_handled=payload.pending_decision_handled,
        ),
    )
    log_stream_stage(request_id, "background_task_state", task_state_started_at)


async def finish_stream_turn_payload(
    db: Session,
    payload: StreamTurnFinalizationPayload,
    *,
    request_id: str,
) -> None:
    """后台补全 assistant message、turn 聚合和摘要任务。"""
    await _stream_finish_turn(
        payload.recorder,
        db,
        payload.started_turn,
        assistant_reply=payload.full_reply,
        skills=payload.skill_names,
        pending_action=payload.pending_action,
        pending_plan=payload.pending_plan,
        pending_plan_id=payload.pending_plan_id,
        selected_tools_count=None,
        tool_calls_count=len(payload.skill_names) or None,
        token_total=None,
        latency_ms=payload.latency_ms,
        status="success",
    )
    schedule_session_summary(
        conversation_id=payload.conversation_id,
        farm_id=payload.farm_id,
        session_id=payload.session_id,
        memory_service_provider=get_memory_service,
    )


def log_stream_stage(
    request_id: str,
    stage: str,
    started_at: float,
    *,
    extra: str = "",
) -> None:
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    suffix = f" | {extra}" if extra else ""
    logger.info(
        "[%s] /chat/stream 阶段耗时 | stage=%s duration_ms=%d%s",
        request_id,
        stage,
        duration_ms,
        suffix,
    )
