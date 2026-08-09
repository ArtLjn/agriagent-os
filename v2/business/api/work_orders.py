"""工单、种植单元和人工工资路由。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from business.api.deps import get_current_user
from business.api.schemas import StrictRequest
from business.db import get_db
from business.services import (
    labor_service,
    operation_type_service,
    recent_operation_service,
    work_order_service,
)

router = APIRouter(prefix="/work-orders", tags=["work-orders"])
operations_router = APIRouter(tags=["planting"])


class LaborEntryRequest(StrictRequest):
    worker_id: int | None = Field(default=None, gt=0)
    worker_name: str | None = Field(default=None, min_length=1, max_length=100)
    pay_type: str = Field(default="daily", max_length=20)
    quantity: Decimal = Field(default=Decimal("1"), ge=0)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    payable_amount: Decimal | None = Field(default=None, ge=0)
    paid_amount: Decimal = Field(default=Decimal("0"), ge=0)
    note: str | None = Field(default=None, max_length=500)
    client_request_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_worker(self):
        if self.worker_id is None and not self.worker_name:
            raise ValueError("worker_id 和 worker_name 至少提供一个")
        return self


class CreateWorkOrderRequest(StrictRequest):
    operation_type: str = Field(min_length=1, max_length=50)
    operation_date: date
    cycle_id: int | None = Field(default=None, gt=0)
    scope_type: str = Field(default="cycle", pattern="^(cycle|unit|farm)$")
    unit_ids: list[int] = Field(default_factory=list)
    labor_entries: list[LaborEntryRequest] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=500)
    photo_urls: str | None = Field(default=None, max_length=2000)


class UpdateWorkOrderRequest(StrictRequest):
    operation_type: str | None = Field(default=None, min_length=1, max_length=50)
    operation_date: date | None = None
    cycle_id: int | None = Field(default=None, gt=0)
    scope_type: str | None = Field(default=None, pattern="^(cycle|unit|farm)$")
    unit_ids: list[int] | None = None
    labor_entries: list[LaborEntryRequest] | None = None
    note: str | None = Field(default=None, max_length=500)
    photo_urls: str | None = Field(default=None, max_length=2000)


class SettleLaborRequest(StrictRequest):
    amount: Decimal | None = Field(default=None, gt=0)
    worker_name: str | None = Field(default=None, max_length=100)
    cycle_id: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    end_date: date | None = None


class CreateUnitRequest(StrictRequest):
    cycle_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    area_mu: Decimal | None = Field(default=None, gt=0)
    planted_date: date | None = None
    status: str = Field(default="active", pattern="^(active|inactive)$")
    note: str | None = Field(default=None, max_length=500)


class UpdateUnitRequest(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    area_mu: Decimal | None = Field(default=None, gt=0)
    planted_date: date | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")
    note: str | None = Field(default=None, max_length=500)


class WageRequest(LaborEntryRequest):
    cycle_id: int = Field(gt=0)
    operation_type: str = Field(min_length=1, max_length=50)
    work_date: date


class UpdateWageRequest(StrictRequest):
    worker_id: int | None = Field(default=None, gt=0)
    worker_name: str | None = Field(default=None, min_length=1, max_length=100)
    cycle_id: int | None = Field(default=None, gt=0)
    operation_type: str | None = Field(default=None, min_length=1, max_length=50)
    work_date: date | None = None
    pay_type: str | None = Field(default=None, max_length=20)
    quantity: Decimal | None = Field(default=None, ge=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    payable_amount: Decimal | None = Field(default=None, ge=0)
    paid_amount: Decimal | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)


@router.get("")
def list_work_orders(
    cycle_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    items = work_order_service.list_work_orders(
        db,
        farm_id=user["farm_id"],
        cycle_id=cycle_id,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    total = work_order_service.count_work_orders(
        db, farm_id=user["farm_id"], cycle_id=cycle_id
    )
    return {"items": items, "total": total}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_work_order(
    request: CreateWorkOrderRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    payload = request.model_dump()
    payload["labor_entries"] = [entry.model_dump() for entry in request.labor_entries]
    try:
        return work_order_service.create_work_order(
            db, farm_id=user["farm_id"], **payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{order_id}")
def get_work_order(
    order_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = work_order_service.get_work_order(db, order_id, farm_id=user["farm_id"])
    if result is None:
        raise HTTPException(status_code=404, detail="工单不存在")
    return result


@router.patch("/{order_id}")
@router.put("/{order_id}")
def update_work_order(
    order_id: int,
    request: UpdateWorkOrderRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    changes = request.model_dump(exclude_unset=True)
    if request.labor_entries is not None:
        changes["labor_entries"] = [
            entry.model_dump() for entry in request.labor_entries
        ]
    try:
        return work_order_service.update_work_order(
            db, order_id, farm_id=user["farm_id"], **changes
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{order_id}/settle")
def settle_work_order_labor(
    order_id: int,
    request: SettleLaborRequest | None = None,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    filters = request.model_dump(exclude_none=True) if request else {}
    try:
        return work_order_service.settle_labor_payment(
            db,
            farm_id=user["farm_id"],
            work_order_id=order_id,
            **filters,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@operations_router.get("/planting-units")
def list_units(
    cycle_id: int | None = Query(default=None),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    items = work_order_service.list_units(
        db, farm_id=user["farm_id"], cycle_id=cycle_id
    )
    return {"items": items, "total": len(items)}


@operations_router.post("/planting-units", status_code=status.HTTP_201_CREATED)
def create_unit(
    request: CreateUnitRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return work_order_service.create_unit(
            db, farm_id=user["farm_id"], **request.model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@operations_router.patch("/planting-units/{unit_id}")
@operations_router.put("/planting-units/{unit_id}")
def update_unit(
    unit_id: int,
    request: UpdateUnitRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return work_order_service.update_unit(
            db,
            unit_id,
            farm_id=user["farm_id"],
            **request.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@operations_router.delete("/planting-units/{unit_id}")
def delete_unit(
    unit_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return work_order_service.delete_unit(db, unit_id, farm_id=user["farm_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@operations_router.post("/labor/wages", status_code=status.HTTP_201_CREATED)
def save_wage(
    request: WageRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return labor_service.save_wage_entry(
            db, request.model_dump(), farm_id=user["farm_id"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@operations_router.patch("/labor/wages/{labor_entry_id}")
def update_wage(
    labor_entry_id: int,
    request: UpdateWageRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return labor_service.update_wage_entry(
            db,
            labor_entry_id,
            request.model_dump(exclude_unset=True),
            farm_id=user["farm_id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@operations_router.get("/labor/unsettled-summary")
def unsettled_labor_summary(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return recent_operation_service.get_unsettled_labor_summary(
        db, farm_id=user["farm_id"]
    )


@operations_router.get("/recent-operations")
def recent_operations(
    cycle_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
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


@operations_router.get("/operation-types")
def operation_types(
    crop_name: str | None = Query(default=None, max_length=100),
    _user: dict = Depends(get_current_user),
) -> dict:
    return {"items": operation_type_service.get_operation_types(crop_name)}
