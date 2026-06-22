"""Agent 聊天 use case。"""

import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.orm import Session

from app.agent.advisor import invoke_advisor, stream_advisor
from app.agent.application.session_flywheel import SessionFlywheelRecorder
from app.agent.application.pending_responses import (
    build_pending_action_response,
    build_pending_plan_response,
)
from app.agent.application.session_summary import schedule_session_summary
from app.agent.executor.pending_actions import handle_pending_action
from app.agent.llm import LlmNotConfiguredError
from app.core.database import SessionLocal
from app.core.logger import request_id_var
from app.memory.service import get_memory_service
from app.models.agent_record import AgentRecord
from app.models.conversation import Conversation
from app.models.farm import Farm
from app.models.trace import TraceRecord
from app.models.user import User
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    PendingActionResponse,
    PendingPlanResponse,
)
from app.services.conversation_service import get_or_create_conversation
from app.services.conversation_service import ConversationAccessError

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

    decision = await handle_pending_action(
        farm_id=farm.id,
        message=chat_request.message,
        session_id=chat_request.session_id,
    )
    if decision.handled:
        reply = decision.reply
    else:
        context = (
            f"【关联周期 ID: {chat_request.cycle_id}】\n"
            if chat_request.cycle_id
            else ""
        )
        reply = await invoke_advisor(
            context + chat_request.message,
            farm_id=farm.id,
            db=db,
            conversation_id=conversation.id if conversation else None,
            session_id=chat_request.session_id or "",
            request_id=request_id,
            user_id=farm.user_id,
        )

    record = AgentRecord(
        cycle_id=chat_request.cycle_id,
        record_type="chat",
        content=reply,
        farm_id=farm.id,
        user_id=farm.user_id,
        conversation_id=conversation.id if conversation else None,
    )
    db.add(record)
    try:
        db.commit()
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


