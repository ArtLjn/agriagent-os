from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.cost import (
    CostRecordCreate,
    CostRecordUpdate,
    CostRecordResponse,
    CycleProfit,
    YearlySummary,
    CostParseRequest,
    CostParseResponse,
)
from app.services import cost_service
from app.core.llm import LlmNotConfiguredError

router = APIRouter(prefix="/costs", tags=["costs"])


@router.post("", response_model=CostRecordResponse)
def create_record(
    record: CostRecordCreate,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
):
    """创建一条成本或收入记录。"""
    return cost_service.create_record(db, record, farm_id=farm_id)


@router.get("", response_model=list[CostRecordResponse])
def list_records(
    cycle_id: int | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
):
    """查询成本记账记录列表（支持日期范围筛选）。"""
    return cost_service.get_records_filtered(
        db,
        farm_id=farm_id,
        cycle_id=cycle_id,
        category=category,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/cycles/{cycle_id}/profit", response_model=CycleProfit)
def get_cycle_profit(
    cycle_id: int,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
):
    """获取指定种植周期的利润统计。"""
    return cost_service.get_cycle_profit(db, cycle_id, farm_id=farm_id)


@router.get("/summary/{year}", response_model=YearlySummary)
def get_yearly_summary(
    year: int,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
):
    """获取指定年度的收支汇总。"""
    return cost_service.get_yearly_summary(db, year, farm_id=farm_id)


@router.post("/parse", response_model=CostParseResponse)
async def parse_cost_record(
    request: CostParseRequest,
    farm_id: int = Query(1, description="农场 ID"),
) -> CostParseResponse:
    """AI 解析自然语言记账描述，返回结构化数据。"""
    try:
        return await cost_service.parse_record(request.description)
    except LlmNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.put("/{record_id}", response_model=CostRecordResponse)
def update_record(
    record_id: int,
    update: CostRecordUpdate,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
):
    """更新一条成本或收入记录。"""
    try:
        return cost_service.update_record(db, record_id, update, farm_id=farm_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{record_id}")
def delete_record(
    record_id: int,
    farm_id: int = Query(1, description="农场 ID"),
    db: Session = Depends(get_db),
):
    """删除一条成本或收入记录。"""
    try:
        cost_service.delete_record(db, record_id, farm_id=farm_id)
        return {"message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
