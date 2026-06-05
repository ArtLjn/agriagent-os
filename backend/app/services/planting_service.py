"""种植单元、农事作业单和工人档案服务。"""

from decimal import Decimal

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
    OperationWorkOrderUpdate,
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


def update_work_order(
    db: Session,
    work_order_id: int,
    data: OperationWorkOrderUpdate,
    farm_id: int,
) -> OperationWorkOrder:
    """更新作业单和可选用工明细。"""
    work_order = _get_work_order_or_raise(db, work_order_id, farm_id)
    cycle_id = data.cycle_id if data.cycle_id is not None else work_order.cycle_id
    scope_type = data.scope_type if data.scope_type is not None else work_order.scope_type
    unit_ids = data.unit_ids if data.unit_ids is not None else [
        link.unit_id for link in work_order.unit_links
    ]
    validation_data = OperationWorkOrderCreate(
        cycle_id=cycle_id,
        operation_type=data.operation_type or work_order.operation_type,
        operation_date=data.operation_date or work_order.operation_date,
        scope_type=scope_type,
        unit_ids=unit_ids,
        note=data.note if "note" in data.model_fields_set else work_order.note,
        photo_urls=(
            data.photo_urls
            if "photo_urls" in data.model_fields_set
            else work_order.photo_urls
        ),
        labor_entries=data.labor_entries or [],
    )
    cycle = _validate_work_order_scope(db, validation_data, farm_id)

    if data.cycle_id is not None:
        work_order.cycle_id = data.cycle_id
    if data.operation_type is not None:
        work_order.operation_type = data.operation_type
    if data.operation_date is not None:
        work_order.operation_date = data.operation_date
    if data.scope_type is not None:
        work_order.scope_type = data.scope_type
    if "note" in data.model_fields_set:
        work_order.note = data.note
    if "photo_urls" in data.model_fields_set:
        work_order.photo_urls = data.photo_urls
    if data.unit_ids is not None:
        _replace_work_order_units(db, work_order, data.unit_ids)
    if data.labor_entries is not None:
        _replace_work_order_labor_entries(db, work_order, data.labor_entries, farm_id)

    db.flush()
    if data.labor_entries is not None:
        db.expire(work_order, ["labor_entries"])
    labor_service.sync_work_order_labor_cost_record(db, work_order, cycle, farm_id)
    try:
        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(work_order)
    except Exception:
        db.rollback()
        raise
    return work_order


def settle_labor_payment(
    db: Session,
    farm_id: int,
    amount: Decimal | None = None,
    worker_name: str | None = None,
    cycle_id: int | None = None,
    work_order_id: int | None = None,
    start_date=None,
    end_date=None,
) -> dict:
    """按筛选条件结算未付人工，amount 为空时全额结算。"""
    from app.services import planting_read_service

    entries = planting_read_service.list_labor_payables(
        db,
        farm_id=farm_id,
        worker_name=worker_name,
        cycle_id=cycle_id,
        work_order_id=work_order_id,
        start_date=start_date,
        end_date=end_date,
    )
    if not entries:
        raise ValueError("未找到可结算的未付人工")

    total_unpaid = sum((entry.unpaid_amount for entry in entries), Decimal("0"))
    remaining = total_unpaid if amount is None else _quantize_money(amount)
    if remaining <= 0:
        raise ValueError("结算金额必须大于 0")
    affected = []
    paid_total = Decimal("0")
    for entry in entries:
        if remaining <= 0:
            break
        pay_amount = min(entry.unpaid_amount, remaining)
        entry.paid_amount = _quantize_money(entry.paid_amount + pay_amount)
        entry.unpaid_amount = _quantize_money(max(entry.payable_amount - entry.paid_amount, Decimal("0")))
        entry.settlement_status = _settlement_status(entry.paid_amount, entry.unpaid_amount)
        remaining -= pay_amount
        paid_total += pay_amount
        affected.append(
            {
                "entry_id": entry.id,
                "work_order_id": entry.work_order_id,
                "worker_name": entry.worker.name if entry.worker else "",
                "paid_amount": _quantize_money(pay_amount),
                "remaining_unpaid": entry.unpaid_amount,
            }
        )

    db.flush()
    for entry in entries:
        if entry.work_order:
            labor_service.sync_work_order_labor_cost_record(
                db, entry.work_order, entry.work_order.cycle, farm_id
            )
    try:
        db.commit()
        invalidate_farm_context(farm_id)
    except Exception:
        db.rollback()
        raise
    return {
        "paid_amount": _quantize_money(paid_total),
        "total_unpaid_before": _quantize_money(total_unpaid),
        "remaining_unpaid": _quantize_money(total_unpaid - paid_total),
        "affected_entries": affected,
    }


def _get_work_order_or_raise(
    db: Session, work_order_id: int, farm_id: int
) -> OperationWorkOrder:
    work_order = get_work_order(db, work_order_id, farm_id)
    if not work_order:
        raise ValueError("农事作业单不存在")
    return work_order


def _replace_work_order_units(
    db: Session, work_order: OperationWorkOrder, unit_ids: list[int]
) -> None:
    for link in list(work_order.unit_links):
        db.delete(link)
    db.flush()
    for unit_id in unit_ids:
        db.add(OperationWorkOrderUnit(work_order_id=work_order.id, unit_id=unit_id))


def _replace_work_order_labor_entries(
    db: Session,
    work_order: OperationWorkOrder,
    labor_entries,
    farm_id: int,
) -> None:
    for entry in list(work_order.labor_entries):
        db.delete(entry)
    db.flush()
    work_order.labor_entries = []
    for data in labor_entries:
        entry = labor_service.build_labor_entry(db, data, work_order.id, farm_id)
        db.add(entry)
        work_order.labor_entries.append(entry)
    db.flush()


def _quantize_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _settlement_status(paid: Decimal, unpaid: Decimal) -> str:
    if paid <= 0:
        return "unpaid"
    if unpaid <= 0:
        return "settled"
    return "partial"
