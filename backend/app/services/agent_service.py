"""Agent 服务层，封装 Agent 调用与记录持久化。"""

from sqlalchemy.orm import Session

from app.agents.advisor import invoke_advisor
from app.agents.report import generate_cycle_report
from app.models.agent import AdviceRecord, ReportRecord
from app.schemas.agent import ChatResponse, DailyAdviceResponse, ReportResponse


def chat_with_agent(db: Session, message: str, cycle_id: int | None = None, farm_id: int = 1) -> ChatResponse:
    """与用户进行 Agent 对话，保存记录。

    Args:
        db: 数据库会话。
        message: 用户消息。
        cycle_id: 关联的种植周期 ID（可选）。
        farm_id: 农场 ID。

    Returns:
        Agent 回复。
    """
    context = f"【关联周期 ID: {cycle_id}】\n" if cycle_id else ""
    full_input = context + message
    reply = invoke_advisor(full_input)

    record = AdviceRecord(cycle_id=cycle_id, advice_type="chat", content=reply, farm_id=farm_id)
    db.add(record)
    db.commit()

    return ChatResponse(reply=reply)


def get_daily_advice(db: Session, cycle_id: int | None = None, farm_id: int = 1) -> DailyAdviceResponse:
    """生成每日农事建议并保存。

    Args:
        db: 数据库会话。
        cycle_id: 关联的种植周期 ID（可选）。
        farm_id: 农场 ID。

    Returns:
        每日建议。
    """
    prompt = "请生成今天的农事建议，考虑当前天气和种植周期阶段。"
    if cycle_id:
        prompt = f"请为周期 ID={cycle_id} 生成今天的农事建议，查询天气和周期信息。"
    advice = invoke_advisor(prompt)

    record = AdviceRecord(cycle_id=cycle_id, advice_type="daily", content=advice, farm_id=farm_id)
    db.add(record)
    db.commit()
    db.refresh(record)

    return DailyAdviceResponse(
        cycle_id=record.cycle_id,
        advice=record.content,
        created_at=record.created_at,
    )


def generate_report(
    db: Session, cycle_id: int | None = None, report_type: str = "weekly", farm_id: int = 1
) -> ReportResponse:
    """生成种植周期报告并保存。

    Args:
        db: 数据库会话。
        cycle_id: 关联的种植周期 ID（可选）。
        report_type: 报告类型（weekly / monthly）。
        farm_id: 农场 ID。

    Returns:
        生成的报告。
    """
    if cycle_id:
        content = generate_cycle_report(cycle_id)
    else:
        content = invoke_advisor(f"请生成一份{report_type}综合报告，查询所有活跃周期的信息。")

    record = ReportRecord(cycle_id=cycle_id, report_type=report_type, content=content)
    db.add(record)
    db.commit()
    db.refresh(record)

    return ReportResponse(
        cycle_id=record.cycle_id,
        report_type=record.report_type,
        content=record.content,
        created_at=record.created_at,
    )


def get_advice_history(
    db: Session, cycle_id: int | None = None, limit: int = 20
) -> list[AdviceRecord]:
    """查询建议历史。

    Args:
        db: 数据库会话。
        cycle_id: 按周期筛选（可选）。
        limit: 返回数量限制。

    Returns:
        建议记录列表。
    """
    query = db.query(AdviceRecord)
    if cycle_id is not None:
        query = query.filter(AdviceRecord.cycle_id == cycle_id)
    return query.order_by(AdviceRecord.created_at.desc()).limit(limit).all()


def get_report_history(
    db: Session, cycle_id: int | None = None, limit: int = 20
) -> list[ReportRecord]:
    """查询报告历史。

    Args:
        db: 数据库会话。
        cycle_id: 按周期筛选（可选）。
        limit: 返回数量限制。

    Returns:
        报告记录列表。
    """
    query = db.query(ReportRecord)
    if cycle_id is not None:
        query = query.filter(ReportRecord.cycle_id == cycle_id)
    return query.order_by(ReportRecord.created_at.desc()).limit(limit).all()


__all__ = [
    "chat_with_agent",
    "get_daily_advice",
    "generate_report",
    "get_advice_history",
    "get_report_history",
]
