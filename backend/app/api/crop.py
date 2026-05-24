from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_farm
from app.models.farm import Farm
from app.schemas.crop import CropTemplateCreate, CropTemplateResponse
from app.services import crop_service

router = APIRouter(prefix="/crops", tags=["crops"])


@router.post("/templates", response_model=CropTemplateResponse)
def create_template(
    template: CropTemplateCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建作物模板。"""
    return crop_service.create_crop_template(db, template, farm_id=farm.id)


@router.get("/templates", response_model=list[CropTemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """获取所有作物模板列表。"""
    return crop_service.get_crop_templates(db, farm_id=farm.id)


@router.get("/templates/{template_id}", response_model=CropTemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """根据 ID 获取作物模板详情。"""
    template = crop_service.get_crop_template(db, template_id, farm_id=farm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


__all__ = ["router"]
