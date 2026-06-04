"""种植单元、农事作业单和工人档案服务。"""

from sqlalchemy.orm import Session

from app.context.invalidation import invalidate_farm_context
from app.models.cycle import CropCycle
from app.models.planting import (
    OperationWorkOrder,
    OperationWorkOrderUnit,
    PlantingUnit,
    Worker,
)
from app.schemas.planting import (
    OperationWorkOrderCreate,
    PlantingUnitCreate,
    PlantingUnitUpdate,
    WorkerCreate,
    WorkerUpdate,
)
from app.services import labor_service

WATERMELON_OPERATION_TYPES = [
    "定植",
    "补苗",
    "整枝打杈",
    "理蔓",
    "压蔓",
    "人工授粉",
    "留瓜/疏瓜",
    "垫瓜/翻瓜",
    "浇水",
    "冲肥",
    "打药",
    "采收",
    "装车",
]

GENERAL_OPERATION_TYPES = ["浇水", "施肥", "打药", "除草", "巡棚", "采收", "其他"]


def _get_cycle(db: Session, cycle_id: int, farm_id: int) -> CropCycle:
    cycle = (
        db.query(CropCycle)
        .filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id)
        .first()
    )
    if not cycle:
        raise ValueError("种植批次不存在")
    return cycle


def _get_unit(db: Session, unit_id: int, farm_id: int) -> PlantingUnit:
    unit = (
        db.query(PlantingUnit)
        .filter(PlantingUnit.id == unit_id, PlantingUnit.farm_id == farm_id)
        .first()
    )
    if not unit:
        raise ValueError("种植单元不存在")
    return unit


def create_unit(db: Session, data: PlantingUnitCreate, farm_id: int) -> PlantingUnit:
    """创建种植单元。"""
    _get_cycle(db, data.cycle_id, farm_id)
    unit = PlantingUnit(farm_id=farm_id, **data.model_dump())
    db.add(unit)
    try:
        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(unit)
    except Exception:
        db.rollback()
        raise
    return unit


