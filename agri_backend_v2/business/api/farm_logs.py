"""农事日志 CRUD 路由。"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy.orm import Session

from business.api.deps import get_current_user
from business.api.schemas import StrictRequest
from business.db import get_db
from business.services import log_service, operation_type_service, worker_service

router = APIRouter(prefix="/farm-logs", tags=["farm-logs"])


class CreateLogRequest(StrictRequest):
    cycle_id: int = Field(gt=0)
    operation_type: str = Field(min_length=1, max_length=50)
    operation_date: date | None = None
    note: str | None = Field(default=None, max_length=500)
    worker_ids: list[int] | None = Field(default=None, max_length=100)
    worker_names: list[str] | None = Field(default=None, max_length=100)


class UpdateLogRequest(StrictRequest):
    cycle_id: int | None = Field(default=None, gt=0)
    operation_type: str | None = Field(default=None, min_length=1, max_length=50)
    operation_date: date | None = None
    note: str | None = Field(default=None, max_length=500)
    worker_ids: list[int] | None = Field(default=None, max_length=100)
    worker_names: list[str] | None = Field(default=None, max_length=100)


@router.get("/operations/types")
def list_operation_types(
    crop_name: str | None = Query(default=None, max_length=100),
    _user: dict = Depends(get_current_user),
) -> dict:
    return {"items": operation_type_service.get_operation_types(crop_name=crop_name)}


@router.get("")
def list_logs(
    cycle_id: int | None = Query(default=None),
    operation_type: str | None = Query(default=None, max_length=50),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> dict:
    result = log_service.query_logs(
        farm_id=user["farm_id"],
        cycle_id=cycle_id,
        operation_type=operation_type,
        start_date=start_date,
        end_date=end_date,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    total = log_service.count_logs(
        farm_id=user["farm_id"],
        cycle_id=cycle_id,
        operation_type=operation_type,
        start_date=start_date,
        end_date=end_date,
    )
    return {"items": result["logs"], "total": total}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_log(
    request: CreateLogRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return log_service.create_log(
            farm_id=user["farm_id"],
            cycle_id=request.cycle_id,
            operation_type=request.operation_type,
            operation_date=(
                request.operation_date.isoformat() if request.operation_date else None
            ),
            note=request.note,
            worker_ids=request.worker_ids,
            worker_names=request.worker_names,
        )
    except worker_service.WorkerIdentityError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc), "meta": exc.meta},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{log_id}")
def get_log(
    log_id: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = log_service.get_log(db, farm_id=user["farm_id"], log_id=log_id)
    if result is None:
        raise HTTPException(status_code=404, detail="日志不存在")
    return result


@router.patch("/{log_id}")
@router.put("/{log_id}")
def update_log(
    log_id: int,
    request: UpdateLogRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    changes = request.model_dump(exclude_unset=True)
    if "operation_date" in changes and changes["operation_date"] is not None:
        changes["operation_date"] = changes["operation_date"].isoformat()
    try:
        return log_service.update_log(farm_id=user["farm_id"], log_id=log_id, **changes)
    except worker_service.WorkerIdentityError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc), "meta": exc.meta},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{log_id}")
def delete_log(
    log_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return log_service.delete_log(farm_id=user["farm_id"], log_id=log_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
