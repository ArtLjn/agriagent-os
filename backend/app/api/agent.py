"""Agent API 路由，提供农事建议、对话和报告接口。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    DailyAdviceResponse,
    ReportRequest,
    ReportResponse,
    AdviceHistoryItem,
    ReportHistoryItem,
)
from app.services.agent_service import (
    chat_with_agent,
    get_daily_advice,
    generate_report,
    get_advice_history,
    get_report_history,
)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
def agent_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """与农事顾问 Agent 对话。

    Args:
        request: 对话请求，包含用户消息和可选的周期 ID。
        db: 数据库会话。

    Returns:
        Agent 回复。
    """
    return chat_with_agent(db, request.message, request.cycle_id)


@router.get("/daily", response_model=DailyAdviceResponse)
def daily_advice(
    cycle_id: int | None = Query(None, description="关联种植周期 ID"),
    db: Session = Depends(get_db),
) -> DailyAdviceResponse:
    """获取每日农事建议。

    Args:
        cycle_id: 种植周期 ID（可选，不指定则生成通用建议）。
        db: 数据库会话。

    Returns:
        每日建议，包含生成时间。
    """
    return get_daily_advice(db, cycle_id)


@router.post("/report", response_model=ReportResponse)
def agent_report(
    request: ReportRequest,
    db: Session = Depends(get_db),
) -> ReportResponse:
    """生成种植周期报告。

    Args:
        request: 报告请求，包含周期 ID 和报告类型。
        db: 数据库会话。

    Returns:
        生成的报告。
    """
    return generate_report(db, request.cycle_id, request.report_type)


@router.get("/advice-history", response_model=list[AdviceHistoryItem])
def advice_history(
    cycle_id: int | None = Query(None, description="按周期筛选"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[AdviceHistoryItem]:
    """查询建议历史记录。

    Args:
        cycle_id: 按周期筛选（可选）。
        limit: 返回数量限制。
        db: 数据库会话。

    Returns:
        建议历史列表。
    """
    return get_advice_history(db, cycle_id, limit)


@router.get("/report-history", response_model=list[ReportHistoryItem])
def report_history(
    cycle_id: int | None = Query(None, description="按周期筛选"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ReportHistoryItem]:
    """查询报告历史记录。

    Args:
        cycle_id: 按周期筛选（可选）。
        limit: 返回数量限制。
        db: 数据库会话。

    Returns:
        报告历史列表。
    """
    return get_report_history(db, cycle_id, limit)


__all__ = ["router"]
