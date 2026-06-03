"""Agent 服务层，封装 Agent 调用与记录持久化。"""

import json
import logging
import re
import time
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.advisor import invoke_advisor, stream_advisor
from app.agent.llm import get_llm
from app.agent.prompt_composer import get_composer
from app.agent.skills import get_langchain_tools
from app.infra.json_repair import safe_parse_json
from app.infra.pending_actions import (
    PendingAction,
    build_confirm_message,
    detect_user_intent,
    get_pending,
    remove_pending,
    store_pending,
)
from app.infra.trace_collector import get_collector
from app.models.agent_record import AgentRecord
from app.schemas.agent import (
    AdviceItem,
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
_MISSING_TEMPLATE_RE = re.compile(r"系统还没有\s*(?P<crop>.+?)\s*模板")


def _truncate_title(title: str) -> str:
    """截断超长 title，超过 _TITLE_MAX_DISPLAY 字则加省略号。"""
    if len(title) > _TITLE_MAX_DISPLAY:
        return title[:_TITLE_MAX_DISPLAY] + "…"
    return title


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


async def _execute_pending_action(farm_id: int, skill_name: str, params: dict) -> str:
    """执行 pending action 中存储的写操作 Skill。"""
    start = time.time()
    error_msg = None
    result_str = ""
    try:
        tool_map = {t.name: t for t in get_langchain_tools(farm_id=farm_id)}
        tool = tool_map.get(skill_name)
        if not tool:
            return f"未知工具: {skill_name}"
        result = await tool.ainvoke(params)
        result_str = str(result)
        return result_str
    except Exception as exc:
        error_msg = str(exc)
        raise
    finally:
        get_collector().record(
            node_type="skill_call",
            node_name=skill_name,
            input_data=params,
            output_data=result_str or None,
            start_time=start,
            end_time=time.time(),
            error_message=error_msg,
        )


def _extract_missing_template_crop(pending: PendingAction, result: str) -> str:
    """从缺模板结果中提取作物名，优先使用 pending 参数。"""
    crop_name = str(pending.params.get("crop_name") or "").strip()
    if crop_name:
        return crop_name

    match = _MISSING_TEMPLATE_RE.search(result)
    return match.group("crop").strip() if match else ""


def _format_follow_up_intro(skill_name: str, params: dict) -> str:
    """生成后续确认动作的自然语言引导。"""
    if skill_name == "create_crop_cycle":
        crop_name = str(params.get("crop_name") or "").strip()
        return f"现在可以继续创建{crop_name}茬口。" if crop_name else "现在可以继续创建茬口。"

    return "下一步需要继续确认。"


async def _confirm_pending_action(farm_id: int, pending: PendingAction) -> str:
    """执行已确认的 pending action，并处理缺模板和链式动作。"""
    result = await _execute_pending_action(farm_id, pending.skill_name, pending.params)
    remove_pending(farm_id)

    if pending.skill_name == "create_crop_cycle" and "系统还没有" in result and "模板" in result:
        crop_name = _extract_missing_template_crop(pending, result)
        if crop_name:
            store_pending(
                farm_id,
                "create_crop_template",
                {"crop_name": crop_name},
                original_input=f"系统还没有{crop_name}作物模板",
                follow_up_skill_name="create_crop_cycle",
                follow_up_params=dict(pending.params),
                follow_up_original_input=pending.original_input,
            )
            confirm = build_confirm_message(
                "create_crop_template",
                {"crop_name": crop_name},
                original_input=f"系统还没有{crop_name}作物模板",
            )
            return (
                f"系统还没有{crop_name}作物模板。创建茬口前需要先创建模板。\n"
                f"{confirm}"
            )

    if pending.follow_up_skill_name and pending.follow_up_params is not None:
        store_pending(
            farm_id,
            pending.follow_up_skill_name,
            dict(pending.follow_up_params),
            original_input=pending.follow_up_original_input,
        )
        confirm = build_confirm_message(
            pending.follow_up_skill_name,
            pending.follow_up_params,
            original_input=pending.follow_up_original_input,
        )
        intro = _format_follow_up_intro(
            pending.follow_up_skill_name,
            pending.follow_up_params,
        )
        return f"已执行：{result}\n\n{intro}\n{confirm}"

    return f"已执行：{result}"


async def chat_with_agent(
    db: Session,
    message: str,
    farm_id: int,
    cycle_id: int | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    request_id: str = "",
) -> ChatResponse:
    """与用户进行 Agent 对话，支持写操作确认流程。"""
    logger.info(
        "开始对话 | farm=%s cycle=%s | input: %s", farm_id, cycle_id, message[:100]
    )

    # 如果有 session_id，获取或创建会话并保存用户消息
    conversation = None
    if session_id:
        conversation = get_or_create_conversation(
            db, farm_id, session_id, user_id=user_id
        )
        save_message(db, conversation.id, "user", message)

    # 检查是否有 pending action
    pending = get_pending(farm_id)
    if pending is not None:
        intent = detect_user_intent(message)

        if intent == "confirm":
            # 用户确认：执行 pending action
            logger.info(
                "用户确认执行 | farm=%s skill=%s params=%s",
                farm_id,
                pending.skill_name,
                pending.params,
            )
            try:
                reply = await _confirm_pending_action(farm_id, pending)
            except Exception as exc:
                logger.error("执行 pending action 失败: %s", exc)
                reply = f"执行失败：{exc}"
                remove_pending(farm_id)

            record = AgentRecord(
                cycle_id=cycle_id, record_type="chat", content=reply, farm_id=farm_id
            )
            db.add(record)
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
            if conversation:
                save_message(db, conversation.id, "assistant", reply)
            return ChatResponse(reply=reply)

        if intent == "cancel":
            # 用户取消：删除 pending action
            logger.info("用户取消操作 | farm=%s skill=%s", farm_id, pending.skill_name)
            remove_pending(farm_id)
            reply = "已取消操作。"
            record = AgentRecord(
                cycle_id=cycle_id, record_type="chat", content=reply, farm_id=farm_id
            )
            db.add(record)
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
            if conversation:
                save_message(db, conversation.id, "assistant", reply)
            return ChatResponse(reply=reply)

        # intent == "modify"：用户修正参数，交给 LLM 处理
        # 保留 pending action 不删除，让 LLM 根据上下文重新决策

    # 统一走 LangGraph Function Calling 路由
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    reply = await invoke_advisor(
        full_input,
        farm_id=farm_id,
        db=db,
        conversation_id=conversation.id if conversation else None,
        session_id=session_id or "",
        request_id=request_id,
    )

    record = AgentRecord(
        cycle_id=cycle_id, record_type="chat", content=reply, farm_id=farm_id
    )
    db.add(record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info("对话记录已保存 | record_id=%s", record.id)

    if conversation:
        save_message(db, conversation.id, "assistant", reply)

    return ChatResponse(reply=reply)


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
        intent = detect_user_intent(message)

        if intent == "confirm":
            logger.info(
                "用户确认执行 | farm=%s skill=%s params=%s",
                farm_id,
                pending.skill_name,
                pending.params,
            )
            try:
                reply = await _confirm_pending_action(farm_id, pending)
            except Exception as exc:
                logger.error("执行 pending action 失败: %s", exc)
                reply = f"执行失败：{exc}"
                remove_pending(farm_id)
            yield reply
            return

        if intent == "cancel":
            logger.info("用户取消操作 | farm=%s skill=%s", farm_id, pending.skill_name)
            remove_pending(farm_id)
            yield "已取消操作。"
            return

        # intent == "modify"：继续走 LangGraph，让 LLM 根据上下文重新决策

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
