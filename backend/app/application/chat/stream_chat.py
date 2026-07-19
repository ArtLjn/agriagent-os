"""Agent 流式聊天 use case。"""

import logging
import time
from collections.abc import AsyncGenerator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.application.advice.advisor import stream_advisor
from app.application.chat.helpers import (
    flush_trace_queue as _flush_trace_queue,
    merge_skill_names as _merge_skill_names,
    record_agent_response,
    skill_names_from_pending_decision as _skill_names_from_pending_decision,
    skill_names_from_pending_plan as _skill_names_from_pending_plan,
    stream_start_turn as _stream_start_turn,
)
from app.application.pending_responses import (
    build_pending_action_response,
    build_pending_plan_response,
)
from app.application.chat.stream_persistence import (
    StreamReplyPersistencePayload,
    get_skill_names as _get_skill_names,
    save_stream_reply as _save_stream_reply,
)
from app.application.chat.stream_finalization import (
    build_stream_turn_finalization_payload as _build_stream_turn_finalization_payload,
    log_stream_stage as _log_stream_stage,
    schedule_stream_background_finalization as _schedule_stream_background_finalization,
)
from app.application.query_capability_menu import resolve_query_menu_or_message
from app.application.session.flywheel import SessionFlywheelRecorder
from app.application.chat.stream_tail import (
    log_stream_completed as _log_stream_completed,
    yield_metadata_events as _yield_metadata_events,
)
from app.application.chat.stream_types import (
    ResponseEvent,
    StreamMetadata,
    StreamReplyState,
    StreamTurnContext,
    format_sse_event,
    format_text_response,
)
from app.agent.executor.models import PendingActionDecision
from app.agent.executor.pending_actions import handle_pending_action
from app.shared.llm import LlmNotConfiguredError
from app.infra.trace_context import clear_trace, init_trace
from app.memory.service import get_memory_service
from app.domains.conversation.models import Conversation
from app.domains.farm.models import Farm
from app.domains.users.models import User
from app.domains.conversation.agent_schemas import ChatRequest
from app.domains.conversation.service import (
    ConversationAccessError,
    get_or_create_conversation,
)

logger = logging.getLogger(__name__)


def resolve_stream_user_and_farm(
    db: Session,
    current_user: User,
    simulate_user_id: str | None,
) -> tuple[User, Farm]:
    """解析流式对话的实际用户和农场。"""
    user = current_user
    if simulate_user_id:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限才能模拟用户")
        simulated = db.query(User).filter(User.id == simulate_user_id).first()
        if not simulated:
            raise HTTPException(status_code=404, detail="模拟用户不存在")
        user = simulated

    farm = db.query(Farm).filter(Farm.user_id == user.id).first()
    if farm is None:
        raise HTTPException(status_code=404, detail="未找到关联农场")
    return user, farm


async def stream_chat_events(
    db: Session,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    request_id: str,
) -> AsyncGenerator[str, None]:
    """生成聊天 SSE 事件。"""
    turn_context = await _start_stream_turn(db, chat_request, user, farm, request_id)
    reply_state = StreamReplyState()
    async for event in _stream_chat_events_safely(
        db,
        chat_request=chat_request,
        user=user,
        farm=farm,
        request_id=request_id,
        turn_context=turn_context,
        reply_state=reply_state,
    ):
        yield event
    yield format_sse_event(ResponseEvent("done"))


async def _stream_chat_events_safely(
    db: Session,
    *,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    request_id: str,
    turn_context: StreamTurnContext,
    reply_state: StreamReplyState,
) -> AsyncGenerator[str, None]:
    """执行流式链路，并把已知业务异常渲染为 SSE error。"""
    try:
        async for event in _stream_chat_success_events(
            db,
            chat_request=chat_request,
            user=user,
            farm=farm,
            request_id=request_id,
            turn_context=turn_context,
            reply_state=reply_state,
        ):
            yield event
    except LlmNotConfiguredError as exc:
        clear_trace()
        logger.error("[%s] /chat/stream 失败: %s", request_id, exc)
        yield format_sse_event(ResponseEvent("error", {"error": str(exc)}))
    except ConversationAccessError as exc:
        clear_trace()
        logger.warning("[%s] /chat/stream 会话不可访问: %s", request_id, exc)
        yield format_sse_event(ResponseEvent("error", {"error": str(exc)}))


