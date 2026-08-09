"""农场仪表板聚合查询。"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from business.api.deps import get_current_user
from business.db import get_db
from business.services import (
    cost_service,
    cycle_service,
    farm_service,
    recent_operation_service,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(user: dict = Depends(get_current_user)) -> dict:
    return farm_service.build_summary(user["farm_id"])


@router.get("/recent-operations")
def recent_operations(
    cycle_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=50),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    items = recent_operation_service.list_recent_operations(
        db,
        farm_id=user["farm_id"],
        cycle_id=cycle_id,
        days=days,
        limit=limit,
    )
    return {"items": items}


@router.get("/cost-summary")
def cost_summary(
    year: int = Query(default_factory=lambda: date.today().year, ge=2000, le=2100),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return cost_service.get_yearly_summary(db, farm_id=user["farm_id"], year=year)


@router.get("/active-cycles")
def active_cycles(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    cycles = cycle_service.get_crop_cycles(
        db,
        farm_id=user["farm_id"],
        status="active",
        skip=0,
        limit=20,
    )
    return {"items": cycles}


@router.get("/unsettled-labor")
def unsettled_labor(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return recent_operation_service.get_unsettled_labor_summary(
        db, farm_id=user["farm_id"]
    )