def resolve_stream_user_and_farm(
    db: Session,
    current_user: User,
    simulate_user_id: str | None,
) -> tuple[User, Farm]:
    """解析流式对话的实际用户和农场。"""
    user = current_user
    if simulate_user_id:
        from fastapi import HTTPException

        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限才能模拟用户")
        simulated = db.query(User).filter(User.id == simulate_user_id).first()
        if not simulated:
            raise HTTPException(status_code=404, detail="模拟用户不存在")
        user = simulated

    from fastapi import HTTPException

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
    full_reply = ""
    conversation = None
    recorder = SessionFlywheelRecorder()
    started_turn = None
    start = time.perf_counter()
    try:
        if chat_request.session_id:
            conversation = get_or_create_conversation(
                db,
                farm.id,
                chat_request.session_id,
                user_id=user.id,
            )
            started_turn = recorder.start_turn(
                db,
                farm_id=farm.id,
                user_id=user.id,
                session_id=chat_request.session_id,
                conversation_id=conversation.id,
                request_id=request_id,
                user_message=chat_request.message,
            )

        decision = await handle_pending_action(
            farm_id=farm.id,
            message=chat_request.message,
            session_id=chat_request.session_id,
        )

        if decision.handled:
            full_reply = decision.reply
            data = json.dumps({"content": decision.reply}, ensure_ascii=False)
            yield f"data: {data}\n\n"
        else:
            context = (
                f"【关联周期 ID: {chat_request.cycle_id}】\n"
                if chat_request.cycle_id
                else ""
            )
            async for chunk in stream_advisor(
                context + chat_request.message,
                farm_id=farm.id,
                db=db,
                conversation_id=conversation.id if conversation else None,
                session_id=chat_request.session_id or "",
                request_id=request_id,
                user_id=user.id,
                call_type="stream_chat",
            ):
                full_reply += chunk
                data = json.dumps({"content": chunk}, ensure_ascii=False)
                yield f"data: {data}\n\n"

        await _flush_trace_queue()
        skill_names = _get_skill_names(db, request_id)
        pending_action = build_pending_action_response(
            farm.id, session_id=chat_request.session_id
        )
        pending_plan = build_pending_plan_response(
            farm.id, session_id=chat_request.session_id
        )
        skill_names = _merge_skill_names(
            skill_names,
            _skill_names_from_pending_decision(decision),
            _skill_names_from_pending_plan(pending_plan),
        )
        if conversation and started_turn and full_reply:
            recorder.finish_turn(
                db,
                started_turn,
                assistant_reply=full_reply,
                skills=skill_names,
                pending_action=pending_action.model_dump(mode="json")
                if pending_action
                else None,
                pending_plan=pending_plan.model_dump(mode="json")
                if pending_plan
                else None,
                pending_plan_id=pending_plan.plan_id if pending_plan else None,
                selected_tools_count=None,
                tool_calls_count=len(skill_names) or None,
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
        conversation = _save_stream_reply(
            db,
            chat_request=chat_request,
            user=user,
            farm=farm,
            full_reply=full_reply,
            skill_names=skill_names,
            pending_action=pending_action,
        )
        await _observe_chat_completion(
            user_id=user.id,
            farm_id=farm.id,
            session_id=chat_request.session_id,
            user_input=chat_request.message,
            assistant_reply=full_reply,
            skills_called=skill_names,
            request_id=request_id,
        )

        if skill_names:
            yield f"data: {json.dumps({'skills': skill_names}, ensure_ascii=False)}\n\n"

        if pending_action:
            logger.info(
                "[%s] 发送 pending_action SSE 事件 | skill=%s",
                request_id,
                pending_action.skill_name,
            )
            yield f"data: {json.dumps({'pending_action': pending_action.model_dump()}, ensure_ascii=False)}\n\n"
        if pending_plan:
            yield f"data: {json.dumps({'pending_plan': pending_plan.model_dump()}, ensure_ascii=False)}\n\n"

        logger.info(
            "[%s] /chat/stream 完成 | 耗时 %.2fs | reply %d 字符 | skills=%s conversation=%s",
            request_id,
            time.perf_counter() - start,
            len(full_reply),
            skill_names,
            conversation.id if conversation else None,
        )
    except LlmNotConfiguredError as exc:
        logger.error("[%s] /chat/stream 失败: %s", request_id, exc)
        yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
    except ConversationAccessError as exc:
        logger.warning("[%s] /chat/stream 会话不可访问: %s", request_id, exc)
        yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


async def _observe_chat_completion(
    *,
    user_id: str,
    farm_id: int,
    session_id: str | None,
    user_input: str,
    assistant_reply: str,
    skills_called: list[str],
    request_id: str,
) -> None:
    """提交 Memory observation，失败不影响聊天主流程。"""
    if not user_id:
        return
    try:
        await get_memory_service().observe_chat_completion(
            user_id=user_id,
            farm_id=farm_id,
            session_id=session_id,
            user_input=user_input,
            assistant_reply=assistant_reply,
            skills_called=skills_called,
            metadata={"request_id": request_id},
        )
    except Exception:
        logger.exception("[%s] Memory observation 提交失败", request_id)


async def _flush_trace_queue() -> None:
    """刷新 trace 队列，确保 skill_call 已落盘。"""
    from app.infra.trace_collector import get_trace_dao

    dao = get_trace_dao()
    if dao and dao.queue_size > 0:
        await dao.flush_now()


def _get_skill_names(db: Session, request_id: str) -> list[str]:
    """查询当前请求调用的 skill 名称。"""
    skills = _query_skill_names(db, request_id)
    if skills:
        return skills
    fresh_db = SessionLocal()
    try:
        return _query_skill_names(fresh_db, request_id)
    finally:
        fresh_db.close()


def _query_skill_names(db: Session, request_id: str) -> list[str]:
    """从指定 DB session 查询 skill_call 名称。"""
    skills = (
        db.query(TraceRecord.node_name)
        .filter(TraceRecord.request_id == request_id)
        .filter(TraceRecord.node_type == "skill_call")
        .distinct()
        .all()
    )
    return [s[0] for s in skills if s[0]]


def _merge_skill_names(*groups: list[str]) -> list[str]:
    """按出现顺序合并技能名并去重。"""
    merged: list[str] = []
    for group in groups:
        for name in group:
            if name and name not in merged:
                merged.append(name)
    return merged


def _skill_names_from_pending_decision(decision) -> list[str]:
    """从 pending plan 确认执行结果中提取已执行工具。"""
    steps = decision.metadata.get("steps") if decision and decision.metadata else None
    if not isinstance(steps, list):
        return []
    return [
        str(step.get("tool_name"))
        for step in steps
        if isinstance(step, dict) and step.get("tool_name")
    ]


def _skill_names_from_pending_plan(
    pending_plan: PendingPlanResponse | None,
) -> list[str]:
    """从待确认计划结构中提取工具名。"""
    if pending_plan is None:
        return []
    return [
        str(step.get("skill_name"))
        for step in pending_plan.steps
        if isinstance(step, dict) and step.get("skill_name")
    ]


def _save_stream_reply(
    db: Session,
    chat_request: ChatRequest,
    user: User,
    farm: Farm,
    full_reply: str,
    skill_names: list[str],
    pending_action: PendingActionResponse | None = None,
) -> Conversation | None:
    """保存流式回复和 AgentRecord。"""
    conversation = None
    if chat_request.session_id:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.session_id == chat_request.session_id,
                Conversation.farm_id == farm.id,
            )
            .first()
        )

    record = AgentRecord(
        cycle_id=chat_request.cycle_id,
        record_type="chat",
        content=full_reply,
        farm_id=farm.id,
        user_id=user.id,
        conversation_id=conversation.id if conversation else None,
    )
    db.add(record)
    db.commit()
    return conversation
