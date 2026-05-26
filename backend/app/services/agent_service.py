"""Agent 服务层，封装 Agent 调用与记录持久化。"""

import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy.orm import Session

from app.agents.advisor import invoke_advisor, stream_advisor
from app.agents.report import generate_cycle_report
from app.core.json_repair import safe_parse_json
from app.core.pending_actions import (
    detect_user_intent,
    get_pending,
    is_write_skill,
    remove_pending,
    store_pending,
)
from app.models.agent import AdviceRecord, ReportRecord
from app.schemas.agent import (
    AdviceItem,
    ChatResponse,
    DailyAdviceResponse,
    ReportResponse,
)
from app.skills import build_skill_context, get_langchain_tools

logger = logging.getLogger(__name__)


async def _try_skillify_route(
    message: str, farm_id: int = 1
) -> tuple[str, dict] | None:
    """skillify 预路由：fast_match + LLM 意图兜底。

    返回 (skill_name, params) 命中时，否则返回 None 走 LangGraph。
    """
    from app.skills import get_skill_manager

    try:
        manager = get_skill_manager()
        context = build_skill_context(farm_id=farm_id)
        result = await manager.handle(message, context)
        if result.match and result.match.skill_name:
            logger.info(
                "skillify 预路由命中 | source=%s | skill=%s",
                result.source,
                result.match.skill_name,
            )
            return result.match.skill_name, result.match.params or {}
    except Exception as exc:
        logger.warning("skillify 预路由异常，降级到 LangGraph | error=%s", exc)
    return None


# title 超过此长度截断并加省略号
_TITLE_MAX_DISPLAY = 10
_ADVICE_ITEM_MAX = 5


def _truncate_title(title: str) -> str:
    """截断超长 title，超过 _TITLE_MAX_DISPLAY 字则加省略号。"""
    if len(title) > _TITLE_MAX_DISPLAY:
        return title[:_TITLE_MAX_DISPLAY] + "…"
    return title


