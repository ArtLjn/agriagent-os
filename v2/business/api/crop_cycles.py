"""种植茬口 CRUD 路由。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy.orm import Session

from business.api.deps import get_current_user
from business.api.schemas import StrictRequest
from business.db import get_db
from business.services import cycle_service

router = APIRouter(prefix="/crop-cycles", tags=["crop-cycles"])


class CreateCycleRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=100)
    crop_template_id: int = Field(gt=0)
    start_date: date
    field_name: str | None = Field(default=None, max_length=100)
    total_area_mu: Decimal | None = Field(default=None, gt=0)
    season: str | None = Field(default=None, max_length=50)
    batch_note: str | None = Field(default=None, max_length=500)


class UpdateCycleRequest(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    crop_template_id: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    field_name: str | None = Field(default=None, max_length=100)
    total_area_mu: Decimal | None = Field(default=None, gt=0)
    season: str | None = Field(default=None, max_length=50)
    batch_note: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern="^(active|completed|cancelled)$")


@router.get("")
def list_cycles(
    status_filter: str | None = Query(
        default=None, alias="status", pattern="^(active|completed|cancelled)$"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    items = cycle_service.get_crop_cycles(
        db,
        farm_id=user["farm_id"],
        skip=(page - 1) * page_size,
        limit=page_size,
        status=status_filter,
    )
    total = cycle_service.count_crop_cycles(
        db, farm_id=user["farm_id"], status=status_filter
    )
    return {"items": items, "total": total}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_cycle(
    request: CreateCycleRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return cycle_service.create_crop_cycle(
            db,
            farm_id=user["farm_id"],
            **request.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{cycle_id}")
def get_cycle(
    cycle_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    cycle = cycle_service.get_crop_cycle(db, cycle_id, farm_id=user["farm_id"])
    if cycle is None:
        raise HTTPException(status_code=404, detail="茬口不存在")
    return cycle


@router.patch("/{cycle_id}")
@router.put("/{cycle_id}")
def update_cycle(
    cycle_id: int,
    request: UpdateCycleRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    current = cycle_service.get_crop_cycle(db, cycle_id, farm_id=user["farm_id"])
    if current is None:
        raise HTTPException(status_code=404, detail="茬口不存在")
    changes = request.model_dump(exclude_unset=True)
    try:
        return cycle_service.update_crop_cycle(
            db,
            cycle_id,
            farm_id=user["farm_id"],
            name=changes.get("name", current["name"]),
            crop_template_id=changes.get(
                "crop_template_id", current["crop_template_id"]
            ),
            start_date=changes.get(
                "start_date", date.fromisoformat(current["start_date"])
            ),
            field_name=changes.get("field_name", current.get("field_name")),
            total_area_mu=changes.get("total_area_mu", current.get("total_area_mu")),
            season=changes.get("season", current.get("season")),
            batch_note=changes.get("batch_note", current.get("batch_note")),
            status=changes.get("status"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{cycle_id}")
def delete_cycle(
    cycle_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        cycle_service.delete_crop_cycle(db, cycle_id, farm_id=user["farm_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": cycle_id}


@router.post("/{cycle_id}/advance-stage")
def advance_cycle_stage(
    cycle_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return cycle_service.advance_stage(db, cycle_id, farm_id=user["farm_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
