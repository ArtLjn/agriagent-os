"""Agent 服务层，封装 Agent 调用与记录持久化。"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.orm import Session

from app.agents.advisor import invoke_advisor, stream_advisor
from app.agents.report import generate_cycle_report
from app.models.agent import AdviceRecord, ReportRecord
from app.schemas.agent import ChatResponse, DailyAdviceResponse, ReportResponse

logger = logging.getLogger(__name__)


async def chat_with_agent(db: Session, message: str, cycle_id: int | None = None, farm_id: int = 1) -> ChatResponse:
    """与用户进行 Agent 对话，保存记录。"""
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    logger.info("开始对话 | farm=%s cycle=%s | input: %s", farm_id, cycle_id, message[:100])
    reply = await invoke_advisor(full_input, farm_id=farm_id)

    record = AdviceRecord(cycle_id=cycle_id, advice_type="chat", content=reply, farm_id=farm_id)
    db.add(record)
    db.commit()
    logger.info("对话记录已保存 | record_id=%s", record.id)

    return ChatResponse(reply=reply)


async def stream_chat_with_agent(
    message: str, cycle_id: int | None = None, farm_id: int = 1
) -> AsyncGenerator[str, None]:
    """流式与 Agent 对话，逐 token 返回。"""
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    async for chunk in stream_advisor(full_input, farm_id=farm_id):
        yield chunk


async def get_daily_advice(db: Session, cycle_id: int | None = None, farm_id: int = 1) -> DailyAdviceResponse:
    """生成每日农事建议并保存。"""
    prompt = "请生成今天的农事建议，考虑当前天气和种植周期阶段。"
    if cycle_id:
        prompt = f"请为周期 ID={cycle_id} 生成今天的农事建议，查询天气和周期信息。"
    logger.info("生成每日建议 | farm=%s cycle=%s", farm_id, cycle_id)
    advice = await invoke_advisor(prompt, farm_id=farm_id)

    record = AdviceRecord(cycle_id=cycle_id, advice_type="daily", content=advice, farm_id=farm_id)
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("建议已保存 | record_id=%s", record.id)

    return DailyAdviceResponse(
        cycle_id=record.cycle_id,
        advice=record.content,
        created_at=record.created_at,
    )


async def generate_report(
    db: Session, cycle_id: int | None = None, report_type: str = "weekly", farm_id: int = 1
) -> ReportResponse:
    """生成种植周期报告并保存。"""
    logger.info("生成报告 | type=%s cycle=%s farm=%s", report_type, cycle_id, farm_id)
    if cycle_id:
        content = await generate_cycle_report(cycle_id)
    else:
        content = await invoke_advisor(f"请生成一份{report_type}综合报告，查询所有活跃周期的信息。", farm_id=farm_id)

    record = ReportRecord(cycle_id=cycle_id, report_type=report_type, content=content, farm_id=farm_id)
    db.add(record)
    db.commit()
    db.refresh(record)
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
    "generate_report",
    "get_advice_history",
    "get_report_history",
]
