"""Agent 流式聊天 use case（SSE 编排层）。

整条链路（自上而下）::

    HTTP POST /chat/stream
        │
        ▼
    agent_chat_stream                 # domains/conversation/routes.py
        │   限流 / 鉴权 / 解析 farm / 生成 request_id
        │   返回 StreamingResponse(media_type="text/event-stream")
        ▼
    stream_chat_events ──────────────── 本模块入口
        │   ① _start_stream_turn      建会话 + 记录用户消息
        │   ② _stream_chat_events_safely 异常兜底
        │       └─ _stream_chat_success_events
        │            ├─ _stream_reply_chunks           ← 正文三路分流
        │            │    ├─ pending_action            待确认写操作 → 直接回复
        │            │    ├─ query_capability_menu     能力菜单改写 → 直接回复
        │            │    └─ stream_advisor            进入 ReAct Agent
        │            ├─ _collect_stream_metadata       正文完后聚合技能名/pending
        │            └─ _schedule_and_log_background_tail 非关键收尾丢后台
        ▼
    stream_advisor                   # application/advice/advisor.py
        │   问候语 / 不支持能力 / pending 短路；否则构建 history
        ▼
    stream_agent_loop                # agent/runtime/loop.py
            LLM → 有 tool_calls? → 工具 → 再 LLM … 直到给出最终回复

核心数据结构:
    - StreamTurnContext: 一轮流式的会话上下文（trace、conversation、计时）
    - StreamReplyState:  累积本轮已吐出的正文与决策（供尾部元数据使用）
    - StreamMetadata:    正文结束后汇总的技能名、pending_action/plan
"""

import logging
import time
from collections.abc import AsyncGenerator

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


async def stream_chat_events(
    db: Session,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    request_id: str,
) -> AsyncGenerator[str, None]:
    """生成聊天 SSE 事件。

    链路位置: 由 ``agent_chat_stream`` 路由直接包装为 StreamingResponse，
    是 SSE 链路与业务层之间的唯一入口。

    产出顺序::
        ① start_turn 之后的全部正文/错误事件  (_stream_chat_events_safely)
        ② 末尾固定一个 ``done`` 事件          (本函数 yield)
    """
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
    """执行流式链路，并把已知业务异常渲染为 SSE error。

    链路位置: ``stream_chat_events`` 的安全外壳，负责把预期内的业务异常
    （LLM 未配置、会话越权访问）转换成 ``error`` SSE 事件，避免连接被
    FastAPI 默认异常处理直接关闭，前端读不到错误原因。
    """
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
    """执行正常流式链路，依次输出正文和尾部元数据。

    链路位置: 无异常路径下的实际执行体。把每一轮 SSE 输出分成三段::

        ① 正文事件 (_stream_reply_chunks)
            — pending_action / 查询菜单 / stream_advisor 三路分流
        ② 元数据事件 (_yield_metadata_events)
            — 正文已结束，前端拿到 skill_names / pending_action / pending_plan
        ③ 后台收尾 (_schedule_and_log_background_tail)
            — 持久化、trace 收尾等非关键任务，不阻塞 SSE
    """
    _init_stream_trace(chat_request, user, farm, request_id)
    # ① 正文阶段：按 pending → 查询菜单 → Advisor 顺序分流
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

    # ② 元数据阶段：正文已吐完，聚合技能名和待确认结构再发给前端
    metadata = await _collect_stream_metadata(
        db,
        request_id=request_id,
        farm=farm,
        chat_request=chat_request,
        reply_state=reply_state,
    )
    async for event in _yield_metadata_events(request_id, metadata):
        yield event

    # ③ 后台收尾：不阻塞 SSE，丢到后台 task 完成持久化和日志
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
    """调度非关键后台收尾，并记录本次 SSE 可见链路完成。

    分两件事::

        ① _schedule_stream_background_finalization
            把回复持久化、turn 完结事件放到后台 task 执行；
            SSE 连接可以立即返回，不让前端等落库。
        ② _log_stream_completed
            记录本轮 SSE 链路可见部分完成（区别于后台 task 完成的日志）。
    """
    _schedule_stream_background_finalization(
        _build_stream_persistence_payload(
            chat_request, user, farm, reply_state, metadata
        ),
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
        pending_plan=metadata.pending_plan,
        pending_decision_handled=bool(getattr(reply_state.decision, "handled", False)),
    )


async def _start_stream_turn(
    db: Session,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    request_id: str,
) -> StreamTurnContext:
    """创建会话上下文，并在有 session_id 时记录用户消息。

    链路位置: ``stream_chat_events`` 的前置步骤，正文还没开始流。
    做两件事::

        ① 创建 StreamTurnContext (recorder + 计时起点)
        ② 若有 session_id，复用/新建 conversation，并把用户这条消息
           通过 flywheel 记下来（用于飞轮分析和历史构建）

    无 session_id（如匿名/一次性调用）则只返回空 context，跳过 ②。
    """
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
    """按 pending、查询菜单、Advisor 三段分流生成正文 SSE。

    分流优先级（命中即短路返回，不再进入下一段）::

        1. pending_action   上一轮流出的"待确认写操作"在本轮被回应
                            → 直接给结论，不进 Agent
        2. 查询菜单         命中"你能做什么"类问题
                            → 直接给菜单文案，不进 Agent
        3. Advisor          走完整 ReAct 循环
    """
    # 优先级 ①：检查是否有上一轮流出的待确认操作/计划
    decision = await _handle_stream_pending(farm, chat_request)
    reply_state.decision = decision

    if decision.handled:
        # pending 命中：直接把结论当正文吐出，跳过 Advisor
        yield _record_and_format_direct_reply(
            reply_state,
            reply=decision.reply,
            user_input=chat_request.message,
            node_name="pending_action_reply",
            reason="pending_action_handled",
        )
        return

    # 优先级 ② & ③：先尝试查询菜单改写，未命中则进入 Advisor
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
    """处理查询菜单改写后，继续进入 Advisor 流式回复。

    两段职责::

        ① resolve_query_menu_or_message
            — 命中"你能做什么"类查询 → 返回 menu_reply，直接吐出菜单
            — 未命中 → 把用户消息可能改写为 effective_message（菜单扩展）
        ② stream_advisor
            — 把消息丢给 ReAct Agent，逐 token 拿回最终回复
    """
    # ① 查询菜单分流：命中则直接回复菜单，跳过 Advisor
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

    # ② 真正进入 ReAct Agent；used_advisor 标记后续元数据收集要走 trace 路径
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
        # 边收边吐：累积全文供持久化使用，同时把 chunk 包成 SSE content 事件
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
    """刷新 trace 后汇总技能名和待确认结构。

    链路位置: 正文阶段（``_stream_reply_chunks``）跑完之后调用，
    为接下来的元数据事件准备 payload。三件事::

        ① flush trace        把 trace 队列里的事件落盘
        ② 收集 pending       当前是否仍有待确认 action/plan（轮次结束时
                              被新流出的待确认结构也要告诉前端）
        ③ 收集 skill_names   本轮命中的技能名（来自 trace、pending 决策、
                              pending plan 三个来源的并集）

    注意: 没进 Advisor 的轮次（pending / 菜单短路）不需要保留 trace，
    显式 clear_trace 避免污染后续请求。
    """
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
    "stream_chat_events",
]
