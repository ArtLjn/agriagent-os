"""Agent 服务层，封装 Agent 调用与记录持久化。"""

import json
import logging
import time
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.advisor import invoke_advisor, stream_advisor
from app.agent.guardrails import filter_output
from app.agent.llm import get_llm
from app.agent.prompt_composer import get_composer
from app.agent.skills import get_langchain_tools
from app.core.json_repair import safe_parse_json
from langchain_core.messages import HumanMessage
from app.infra.pending_actions import (
    detect_user_intent,
    get_pending,
    remove_pending,
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

logger = logging.getLogger(__name__)


# title 超过此长度截断并加省略号
_TITLE_MAX_DISPLAY = 10
_ADVICE_ITEM_MAX = 5


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
        conversation = get_or_create_conversation(db, farm_id, session_id, user_id=user_id)
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
                result = await _execute_pending_action(
                    farm_id, pending.skill_name, pending.params
                )
                reply = f"已执行：{result}"
            except Exception as exc:
                logger.error("执行 pending action 失败: %s", exc)
                reply = f"执行失败：{exc}"
            finally:
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
        conversation = get_or_create_conversation(db, farm_id, session_id, user_id=user_id)
        save_message(db, conversation.id, "user", message)

    # 检查是否有 pending action（写操作确认流程）
    pending = get_pending(farm_id)
    if pending is not None:
        intent = detect_user_intent(message)

        if intent == "confirm":
            logger.info(
                "用户确认执行 | farm=%s skill=%s params=%s",
                farm_id, pending.skill_name, pending.params,
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
    """生成结构化种植报告并保存。"""
    logger.info("生成报告 | type=%s cycle=%s farm=%s", report_type, cycle_id, farm_id)

    from app.services import report_data_service
    from app.schemas.structured_report import (
        StructuredReportData,
        ReportOverviewMetrics,
        ReportCycleItem,
        ReportCostItem,
        ReportLogItem,
        ReportAdviceItem,
    )
    from pathlib import Path
    from jinja2 import Template

    # 1. 获取结构化数据（数据库精确计算）
    if report_type == "monthly":
        report_data = await report_data_service.get_monthly_report_data(db, farm_id)
    else:
        report_data = await report_data_service.get_weekly_report_data(db, farm_id)

    # 如果指定了 cycle_id，过滤数据只保留该茬口
    if cycle_id is not None:
        report_data.cycles = [c for c in report_data.cycles if c["cycle_id"] == cycle_id]
        report_data.costs = [c for c in report_data.costs if c.get("cycle_id") == cycle_id]
        report_data.logs = [log for log in report_data.logs if log.get("cycle_id") == cycle_id]

    # 2. 调用 LLM 生成总结和建议
    import json
    data_json = json.dumps(
        {
            "report_type": report_data.report_type,
            "period": f"{report_data.period_start.isoformat()} ~ {report_data.period_end.isoformat()}",
            "overview": report_data.overview,
            "cycles": report_data.cycles,
            "costs": report_data.costs,
            "logs": report_data.logs,
        },
        ensure_ascii=False,
        default=str,
    )

    prompts_dir = Path(__file__).parent.parent.parent / "prompts"
    template_path = prompts_dir / "structured_report.j2"
    prompt_text = Template(template_path.read_text()).render(
        report_data_json=data_json
    )

    llm = get_llm()
    response = await llm.ainvoke([HumanMessage(content=prompt_text)])
    raw = filter_output(response.content or "")

    # 3. 解析 LLM 返回的 JSON
    summary = ""
    advice_items: list[ReportAdviceItem] = []
    try:
        parsed = safe_parse_json(raw)
        if isinstance(parsed, dict):
            summary = str(parsed.get("summary", ""))[:200]
            for item in parsed.get("advice_items", []):
                advice_items.append(
                    ReportAdviceItem(
                        title=str(item.get("title", ""))[:20],
                        detail=str(item.get("detail", ""))[:100],
                        priority=int(item.get("priority", 2)),
                    )
                )
    except Exception as exc:
        logger.warning("报告建议解析失败，使用 fallback | error=%s", exc)
        summary = raw[:100] if raw else "报告生成完成"
        advice_items = [
            ReportAdviceItem(
                title="农事建议",
                detail=summary[:100],
                priority=2,
            )
        ]

    # 4. 组装结构化数据
    structured_data = StructuredReportData(
        report_type=report_data.report_type,
        period_start=report_data.period_start,
        period_end=report_data.period_end,
        overview=ReportOverviewMetrics(**report_data.overview),
        cycles=[ReportCycleItem(**c) for c in report_data.cycles],
        costs=[ReportCostItem(**c) for c in report_data.costs],
        logs=[ReportLogItem(**log) for log in report_data.logs],
        advice=advice_items,
        summary=summary,
    )

    # 5. 组装纯文本内容（兼容旧版 + 便于人类阅读）
    type_label = "周报" if report_type == "weekly" else "月报"
    content_lines = [
        f"## {type_label} ({report_data.period_start} ~ {report_data.period_end})",
        "",
        f"**农场概览**：活跃茬口 {structured_data.overview.active_cycles} 个，"
        f"农事 {structured_data.overview.log_count} 次，"
        f"净收支 {structured_data.overview.net_profit} 元",
        "",
        f"**总结**：{summary}",
        "",
        "**建议**：",
    ]
    for item in advice_items:
        priority_label = {1: "【高】", 2: "【中】", 3: "【低】"}.get(item.priority, "")
        content_lines.append(f"- {priority_label}{item.title}：{item.detail}")
    content = "\n".join(content_lines)

    # 6. 保存到数据库（content 存纯文本，meta 存结构化数据 JSON）
    import json

    record = AgentRecord(
        cycle_id=cycle_id,
        record_type=report_type,
        content=content,
        meta=json.dumps(structured_data.model_dump(mode="json"), ensure_ascii=False),
        farm_id=farm_id,
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
        report_type=record.record_type,
        content=record.content,
        structured_data=structured_data.model_dump(mode="json"),
        created_at=record.created_at,
    )


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
