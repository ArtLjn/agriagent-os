"""Agent 聊天 use case。"""

import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.agent.advisor import invoke_advisor
from app.agent.application.chat_use_case_helpers import (
    flush_trace_queue as _flush_trace_queue,
    observe_chat_completion as _observe_chat_completion,
)
from app.agent.application.session_flywheel import SessionFlywheelRecorder
from app.agent.application.pending_responses import (
    build_pending_action_response,
    build_pending_plan_response,
)
from app.agent.application.query_capability_menu import resolve_query_menu_or_message
from app.agent.application.response_trace import record_agent_response
from app.agent.application.session_summary import schedule_session_summary
from app.agent.application.stream_chat_use_case import (
    resolve_stream_user_and_farm,
    stream_chat_events,
)
from app.agent.executor.pending_actions import handle_pending_action
from app.core.logger import request_id_var
from app.infra.repository_runtime import (
    get_agent_record_repository,
    run_maybe_awaitable,
)
from app.infra.trace_context import clear_trace, init_trace
from app.memory.service import get_memory_service
from app.models.agent_record import AgentRecord
from app.models.farm import Farm
from app.schemas.agent import ChatRequest, ChatResponse
from app.services.conversation_service import get_or_create_conversation

logger = logging.getLogger(__name__)


def new_request_id() -> str:
    """生成并绑定请求 ID。"""
    rid = uuid.uuid4().hex[:8]
    request_id_var.set(rid)
    return rid


async def chat(
    db: Session,
    chat_request: ChatRequest,
    farm: Farm,
    request_id: str,
) -> ChatResponse:
    """执行非流式聊天。"""
    logger.info(
        "[%s] POST /agent/chat | message=%s cycle_id=%s",
        request_id,
        chat_request.message[:80],
        chat_request.cycle_id,
    )
    start = time.perf_counter()

    recorder = SessionFlywheelRecorder()
    started_turn = None
    conversation = None
    if chat_request.session_id:
        conversation = get_or_create_conversation(
            db,
            farm.id,
            chat_request.session_id,
            user_id=farm.user_id,
        )
        started_turn = recorder.start_turn(
            db,
            farm_id=farm.id,
            user_id=farm.user_id,
            session_id=chat_request.session_id,
            conversation_id=conversation.id,
            request_id=request_id,
            user_message=chat_request.message,
        )

    init_trace(
        farm_id=farm.id,
        session_id=chat_request.session_id or "",
        request_id=request_id,
        user_id=farm.user_id,
        call_type="chat",
    )
    decision = await handle_pending_action(
        farm_id=farm.id,
        message=chat_request.message,
        session_id=chat_request.session_id,
    )
    if decision.handled:
        reply = decision.reply
        record_agent_response(
            node_name="pending_action_reply",
            user_input=chat_request.message,
            reply=reply,
            reason="pending_action_handled",
        )
        await _flush_trace_queue()
        clear_trace()
    else:
        effective_message, menu_reply = await resolve_query_menu_or_message(
            memory_service=get_memory_service(),
            user_id=farm.user_id,
            farm_id=farm.id,
            session_id=chat_request.session_id,
            message=chat_request.message,
        )
        if menu_reply:
            reply = menu_reply
            record_agent_response(
                node_name="query_capability_menu_reply",
                user_input=chat_request.message,
                reply=reply,
                reason="query_capability_menu",
            )
            await _flush_trace_queue()
            clear_trace()
        else:
            context = (
                f"【关联周期 ID: {chat_request.cycle_id}】\n"
                if chat_request.cycle_id
                else ""
            )
            reply = await invoke_advisor(
                context + effective_message,
                farm_id=farm.id,
                db=db,
                conversation_id=conversation.id if conversation else None,
                session_id=chat_request.session_id or "",
                request_id=request_id,
                user_id=farm.user_id,
            )
            await _flush_trace_queue()

    record = AgentRecord(
        cycle_id=chat_request.cycle_id,
        record_type="chat",
        content=reply,
        farm_id=farm.id,
        user_id=farm.user_id,
        conversation_id=conversation.id if conversation else None,
    )
    try:
        record = run_maybe_awaitable(get_agent_record_repository(db).create(record))
    except Exception:
        db.rollback()
        raise
    logger.info("[%s] 对话记录已保存 | record_id=%s", request_id, record.id)

    result = ChatResponse(reply=reply)
    pending_action = build_pending_action_response(
        farm.id, session_id=chat_request.session_id
    )
    pending_plan = build_pending_plan_response(
        farm.id, session_id=chat_request.session_id
    )
    if pending_action:
        result.pending_action = pending_action
    if pending_plan:
        result.pending_plan = pending_plan
    if conversation and started_turn:
        recorder.finish_turn(
            db,
            started_turn,
            assistant_reply=reply,
            skills=[],
            pending_action=pending_action.model_dump(mode="json")
            if pending_action
            else None,
            pending_plan=pending_plan.model_dump(mode="json") if pending_plan else None,
            pending_plan_id=pending_plan.plan_id if pending_plan else None,
            selected_tools_count=None,
            tool_calls_count=None,
            token_total=None,
            latency_ms=int((time.perf_counter() - start) * 1000),
            status="success",
        )
        schedule_session_summary(
            conversation_id=conversation.id,
            farm_id=farm.id,
            session_id=chat_request.session_id,
            memory_service_provider=get_memory_service,
        )
    await _observe_chat_completion(
        user_id=farm.user_id or "",
        farm_id=farm.id,
        session_id=chat_request.session_id,
        user_input=chat_request.message,
        assistant_reply=result.reply,
        skills_called=[],
        request_id=request_id,
    )
    logger.info(
        "[%s] /agent/chat 完成 | 耗时 %.2fs | reply %d 字符 | pending=%s",
        request_id,
        time.perf_counter() - start,
        len(result.reply),
        bool(pending_action),
    )
    return result


__all__ = [
    "chat",
    "new_request_id",
    "resolve_stream_user_and_farm",
    "stream_chat_events",
]
