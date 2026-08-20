"""成本分类与收支记录路由。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy.orm import Session

from business.api.deps import get_current_user
from business.api.schemas import StrictRequest
from business.db import get_db
from business.services import cost_category_service, cost_service

categories_router = APIRouter(prefix="/cost-categories", tags=["costs"])
records_router = APIRouter(prefix="/cost-records", tags=["costs"])


class CreateCategoryRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=50)
    type: str = Field(pattern="^(cost|income)$")
    icon: str = Field(default="tag", max_length=50)
    sort_order: int = 0


class CreateRecordRequest(StrictRequest):
    record_type: str = Field(pattern="^(cost|income)$")
    category: str = Field(min_length=1, max_length=50)
    amount: Decimal = Field(gt=0)
    record_date: date
    cycle_id: int | None = Field(default=None, gt=0)
    settled_amount: Decimal | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)
    record_subtype: str | None = Field(default=None, max_length=50)
    counterparty: str | None = Field(default=None, max_length=100)
    due_date: date | None = None
    source_type: str | None = Field(default=None, max_length=50)
    source_id: int | None = Field(default=None, gt=0)


def _category_out(category) -> dict:
    return {
        "id": category.id,
        "farm_id": category.farm_id,
        "name": category.name,
        "type": category.type,
        "icon": category.icon,
        "sort_order": category.sort_order,
        "is_default": category.is_default,
    }


@categories_router.get("")
def list_categories(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    categories = cost_category_service.get_categories(db, farm_id=user["farm_id"])
    return {"items": [_category_out(category) for category in categories]}


@categories_router.post("", status_code=status.HTTP_201_CREATED)
def create_category(
    request: CreateCategoryRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    category = cost_category_service.create_category(
        db, farm_id=user["farm_id"], **request.model_dump()
    )
    return _category_out(category)


@categories_router.patch("/{category_id}")
@categories_router.put("/{category_id}")
def update_category(
    category_id: int,
    request: dict,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        category = cost_category_service.update_category(
            db,
            category_id=category_id,
            farm_id=user["farm_id"],
            changes=request,
        )
        return _category_out(category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@categories_router.delete("/{category_id}")
def delete_category(
    category_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        cost_category_service.delete_category(
            db, category_id=category_id, farm_id=user["farm_id"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"deleted": category_id}


@records_router.get("")
def list_records(
    cycle_id: int | None = Query(default=None),
    record_type: str | None = Query(default=None, pattern="^(cost|income)$"),
    category: str | None = Query(default=None, max_length=50),
    source_type: str | None = Query(default=None, max_length=50),
    source_id: int | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    filters = {
        "farm_id": user["farm_id"],
        "cycle_id": cycle_id,
        "record_type": record_type,
        "category": category,
        "source_type": source_type,
        "source_id": source_id,
        "date_from": date_from,
        "date_to": date_to,
    }
    items = cost_service.get_records(
        db,
        **filters,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    total = cost_service.count_records(db, **filters)
    return {"items": items, "total": total}


@records_router.post("", status_code=status.HTTP_201_CREATED)
def create_record(
    request: CreateRecordRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return cost_service.create_record(
            db, farm_id=user["farm_id"], **request.model_dump()
        )
    except cost_service.DuplicateSourceRecordError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@records_router.get("/summary/yearly")
def yearly_summary(
    year: int = Query(ge=2000, le=2100),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return cost_service.get_yearly_summary(db, farm_id=user["farm_id"], year=year)


@records_router.get("/cycles/{cycle_id}/profit")
def cycle_profit(
    cycle_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return cost_service.get_cycle_profit(db, farm_id=user["farm_id"], cycle_id=cycle_id)


@records_router.patch("/{record_id}")
@records_router.put("/{record_id}")
def update_record(
    record_id: int,
    request: dict,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = cost_service.update_record(
        db,
        farm_id=user["farm_id"],
        record_id=record_id,
        changes=request,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="记录不存在或已删除")
    return result


@records_router.delete("/{record_id}")
def delete_record(
    record_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = cost_service.delete_record(
        db, farm_id=user["farm_id"], record_id=record_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="记录不存在或已删除")
    return result
