from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.modules.farm.dependencies import get_current_farm
from app.models.farm import Farm
from app.schemas.common import PaginatedResponse
from app.schemas.log import FarmLogCreate, FarmLogResponse
from app.services import log_service

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("", response_model=FarmLogResponse)
def create_log(
    log: FarmLogCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建农事日志。"""
    try:
        return log_service.create_log(db, log, farm_id=farm.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=PaginatedResponse[FarmLogResponse])
def list_logs(
    cycle_id: int | None = None,
    operation_type: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """获取农事日志列表，支持按周期 ID 和操作类型筛选（分页）。"""
    skip = (page - 1) * size
    items = log_service.get_logs(
        db,
        farm_id=farm.id,
        cycle_id=cycle_id,
        operation_type=operation_type,
        skip=skip,
        limit=size,
    )
    total = log_service.count_logs(
        db, farm_id=farm.id, cycle_id=cycle_id, operation_type=operation_type
    )
    return {"items": items, "total": total}


@router.put("/{log_id}", response_model=FarmLogResponse)
def update_log(
    log_id: int,
    log: FarmLogCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """更新农事日志。"""
    try:
        return log_service.update_log(db, log_id, log, farm_id=farm.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{log_id}")
def delete_log(
    log_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """删除农事日志。"""
    try:
        log_service.delete_log(db, log_id, farm_id=farm.id)
        return {"message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


__all__ = ["router"]
