"""工人档案与用工摘要路由。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy.orm import Session

from business.api.deps import get_current_user
from business.api.schemas import StrictRequest
from business.db import get_db
from business.services import recent_operation_service, worker_service

router = APIRouter(prefix="/workers", tags=["workers"])


class CreateWorkerRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    default_pay_type: str = Field(
        default="daily", pattern="^(daily|hourly|monthly|piece)$"
    )
    default_unit_price: Decimal | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)


class UpdateWorkerRequest(StrictRequest):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    default_pay_type: str | None = Field(
        default=None, pattern="^(daily|hourly|monthly|piece)$"
    )
    default_unit_price: Decimal | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")


@router.get("/summary")
def list_worker_summaries(
    active_only: bool = Query(default=False),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    items = recent_operation_service.list_worker_labor_summaries(
        db, farm_id=user["farm_id"], active_only=active_only
    )
    return {"items": items, "total": len(items)}


@router.get("")
def list_workers(
    active_only: bool = Query(default=False),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    items = worker_service.list_workers(
        db, farm_id=user["farm_id"], active_only=active_only
    )
    return {"items": items, "total": len(items)}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_worker(
    request: CreateWorkerRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return worker_service.create_worker(
            db, farm_id=user["farm_id"], **request.model_dump()
        )
    except worker_service.WorkerIdentityError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc), "meta": exc.meta},
        ) from exc


@router.get("/{worker_id}")
def get_worker(
    worker_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = worker_service.get_worker(db, worker_id, farm_id=user["farm_id"])
    if result is None:
        raise HTTPException(status_code=404, detail="工人不存在")
    return result


@router.patch("/{worker_id}")
@router.put("/{worker_id}")
def update_worker(
    worker_id: int,
    request: UpdateWorkerRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return worker_service.update_worker(
            db,
            worker_id,
            farm_id=user["farm_id"],
            **request.model_dump(exclude_unset=True),
        )
    except worker_service.WorkerIdentityError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc), "meta": exc.meta},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{worker_id}")
def delete_worker(
    worker_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return worker_service.delete_worker(db, worker_id, farm_id=user["farm_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
