"""Agent 服务层，封装 Agent 调用与记录持久化。"""

import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.agent.advisor import invoke_advisor, stream_advisor
from app.agent.executor.pending_actions import handle_pending_action
from app.agent.llm import get_llm
from app.agent.prompt_composer import get_composer
from app.infra.json_repair import safe_parse_json
from app.infra.pending_actions import (
    get_pending,
)
from app.models.agent_record import AgentRecord
from app.models.farm import Farm
from app.schemas.agent import (
    AdviceItem,
    ChatRequest,
    ChatResponse,
    DailyAdviceResponse,
    ReportResponse,
)
from app.services.conversation_service import (
    get_or_create_conversation,
    save_message,
)
from app.services import farm_context_service
from app.services import agent_report_service

logger = logging.getLogger(__name__)


# title 超过此长度截断并加省略号
_TITLE_MAX_DISPLAY = 10
_ADVICE_ITEM_MAX = 5
application_chat = None


def _truncate_title(title: str) -> str:
    """截断超长 title，超过 _TITLE_MAX_DISPLAY 字则加省略号。"""
    if len(title) > _TITLE_MAX_DISPLAY:
        return title[:_TITLE_MAX_DISPLAY] + "…"
    return title


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


def _parse_advice_items(raw: str) -> tuple[str, list[AdviceItem]]:
    """解析 LLM 返回的 JSON 为 (preview, AdviceItem 列表)，失败则 fallback。"""
    fallback_item = AdviceItem(
        title="今日农事建议",
        detail=raw[:50],
        priority=2,
        icon="📋",
    )
    try:
        parsed = safe_parse_json(raw)
        if isinstance(parsed, dict):
            if "items" in parsed:
                items_raw = parsed["items"]
                preview = str(parsed.get("preview", ""))[:20]
            else:
                items_raw = [parsed]
                preview = ""
        elif isinstance(parsed, list):
            items_raw = parsed
            preview = ""
        else:
            raise ValueError("非预期的 JSON 结构")

        items: list[AdviceItem] = []
        for entry in items_raw[:_ADVICE_ITEM_MAX]:
            title = _truncate_title(str(entry.get("title", "今日建议")))
            items.append(
                AdviceItem(
                    title=title,
                    detail=str(entry.get("detail", ""))[:50],
                    priority=int(entry.get("priority", 2)),
                    icon=str(entry.get("icon", "📋"))[:4],
                )
            )
        items.sort(key=lambda x: x.priority)
        return preview, items
    except (ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("建议 JSON 解析失败，fallback 为单条 | error=%s", exc)
        return "", [fallback_item]


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
        from app.agent.application.chat_use_case import chat as application_chat

    farm = _load_farm_for_application(db, farm_id)
    application_farm = (
        SimpleNamespace(id=farm.id, user_id=user_id) if user_id else farm
    )
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
    pending = get_pending(farm_id)
    if pending is not None:
        decision = await handle_pending_action(farm_id=farm_id, message=message)
        if decision.handled:
            yield decision.reply
            return

    # 统一走 LangGraph Function Calling 流式路由
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
    db: Session, farm_id: int, cycle_id: int | None = None
) -> DailyAdviceResponse:
    """生成每日农事建议并保存。命中今日缓存则直接返回。"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cached = (
        db.query(AgentRecord)
        .filter(
            AgentRecord.farm_id == farm_id,
            AgentRecord.record_type == "daily",
            AgentRecord.created_at >= today_start,
        )
        .order_by(AgentRecord.created_at.desc())
        .first()
    )
    if cached:
        preview, items = _parse_advice_items(cached.content)
        logger.info("缓存命中 | record_id=%s", cached.id)
        return DailyAdviceResponse(
            cycle_id=cached.cycle_id,
            preview=preview,
            items=items,
            created_at=cached.created_at,
        )

    # 注入农场上下文，通过 PromptComposer 渲染模板
    context = await farm_context_service.build_summary(db, farm_id)
    prompt = get_composer().compose(
        "daily_advice",
        variables={"farm_context": context, "cycle_id": cycle_id},
    )

    logger.info("生成每日建议 | farm=%s cycle=%s", farm_id, cycle_id)
    advice = await invoke_advisor(prompt, farm_id=farm_id)

    preview, items = _parse_advice_items(advice)

    record = AgentRecord(
        cycle_id=cycle_id, record_type="daily", content=advice, farm_id=farm_id
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        raise
    logger.info("建议已保存 | record_id=%s | items=%d", record.id, len(items))

    return DailyAdviceResponse(
        cycle_id=record.cycle_id,
        preview=preview,
        items=items,
        created_at=record.created_at,
    )


async def refresh_daily_advice(
    db: Session, farm_id: int, cycle_id: int | None = None
) -> DailyAdviceResponse:
    """强制刷新每日农事建议：删除今日旧记录后重新生成。"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    db.query(AgentRecord).filter(
        AgentRecord.farm_id == farm_id,
        AgentRecord.record_type == "daily",
        AgentRecord.cycle_id == cycle_id if cycle_id is not None else True,
        AgentRecord.created_at >= today_start,
    ).delete(synchronize_session=False)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info("已清除今日旧建议 | farm=%s cycle=%s", farm_id, cycle_id)
    return await get_daily_advice(db, farm_id, cycle_id)


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
    query = (
        db.query(AgentRecord)
        .filter(AgentRecord.farm_id == farm_id)
        .filter(AgentRecord.record_type.in_(["chat", "daily"]))
    )
    if cycle_id is not None:
        query = query.filter(AgentRecord.cycle_id == cycle_id)
    return query.order_by(AgentRecord.created_at.desc()).limit(limit).all()


def get_report_history(
    db: Session, farm_id: int, cycle_id: int | None = None, limit: int = 20
) -> list[AgentRecord]:
    """查询报告历史。"""
    query = (
        db.query(AgentRecord)
        .filter(AgentRecord.farm_id == farm_id)
        .filter(AgentRecord.record_type.in_(["report", "weekly", "monthly"]))
    )
    if cycle_id is not None:
        query = query.filter(AgentRecord.cycle_id == cycle_id)
    return query.order_by(AgentRecord.created_at.desc()).limit(limit).all()


__all__ = [
    "chat_with_agent",
    "stream_chat_with_agent",
    "get_daily_advice",
    "refresh_daily_advice",
    "generate_report",
    "get_advice_history",
    "get_report_history",
]
