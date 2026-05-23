from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.log import FarmLogCreate, FarmLogResponse
from app.services import log_service

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("", response_model=FarmLogResponse)
def create_log(log: FarmLogCreate, db: Session = Depends(get_db)):
    """创建农事日志。"""
    return log_service.create_log(db, log)


@router.get("", response_model=list[FarmLogResponse])
def list_logs(
    cycle_id: int | None = None,
    operation_type: str | None = None,
    db: Session = Depends(get_db),
):
    """获取农事日志列表，支持按周期 ID 和操作类型筛选。"""
    return log_service.get_logs(db, cycle_id=cycle_id, operation_type=operation_type)


__all__ = ["router"]
