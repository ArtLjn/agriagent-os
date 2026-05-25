from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_farm
from app.models.farm import Farm
from app.schemas.common import PaginatedResponse
from app.schemas.cycle import CropCycleCreate, CropCycleResponse, CropCycleListResponse
from app.services import cycle_service

router = APIRouter(prefix="/cycles", tags=["cycles"])


@router.post("", response_model=CropCycleResponse)
def create_cycle(
    cycle: CropCycleCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建茬口。"""
    try:
        return cycle_service.create_crop_cycle(db, cycle, farm_id=farm.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=PaginatedResponse[CropCycleListResponse])
def list_cycles(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """获取茬口列表（分页）。"""
    skip = (page - 1) * size
    cycles = cycle_service.get_crop_cycles(db, farm_id=farm.id, skip=skip, limit=size)
    total = cycle_service.count_crop_cycles(db, farm_id=farm.id)
    items = []
    for c in cycles:
        current = next((s for s in c.stages if s.is_current), None)
        items.append(
            CropCycleListResponse(
                id=c.id,
                name=c.name,
                crop_template_name=c.crop_template.name,
                start_date=c.start_date,
                status=c.status,
                current_stage_name=current.name if current else None,
            )
        )
    return {"items": items, "total": total}


@router.get("/{cycle_id}", response_model=CropCycleResponse)
def get_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """根据 ID 获取茬口详情。"""
    cycle = cycle_service.get_crop_cycle(db, cycle_id, farm_id=farm.id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return cycle


@router.put("/{cycle_id}", response_model=CropCycleResponse)
def update_cycle(
    cycle_id: int,
    cycle: CropCycleCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """更新茬口。"""
    try:
        return cycle_service.update_crop_cycle(db, cycle_id, cycle, farm_id=farm.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{cycle_id}")
def delete_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """删除茬口。"""
    try:
        cycle_service.delete_crop_cycle(db, cycle_id, farm_id=farm.id)
        return {"message": "删除成功"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{cycle_id}/advance-stage", response_model=CropCycleResponse)
def advance_stage(
    cycle_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """推进茬口到下一阶段。"""
    try:
        return cycle_service.advance_stage(db, cycle_id, farm_id=farm.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


__all__ = ["router"]