async def _stream_chat_success_events(
    db: Session,
    *,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    request_id: str,
    turn_context: StreamTurnContext,
    reply_state: StreamReplyState,
) -> AsyncGenerator[str, None]:
    """执行正常流式链路，依次输出正文和尾部元数据。"""
    _init_stream_trace(chat_request, user, farm, request_id)
    async for event in _stream_reply_chunks(
        db,
        chat_request=chat_request,
        user=user,
        farm=farm,
        request_id=request_id,
        turn_context=turn_context,
        reply_state=reply_state,
    ):
        yield event

    metadata = await _collect_stream_metadata(
        db,
        request_id=request_id,
        farm=farm,
        chat_request=chat_request,
        reply_state=reply_state,
    )
    async for event in _yield_metadata_events(request_id, metadata):
        yield event

    _schedule_and_log_background_tail(
        chat_request=chat_request,
        user=user,
        farm=farm,
        request_id=request_id,
        turn_context=turn_context,
        reply_state=reply_state,
        metadata=metadata,
    )


def _schedule_and_log_background_tail(
    *,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    request_id: str,
    turn_context: StreamTurnContext,
    reply_state: StreamReplyState,
    metadata: StreamMetadata,
) -> None:
    """调度非关键后台收尾，并记录本次 SSE 可见链路完成。"""
    _schedule_stream_background_finalization(
        _build_stream_persistence_payload(chat_request, user, farm, reply_state, metadata),
        request_id=request_id,
        turn_payload=_build_stream_turn_finalization_payload(
            chat_request=chat_request,
            farm=farm,
            turn_context=turn_context,
            reply_state=reply_state,
            metadata=metadata,
        ),
    )
    _log_stream_completed(
        request_id=request_id,
        started_at=turn_context.started_at,
        reply_state=reply_state,
        metadata=metadata,
        conversation=turn_context.conversation,
    )


def _build_stream_persistence_payload(
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    reply_state: StreamReplyState,
    metadata: StreamMetadata,
) -> StreamReplyPersistencePayload:
    return StreamReplyPersistencePayload(
        cycle_id=chat_request.cycle_id,
        session_id=chat_request.session_id,
        user_id=user.id,
        farm_id=farm.id,
        user_input=chat_request.message,
        full_reply=reply_state.full_reply,
        skill_names=metadata.skill_names,
        pending_action=metadata.pending_action,
    )


async def _start_stream_turn(
    db: Session,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    request_id: str,
) -> StreamTurnContext:
    """创建会话上下文，并在有 session_id 时记录用户消息。"""
    context = StreamTurnContext(
        recorder=SessionFlywheelRecorder(),
        started_at=time.perf_counter(),
    )
    if not chat_request.session_id:
        return context

    conversation = get_or_create_conversation(
        db,
        farm.id,
        chat_request.session_id,
        user_id=user.id,
    )
    started_turn = await _stream_start_turn(
        context.recorder,
        db,
        farm_id=farm.id,
        user_id=user.id,
        session_id=chat_request.session_id,
        conversation_id=conversation.id,
        request_id=request_id,
        user_message=chat_request.message,
    )
    context.conversation = conversation
    context.started_turn = started_turn
    return context


def _init_stream_trace(
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    request_id: str,
) -> None:
    """初始化本轮流式请求 trace 上下文。"""
    init_trace(
        farm_id=farm.id,
        session_id=chat_request.session_id or "",
        request_id=request_id,
        user_id=user.id,
        call_type="stream_chat",
    )


async def _stream_reply_chunks(
    db: Session,
    *,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    request_id: str,
    turn_context: StreamTurnContext,
    reply_state: StreamReplyState,
) -> AsyncGenerator[str, None]:
    """按 pending、查询菜单、Advisor 三段分流生成正文 SSE。"""
    decision = await _handle_stream_pending(farm, chat_request)
    reply_state.decision = decision

    if decision.handled:
        yield _record_and_format_direct_reply(
            reply_state,
            reply=decision.reply,
            user_input=chat_request.message,
            node_name="pending_action_reply",
            reason="pending_action_handled",
        )
        return

    async for event in _stream_query_or_advisor_reply(
        db,
        chat_request=chat_request,
        user=user,
        farm=farm,
        request_id=request_id,
        conversation=turn_context.conversation,
        reply_state=reply_state,
    ):
        yield event


