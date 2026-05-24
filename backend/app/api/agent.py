"""Agent API 路由，提供农事建议、对话和报告接口。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_farm
from app.core.llm import LlmNotConfiguredError
from app.models.farm import Farm
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
    farm: Farm = Depends(get_current_farm),
) -> ChatResponse:
    """与农事顾问 Agent 对话。"""
    try:
        return chat_with_agent(db, request.message, request.cycle_id, farm_id=farm.id)
    except LlmNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/daily", response_model=DailyAdviceResponse)
def daily_advice(
    cycle_id: int | None = Query(None, description="关联种植周期 ID"),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> DailyAdviceResponse:
    """获取每日农事建议。"""
    try:
        return get_daily_advice(db, cycle_id, farm_id=farm.id)
    except LlmNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/report", response_model=ReportResponse)
def agent_report(
    request: ReportRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> ReportResponse:
    """生成种植周期报告。"""
    try:
        return generate_report(db, request.cycle_id, request.report_type, farm_id=farm.id)
    except LlmNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/advice-history", response_model=list[AdviceHistoryItem])
def advice_history(
    cycle_id: int | None = Query(None, description="按周期筛选"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> list[AdviceHistoryItem]:
    """查询建议历史记录。"""
    return get_advice_history(db, cycle_id, limit, farm_id=farm.id)


@router.get("/report-history", response_model=list[ReportHistoryItem])
def report_history(
    cycle_id: int | None = Query(None, description="按周期筛选"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> list[ReportHistoryItem]:
    """查询报告历史记录。"""
    return get_report_history(db, cycle_id, limit, farm_id=farm.id)


__all__ = ["router"]
