from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.cost import CostRecordCreate, CostRecordResponse, CycleProfit, YearlySummary
from app.services import cost_service

router = APIRouter(prefix="/costs", tags=["costs"])


@router.post("", response_model=CostRecordResponse)
def create_record(record: CostRecordCreate, db: Session = Depends(get_db)):
    """创建一条成本或收入记录。"""
    return cost_service.create_record(db, record)


@router.get("", response_model=list[CostRecordResponse])
def list_records(
    cycle_id: int | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """查询成本记账记录列表。"""
    return cost_service.get_records(db, cycle_id=cycle_id, category=category)


@router.get("/cycles/{cycle_id}/profit", response_model=CycleProfit)
def get_cycle_profit(cycle_id: int, db: Session = Depends(get_db)):
    """获取指定种植周期的利润统计。"""
    return cost_service.get_cycle_profit(db, cycle_id)


@router.get("/summary/{year}", response_model=YearlySummary)
def get_yearly_summary(year: int, db: Session = Depends(get_db)):
    """获取指定年度的收支汇总。"""
    return cost_service.get_yearly_summary(db, year)