def _parse_advice_items(raw: str) -> list[AdviceItem]:
    """解析 LLM 返回的 JSON 数组为 AdviceItem 列表，失败则 fallback。"""
    try:
        parsed = safe_parse_json(raw)
        # safe_parse_json 返回 dict，但 LLM 应输出 JSON 数组
        if isinstance(parsed, list):
            items_raw = parsed
        elif isinstance(parsed, dict):
            # 兜底：如果返回的是单条 dict，包装为列表
            items_raw = [parsed]
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
        # 按 priority 升序排列
        items.sort(key=lambda x: x.priority)
        return items
    except (ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("建议 JSON 解析失败，fallback 为单条 | error=%s", exc)
        return [
            AdviceItem(
                title="今日农事建议",
                detail=raw[:50],
                priority=2,
                icon="📋",
            )
        ]


async def _execute_pending_action(farm_id: int, skill_name: str, params: dict) -> str:
    """执行 pending action 中存储的写操作 Skill。"""
    tool_map = {t.name: t for t in get_langchain_tools()}
    tool = tool_map.get(skill_name)
    if not tool:
        return f"未知工具: {skill_name}"
    result = await tool.ainvoke(params)
    return str(result)


async def _execute_skill(skill_name: str, params: dict) -> str:
    """直接执行指定 Skill 并返回结果文本。"""
    tool_map = {t.name: t for t in get_langchain_tools()}
    tool = tool_map.get(skill_name)
    if not tool:
        return f"未知工具: {skill_name}"
    result = await tool.ainvoke(params)
    return str(result)


async def _invoke_advisor_fallback(
    message: str, cycle_id: int | None, farm_id: int
) -> str:
    """LangGraph 兜底调用。"""
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    return await invoke_advisor(full_input, farm_id=farm_id)


async def chat_with_agent(
    db: Session, message: str, cycle_id: int | None = None, farm_id: int = 1
) -> ChatResponse:
    """与用户进行 Agent 对话，支持写操作确认流程。"""
    logger.info(
        "开始对话 | farm=%s cycle=%s | input: %s", farm_id, cycle_id, message[:100]
    )

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
                result = await _execute_pending_action(
                    farm_id, pending.skill_name, pending.params
                )
                reply = f"已执行：{result}"
            except Exception as exc:
                logger.error("执行 pending action 失败: %s", exc)
                reply = f"执行失败：{exc}"
            finally:
                remove_pending(farm_id)

            record = AdviceRecord(
                cycle_id=cycle_id, advice_type="chat", content=reply, farm_id=farm_id
            )
            db.add(record)
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
            return ChatResponse(reply=reply)

        if intent == "cancel":
            # 用户取消：删除 pending action
            logger.info("用户取消操作 | farm=%s skill=%s", farm_id, pending.skill_name)
            remove_pending(farm_id)
            reply = "已取消操作。"
            record = AdviceRecord(
                cycle_id=cycle_id, advice_type="chat", content=reply, farm_id=farm_id
            )
            db.add(record)
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
            return ChatResponse(reply=reply)

        # intent == "modify"：用户修正参数，交给 LLM 处理
        # 保留 pending action 不删除，让 LLM 根据上下文重新决策

    # 无 pending action 或用户修正参数 → 先尝试 skillify 预路由
    skillify_match = await _try_skillify_route(message, farm_id=farm_id)
    if skillify_match:
        skill_name, skill_params = skillify_match
        if is_write_skill(skill_name):
            # 写操作：预路由只做意图识别，参数提取交给 LangGraph
            logger.info(
                "skillify 预路由 → 写操作，交给 LangGraph 提取参数 | skill=%s",
                skill_name,
            )
        else:
            # 只读操作：预路由命中后直接执行
            try:
                reply = await _execute_skill(skill_name, skill_params)
            except Exception as exc:
                logger.error("skillify 预路由执行失败 | skill=%s error=%s", skill_name, exc)
                reply = await _invoke_advisor_fallback(message, cycle_id, farm_id)

            record = AdviceRecord(
                cycle_id=cycle_id, advice_type="chat", content=reply, farm_id=farm_id
            )
            db.add(record)
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
            return ChatResponse(reply=reply)

    # 预路由未命中（或写操作需要参数提取）→ 走 LangGraph
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    reply = await invoke_advisor(full_input, farm_id=farm_id)

    record = AdviceRecord(
        cycle_id=cycle_id, advice_type="chat", content=reply, farm_id=farm_id
    )
    db.add(record)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info("对话记录已保存 | record_id=%s", record.id)

    return ChatResponse(reply=reply)


async def stream_chat_with_agent(
    message: str, cycle_id: int | None = None, farm_id: int = 1
) -> AsyncGenerator[str, None]:
    """流式与 Agent 对话，逐 token 返回。支持 skillify 预路由。"""
    from app.core.guardrails import check_input, filter_output

    # skillify 预路由（只读 skill 直接执行，写操作和未命中走 LangGraph）
    skillify_match = await _try_skillify_route(message, farm_id=farm_id)
    if skillify_match:
        skill_name, skill_params = skillify_match
        if not is_write_skill(skill_name):
            try:
                result = await _execute_skill(skill_name, skill_params)
                yield filter_output(result)
                return
            except Exception as exc:
                logger.warning(
                    "stream 预路由执行失败，降级 LangGraph | skill=%s error=%s",
                    skill_name,
                    exc,
                )

    # 写操作或未命中 → 走 LangGraph 流式
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    async for chunk in stream_advisor(full_input, farm_id=farm_id):
        yield chunk


async def get_daily_advice(
    db: Session, cycle_id: int | None = None, farm_id: int = 1
) -> DailyAdviceResponse:
    """生成每日农事建议并保存。命中今日缓存则直接返回。"""
    # 缓存命中检查：查询今日已有记录（本地时间计算今天起点）
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    cached = (
        db.query(AdviceRecord)
        .filter(
            AdviceRecord.farm_id == farm_id,
            AdviceRecord.advice_type == "daily",
            AdviceRecord.created_at >= today_start,
        )
        .order_by(AdviceRecord.created_at.desc())
        .first()
    )
    if cached:
        items = _parse_advice_items(cached.content)
        logger.info("缓存命中 | record_id=%s", cached.id)
        return DailyAdviceResponse(
            cycle_id=cached.cycle_id,
            items=items,
            created_at=cached.created_at,
        )

    base_prompt = (
        "请生成今天的农事建议。你必须以 JSON 数组格式回复，格式为："
        '[{"title":"≤10字结论","detail":"≤40字原因","priority":1到3,"icon":"emoji"}]。'
        "最多5条，按紧急程度排序。"
    )
    if cycle_id:
        prompt = f"请为周期 ID={cycle_id} 生成今天的农事建议。{base_prompt}"
    else:
        prompt = base_prompt
    logger.info("生成每日建议 | farm=%s cycle=%s", farm_id, cycle_id)
    advice = await invoke_advisor(prompt, farm_id=farm_id)

    items = _parse_advice_items(advice)

    record = AdviceRecord(
        cycle_id=cycle_id, advice_type="daily", content=advice, farm_id=farm_id
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
        items=items,
        created_at=record.created_at,
    )


async def refresh_daily_advice(
    db: Session, cycle_id: int | None = None, farm_id: int = 1
) -> DailyAdviceResponse:
    """强制刷新每日农事建议：删除今日旧记录后重新生成。"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    db.query(AdviceRecord).filter(
        AdviceRecord.farm_id == farm_id,
        AdviceRecord.advice_type == "daily",
        AdviceRecord.cycle_id == cycle_id if cycle_id is not None else True,
        AdviceRecord.created_at >= today_start,
    ).delete(synchronize_session=False)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    logger.info("已清除今日旧建议 | farm=%s cycle=%s", farm_id, cycle_id)
    return await get_daily_advice(db, cycle_id, farm_id)


async def generate_report(
    db: Session,
    cycle_id: int | None = None,
    report_type: str = "weekly",
    farm_id: int = 1,
) -> ReportResponse:
    """生成种植周期报告并保存。"""
    logger.info("生成报告 | type=%s cycle=%s farm=%s", report_type, cycle_id, farm_id)
    if cycle_id:
        content = await generate_cycle_report(cycle_id)
    else:
        content = await invoke_advisor(
            f"请生成一份{report_type}综合报告，查询所有活跃周期的信息。",
            farm_id=farm_id,
        )

    record = ReportRecord(
        cycle_id=cycle_id, report_type=report_type, content=content, farm_id=farm_id
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        raise
    logger.info("报告已保存 | record_id=%s", record.id)

    return ReportResponse(
        cycle_id=record.cycle_id,
        report_type=record.report_type,
        content=record.content,
        created_at=record.created_at,
    )


def get_advice_history(
    db: Session, cycle_id: int | None = None, limit: int = 20, farm_id: int = 1
) -> list[AdviceRecord]:
    """查询建议历史。"""
    query = db.query(AdviceRecord).filter(AdviceRecord.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(AdviceRecord.cycle_id == cycle_id)
    return query.order_by(AdviceRecord.created_at.desc()).limit(limit).all()


def get_report_history(
    db: Session, cycle_id: int | None = None, limit: int = 20, farm_id: int = 1
) -> list[ReportRecord]:
    """查询报告历史。"""
    query = db.query(ReportRecord).filter(ReportRecord.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(ReportRecord.cycle_id == cycle_id)
    return query.order_by(ReportRecord.created_at.desc()).limit(limit).all()


__all__ = [
    "chat_with_agent",
    "stream_chat_with_agent",
    "get_daily_advice",
    "refresh_daily_advice",
    "generate_report",
    "get_advice_history",
    "get_report_history",
]
