"""种植单元、农事作业单和轻量用工 API。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_db
from app.models.farm import Farm
from app.schemas.common import PaginatedResponse
from app.schemas.planting import (
    OperationTypeResponse,
    OperationWorkOrderCreate,
    OperationWorkOrderResponse,
    PlantingUnitCreate,
    PlantingUnitResponse,
    PlantingUnitUpdate,
    RecentOperationResponse,
    WorkerCreate,
    WorkerResponse,
    WorkerUpdate,
)
from app.services import planting_read_service, planting_service

router = APIRouter(prefix="/planting", tags=["planting"])


@router.post("/units", response_model=PlantingUnitResponse)
def create_unit(
    data: PlantingUnitCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建种植单元。"""
    try:
        return planting_service.create_unit(db, data, farm.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/units", response_model=list[PlantingUnitResponse])
def list_units(
    cycle_id: int | None = None,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """查询种植单元。"""
    return planting_service.list_units(db, farm.id, cycle_id=cycle_id)


@router.put("/units/{unit_id}", response_model=PlantingUnitResponse)
def update_unit(
    unit_id: int,
    data: PlantingUnitUpdate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """更新种植单元。"""
    try:
        return planting_service.update_unit(db, unit_id, data, farm.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/units/{unit_id}")
def delete_unit(
    unit_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """删除种植单元。"""
    try:
        planting_service.delete_unit(db, unit_id, farm.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"message": "删除成功"}


@router.post("/workers", response_model=WorkerResponse)
def create_worker(
    data: WorkerCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建工人档案。"""
    return planting_service.create_worker(db, data, farm.id)


@router.get("/workers", response_model=list[WorkerResponse])
def list_workers(
    active_only: bool = False,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """查询工人档案。"""
    return planting_service.list_workers(db, farm.id, active_only=active_only)


@router.put("/workers/{worker_id}", response_model=WorkerResponse)
def update_worker(
    worker_id: int,
    data: WorkerUpdate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """更新工人档案。"""
    try:
        return planting_service.update_worker(db, worker_id, data, farm.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/workers/{worker_id}")
def delete_worker(
    worker_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """停用工人档案。"""
    try:
        planting_service.delete_worker(db, worker_id, farm.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"message": "停用成功"}


@router.get("/operation-types", response_model=list[OperationTypeResponse])
def list_operation_types(crop_name: str | None = None):
    """查询通用或西瓜内置作业类型。"""
    return planting_service.get_operation_types(crop_name)


@router.post("/work-orders", response_model=OperationWorkOrderResponse)
def create_work_order(
    data: OperationWorkOrderCreate,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """创建农事作业单。"""
    try:
        work_order = planting_service.create_work_order(db, data, farm.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return planting_read_service.to_work_order_response(work_order)


@router.get("/work-orders", response_model=PaginatedResponse[OperationWorkOrderResponse])
def list_work_orders(
    cycle_id: int | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """查询农事作业单。"""
    skip = (page - 1) * size
    items = planting_service.list_work_orders(
        db, farm.id, cycle_id=cycle_id, skip=skip, limit=size
    )
    total = planting_service.count_work_orders(db, farm.id, cycle_id=cycle_id)
    return {
        "items": [planting_read_service.to_work_order_response(item) for item in items],
        "total": total,
    }


@router.get("/work-orders/{work_order_id}", response_model=OperationWorkOrderResponse)
def get_work_order(
    work_order_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """查询农事作业单详情。"""
    work_order = planting_service.get_work_order(db, work_order_id, farm.id)
    if not work_order:
        raise HTTPException(status_code=404, detail="作业单不存在")
    return planting_read_service.to_work_order_response(work_order)


@router.get("/recent-operations", response_model=list[RecentOperationResponse])
def list_recent_operations(
    cycle_id: int | None = None,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """查询合并新作业单和旧日志的近期农事。"""
    return planting_read_service.list_recent_operations(db, farm.id, cycle_id, days, limit)


@router.get("/labor/unsettled-summary")
def get_unsettled_labor_summary(
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
):
    """查询未结人工摘要。"""
    return planting_read_service.get_unsettled_labor_summary(db, farm.id)