def list_units(
    db: Session, farm_id: int, cycle_id: int | None = None
) -> list[PlantingUnit]:
    """查询种植单元。"""
    query = db.query(PlantingUnit).filter(PlantingUnit.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(PlantingUnit.cycle_id == cycle_id)
    return query.order_by(PlantingUnit.id).all()


def update_unit(
    db: Session, unit_id: int, data: PlantingUnitUpdate, farm_id: int
) -> PlantingUnit:
    """更新种植单元。"""
    unit = _get_unit(db, unit_id, farm_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(unit, field, value)
    try:
        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(unit)
    except Exception:
        db.rollback()
        raise
    return unit


def delete_unit(db: Session, unit_id: int, farm_id: int) -> None:
    """删除种植单元。"""
    unit = _get_unit(db, unit_id, farm_id)
    db.delete(unit)
    try:
        db.commit()
        invalidate_farm_context(farm_id)
    except Exception:
        db.rollback()
        raise


def create_worker(db: Session, data: WorkerCreate, farm_id: int) -> Worker:
    """创建工人档案。"""
    existing = _find_worker_by_name(db, data.name, farm_id)
    if existing:
        return existing
    worker = Worker(farm_id=farm_id, **data.model_dump())
    db.add(worker)
    try:
        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(worker)
    except Exception:
        db.rollback()
        raise
    return worker


def list_workers(db: Session, farm_id: int, active_only: bool = False) -> list[Worker]:
    """查询工人档案。"""
    query = db.query(Worker).filter(Worker.farm_id == farm_id)
    if active_only:
        query = query.filter(Worker.status == "active")
    return query.order_by(Worker.id).all()


def update_worker(
    db: Session, worker_id: int, data: WorkerUpdate, farm_id: int
) -> Worker:
    """更新工人档案。"""
    worker = _get_worker(db, worker_id, farm_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(worker, field, value)
    try:
        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(worker)
    except Exception:
        db.rollback()
        raise
    return worker


def _get_worker(db: Session, worker_id: int, farm_id: int) -> Worker:
    worker = (
        db.query(Worker)
        .filter(Worker.id == worker_id, Worker.farm_id == farm_id)
        .first()
    )
    if not worker:
        raise ValueError("工人不存在")
    return worker


def _find_worker_by_name(db: Session, name: str, farm_id: int) -> Worker | None:
    normalized = name.strip()
    return (
        db.query(Worker)
        .filter(Worker.farm_id == farm_id, Worker.name == normalized)
        .order_by(Worker.id)
        .first()
    )


def delete_worker(db: Session, worker_id: int, farm_id: int) -> None:
    """停用工人档案，保留历史用工。"""
    worker = _get_worker(db, worker_id, farm_id)
    worker.status = "inactive"
    try:
        db.commit()
        invalidate_farm_context(farm_id)
    except Exception:
        db.rollback()
        raise


def get_operation_types(crop_name: str | None = None) -> list[dict]:
    """返回内置作业类型。"""
    normalized = (crop_name or "").lower()
    is_watermelon = "西瓜" in normalized or "watermelon" in normalized
    names = WATERMELON_OPERATION_TYPES if is_watermelon else GENERAL_OPERATION_TYPES
    return [
        {
            "name": name,
            "crop": "西瓜" if is_watermelon else None,
            "is_builtin": True,
            "sort_order": index,
        }
        for index, name in enumerate(names)
    ]


def create_work_order(
    db: Session, data: OperationWorkOrderCreate, farm_id: int
) -> OperationWorkOrder:
    """创建作业单，含用工时自动生成人工成本。"""
    cycle = _validate_work_order_scope(db, data, farm_id)
    work_order = OperationWorkOrder(
        farm_id=farm_id,
        cycle_id=data.cycle_id,
        operation_type=data.operation_type,
        operation_date=data.operation_date,
        scope_type=data.scope_type,
        note=data.note,
        photo_urls=data.photo_urls,
    )
    db.add(work_order)
    db.flush()

    for unit_id in data.unit_ids:
        db.add(OperationWorkOrderUnit(work_order_id=work_order.id, unit_id=unit_id))

    for labor in data.labor_entries:
        db.add(labor_service.build_labor_entry(db, labor, work_order.id, farm_id))

    db.flush()
    labor_service.sync_work_order_labor_cost_record(db, work_order, cycle, farm_id)

    try:
        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(work_order)
    except Exception:
        db.rollback()
        raise
    return work_order


def _validate_work_order_scope(
    db: Session, data: OperationWorkOrderCreate, farm_id: int
) -> CropCycle | None:
    cycle = _get_cycle(db, data.cycle_id, farm_id) if data.cycle_id else None
    if data.scope_type not in {"cycle", "unit", "farm"}:
        raise ValueError("作业范围类型不合法")
    if data.scope_type in {"cycle", "unit"} and not cycle:
        raise ValueError("批次级或单元级作业必须关联种植批次")
    if data.scope_type == "unit" and not data.unit_ids:
        raise ValueError("单元级作业必须选择种植单元")
    if data.unit_ids:
        units = (
            db.query(PlantingUnit)
            .filter(
                PlantingUnit.farm_id == farm_id,
                PlantingUnit.id.in_(data.unit_ids),
            )
            .all()
        )
        if len(units) != len(set(data.unit_ids)):
            raise ValueError("存在不可访问的种植单元")
        if cycle and any(unit.cycle_id != cycle.id for unit in units):
            raise ValueError("种植单元不属于当前批次")
    return cycle


def list_work_orders(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[OperationWorkOrder]:
    """查询作业单。"""
    query = db.query(OperationWorkOrder).filter(OperationWorkOrder.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(OperationWorkOrder.cycle_id == cycle_id)
    return (
        query.order_by(OperationWorkOrder.operation_date.desc(), OperationWorkOrder.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_work_orders(db: Session, farm_id: int, cycle_id: int | None = None) -> int:
    """统计作业单数量。"""
    query = db.query(OperationWorkOrder).filter(OperationWorkOrder.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(OperationWorkOrder.cycle_id == cycle_id)
    return query.count()


def get_work_order(
    db: Session, work_order_id: int, farm_id: int
) -> OperationWorkOrder | None:
    """查询作业单详情。"""
    return (
        db.query(OperationWorkOrder)
        .filter(OperationWorkOrder.id == work_order_id, OperationWorkOrder.farm_id == farm_id)
        .first()
    )
