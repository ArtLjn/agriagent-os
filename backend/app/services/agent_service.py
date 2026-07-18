"""Agent 服务层，封装 Agent 调用与记录持久化。"""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.application.advice.advisor import invoke_advisor, stream_advisor
from app.agent.executor.pending_actions import handle_pending_action
from app.core.llm import get_llm
from app.prompt.composer import get_composer
from app.infra.pending_actions import (
    get_pending,
)
from app.infra.repository_runtime import (
    get_agent_record_repository,
    run_maybe_awaitable,
)
from app.models.agent_record import AgentRecord
from app.models.farm import Farm
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    DailyAdviceResponse,
    ReportResponse,
)
from app.services.conversation_service import (
    get_or_create_conversation,
    save_message,
)
from app.services.daily_advice_generation import generate_daily_advice
from app.services import agent_report_service

logger = logging.getLogger(__name__)


application_chat = None


def _resolve_user_id(
    db: Session | None, farm_id: int, user_id: str | None
) -> str | None:
    """优先使用调用方用户；缺省时从当前农场回填。"""
    if user_id or db is None:
        return user_id
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    return farm.user_id if farm else None


def _load_farm_for_application(db: Session, farm_id: int) -> Farm:
    """加载 Application 聊天用例需要的农场实体。"""
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    if farm is None:
        raise ValueError(f"未找到农场: {farm_id}")
    return farm


async def chat_with_agent(
    db: Session,
    message: str,
    farm_id: int,
    cycle_id: int | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    request_id: str = "",
) -> ChatResponse:
    """兼容旧 service 入口，委托 Application 聊天用例。"""
    global application_chat
    if application_chat is None:
        from app.application.chat.use_case import chat as application_chat

    farm = _load_farm_for_application(db, farm_id)
    application_farm = SimpleNamespace(id=farm.id, user_id=user_id) if user_id else farm
    return await application_chat(
        db,
        ChatRequest(
            message=message,
            cycle_id=cycle_id,
            session_id=session_id,
        ),
        application_farm,
        request_id=request_id,
    )


async def stream_chat_with_agent(
    message: str,
    farm_id: int,
    cycle_id: int | None = None,
    db: Session | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    request_id: str = "",
) -> AsyncGenerator[str, None]:
    """流式与 Agent 对话，逐 token 返回。支持写操作确认流程。"""
    user_id = _resolve_user_id(db, farm_id, user_id)
    # 如果有 session_id 和 db，获取或创建会话并保存用户消息
    conversation = None
    if db and session_id:
        conversation = get_or_create_conversation(
            db, farm_id, session_id, user_id=user_id
        )
        save_message(db, conversation.id, "user", message)

    # 检查是否有 pending action（写操作确认流程）
    pending = get_pending(farm_id, session_id=session_id)
    if pending is not None:
        decision = await handle_pending_action(
            farm_id=farm_id,
            message=message,
            session_id=session_id,
        )
        if decision.handled:
            yield decision.reply
            return

    # 统一走 ReAct Function Calling 流式路由
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    full_reply = ""
    async for chunk in stream_advisor(
        full_input,
        farm_id=farm_id,
        db=db,
        conversation_id=conversation.id if conversation else None,
        session_id=session_id or "",
        request_id=request_id,
        user_id=user_id,
        call_type="stream_chat",
    ):
        full_reply += chunk
        yield chunk

    # assistant 消息由调用方（agent.py stream 端点）保存，避免重复


async def get_daily_advice(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    user_id: str | None = None,
) -> DailyAdviceResponse:
    """生成每日农事建议并保存。命中今日缓存则直接返回。"""
    user_id = _resolve_user_id(db, farm_id, user_id)
    return await generate_daily_advice(
        db,
        farm_id=farm_id,
        cycle_id=cycle_id,
        user_id=user_id,
        invoke_advisor=invoke_daily_advice_llm,
        get_composer=get_composer,
    )


async def invoke_daily_advice_llm(
    prompt: str,
    *,
    farm_id: int,
    db: Session | None = None,
    user_id: str | None = None,
    call_type: str = "daily_advice",
) -> str:
    """每日建议专用 LLM 入口：保持既有签名，实际绕过聊天 loop。"""
    return await invoke_advisor(
        prompt,
        farm_id=farm_id,
        db=db,
        user_id=user_id,
        call_type=call_type,
    )


async def refresh_daily_advice(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    user_id: str | None = None,
) -> DailyAdviceResponse:
    """强制刷新每日农事建议：删除今日旧记录后重新生成。"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    repo = get_agent_record_repository(db)
    run_maybe_awaitable(
        repo.delete_daily_cache(farm_id=farm_id, cycle_id=cycle_id, since=today_start)
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info("已清除今日旧建议 | farm=%s cycle=%s", farm_id, cycle_id)
    return await get_daily_advice(db, farm_id, cycle_id, user_id=user_id)


async def generate_report(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    report_type: str = "weekly",
) -> ReportResponse:
    """兼容旧 patch 点的报告生成入口。"""
    original_get_llm = agent_report_service.get_llm
    try:
        agent_report_service.get_llm = get_llm
        return await agent_report_service.generate_report(
            db,
            farm_id=farm_id,
            cycle_id=cycle_id,
            report_type=report_type,
        )
    finally:
        agent_report_service.get_llm = original_get_llm


def get_advice_history(
    db: Session, farm_id: int, cycle_id: int | None = None, limit: int = 20
) -> list[AgentRecord]:
    """查询建议历史。"""
    return run_maybe_awaitable(
        get_agent_record_repository(db).list_advice_history(
            farm_id=farm_id,
            cycle_id=cycle_id,
            limit=limit,
        )
    )


def get_report_history(
    db: Session, farm_id: int, cycle_id: int | None = None, limit: int = 20
) -> list[AgentRecord]:
    """查询报告历史。"""
    return run_maybe_awaitable(
        get_agent_record_repository(db).list_report_history(
            farm_id=farm_id,
            cycle_id=cycle_id,
            limit=limit,
        )
    )


__all__ = [
    "chat_with_agent",
    "stream_chat_with_agent",
    "get_daily_advice",
    "refresh_daily_advice",
    "generate_report",
    "get_advice_history",
    "get_report_history",
]