async def _handle_stream_pending(
    farm: Farm,
    chat_request: ChatRequest,
) -> PendingActionDecision:
    """优先处理当前会话中的待确认操作或计划。"""
    return await handle_pending_action(
        farm_id=farm.id,
        message=chat_request.message,
        session_id=chat_request.session_id,
    )


def _record_and_format_direct_reply(
    reply_state: StreamReplyState,
    *,
    reply: str,
    user_input: str,
    node_name: str,
    reason: str,
) -> str:
    """记录无需进入 Advisor 的直接回复，并渲染为正文事件。"""
    reply_state.full_reply = reply
    reply_state.used_advisor = False
    record_agent_response(
        node_name=node_name,
        user_input=user_input,
        reply=reply,
        reason=reason,
    )
    return _content_event(reply)


async def _stream_query_or_advisor_reply(
    db: Session,
    *,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    request_id: str,
    conversation: Conversation | None,
    reply_state: StreamReplyState,
) -> AsyncGenerator[str, None]:
    """处理查询菜单改写后，继续进入 Advisor 流式回复。"""
    effective_message, menu_reply = await resolve_query_menu_or_message(
        memory_service=get_memory_service(),
        user_id=user.id,
        farm_id=farm.id,
        session_id=chat_request.session_id,
        message=chat_request.message,
    )
    if menu_reply:
        yield _record_and_format_direct_reply(
            reply_state,
            reply=menu_reply,
            user_input=chat_request.message,
            node_name="query_capability_menu_reply",
            reason="query_capability_menu",
        )
        return

    reply_state.used_advisor = True
    advisor_message = _with_cycle_context(chat_request, effective_message)
    async for chunk in stream_advisor(
        advisor_message,
        farm_id=farm.id,
        db=db,
        conversation_id=conversation.id if conversation else None,
        session_id=chat_request.session_id or "",
        request_id=request_id,
        user_id=user.id,
        call_type="stream_chat",
    ):
        reply_state.full_reply += chunk
        yield _content_event(chunk)


def _with_cycle_context(chat_request: ChatRequest, message: str) -> str:
    """把关联周期上下文拼到用户消息前。"""
    if not chat_request.cycle_id:
        return message
    return f"【关联周期 ID: {chat_request.cycle_id}】\n{message}"


def _content_event(content: str) -> str:
    return format_sse_event(ResponseEvent("content", {"content": content}))


async def _collect_stream_metadata(
    db: Session,
    *,
    request_id: str,
    farm: Farm,
    chat_request: ChatRequest,
    reply_state: StreamReplyState,
) -> StreamMetadata:
    """刷新 trace 后汇总技能名和待确认结构。"""
    started_at = time.perf_counter()
    await _flush_trace_queue()
    _log_stream_stage(request_id, "trace_flush", started_at)
    if not reply_state.used_advisor:
        clear_trace()

    pending_started_at = time.perf_counter()
    pending_action = build_pending_action_response(
        farm.id,
        session_id=chat_request.session_id,
    )
    pending_plan = build_pending_plan_response(
        farm.id,
        session_id=chat_request.session_id,
    )
    _log_stream_stage(request_id, "pending_metadata", pending_started_at)
    skill_started_at = time.perf_counter()
    skill_names = _merge_skill_names(
        await _get_skill_names(db, farm.id, request_id),
        _skill_names_from_pending_decision(reply_state.decision),
        _skill_names_from_pending_plan(pending_plan),
    )
    _log_stream_stage(
        request_id,
        "skill_metadata",
        skill_started_at,
        extra="skills=%s" % skill_names,
    )
    _log_stream_stage(request_id, "metadata_total", started_at)
    return StreamMetadata(
        skill_names=skill_names,
        pending_action=pending_action,
        pending_plan=pending_plan,
    )

__all__ = [
    "ResponseEvent",
    "_save_stream_reply",
    "format_sse_event",
    "format_text_response",
    "resolve_stream_user_and_farm",
    "stream_chat_events",
]
