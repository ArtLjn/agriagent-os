from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_farm
from app.models.farm import Farm
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


@router.get("", response_model=list[CropCycleListResponse])
def list_cycles(
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """获取所有茬口列表。"""
    cycles = cycle_service.get_crop_cycles(db, farm_id=farm.id)
    result = []
    for c in cycles:
        current = next((s for s in c.stages if s.is_current), None)
        result.append(
            CropCycleListResponse(
                id=c.id,
                name=c.name,
                crop_template_name=c.crop_template.name,
                start_date=c.start_date,
                status=c.status,
                current_stage_name=current.name if current else None,
            )
        )
    return result


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


__all__ = ["router"]
