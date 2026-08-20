"""作物模板 CRUD 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy.orm import Session

from business.api.deps import get_current_user
from business.api.schemas import StrictRequest
from business.db import get_db
from business.services import crop_service

router = APIRouter(prefix="/crop-templates", tags=["crop-templates"])


class StageRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=100)
    duration_days: int = Field(ge=1, le=3650)
    order_index: int = Field(ge=0)
    key_tasks: str | None = Field(default=None, max_length=500)


class TemplateRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=100)
    variety: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=50)
    stages: list[StageRequest] = Field(min_length=1)


@router.get("/system/list")
def list_system_templates(
    category: str | None = Query(default=None, max_length=50),
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return {"items": crop_service.list_system_templates(db, category=category)}


@router.post("/system/{template_id}/import")
def import_system_template(
    template_id: int,
    response: Response,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = crop_service.import_system_template(
            db, system_template_id=template_id, farm_id=user["farm_id"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if result.already_exists:
        response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_201_CREATED
    return {
        "id": result.template_id,
        "already_exists": result.already_exists,
    }


@router.get("")
def list_templates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    items = crop_service.get_crop_templates(
        db,
        farm_id=user["farm_id"],
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    total = crop_service.count_crop_templates(db, farm_id=user["farm_id"])
    return {"items": items, "total": total}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_template(
    request: TemplateRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    duplicate = crop_service.find_exact_duplicate(
        db,
        farm_id=user["farm_id"],
        name=request.name,
        variety=request.variety,
        stages=[stage.model_dump() for stage in request.stages],
    )
    if duplicate is not None:
        existing = crop_service.get_crop_template(
            db, duplicate.id, farm_id=user["farm_id"]
        )
        return {**existing, "already_exists": True}
    created = crop_service.create_crop_template(
        db,
        farm_id=user["farm_id"],
        name=request.name,
        variety=request.variety,
        category=request.category,
        stages=[stage.model_dump() for stage in request.stages],
    )
    return {**created, "already_exists": False}


@router.get("/{template_id}")
def get_template(
    template_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    template = crop_service.get_crop_template(db, template_id, farm_id=user["farm_id"])
    if template is None:
        raise HTTPException(status_code=404, detail="模板不存在")
    return template


@router.put("/{template_id}")
@router.patch("/{template_id}")
def update_template(
    template_id: int,
    request: TemplateRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return crop_service.update_crop_template(
            db,
            template_id,
            farm_id=user["farm_id"],
            name=request.name,
            variety=request.variety,
            stages=[stage.model_dump() for stage in request.stages],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        crop_service.delete_crop_template(db, template_id, farm_id=user["farm_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": template_id}
