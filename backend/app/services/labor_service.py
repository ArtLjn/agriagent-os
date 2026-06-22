"""轻量用工和人工成本账单同步服务。"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.context.invalidation import invalidate_farm_context
from app.core.timezone import ensure_beijing_timezone  # harness-exempt: 迁移期 service 复用统一时区校验，后续下沉 shared 时间工具
from app.models.cost import CostRecord
from app.models.cost_category import CostCategory
from app.models.cycle import CropCycle
from app.models.planting import LaborEntry, OperationWorkOrder, Worker
from app.schemas.planting import LaborEntryCreate, WageSaveRequest, WageUpdateRequest
from app.services.cost_service import _find_category, settlement_status_for

LABOR_CATEGORY = "人工"
WORK_ORDER_SOURCE = "operation_work_order"
LABOR_ENTRY_SOURCE = "labor_entry"
WAGE_WORK_ORDER_SOURCE = "wage_entry"
ACTIVE_SOURCE_KEY = "active"


def build_labor_entry(
    db: Session, data: LaborEntryCreate, work_order_id: int, farm_id: int
) -> LaborEntry:
    """构建作业单用工明细。"""
    _get_worker(db, data.worker_id, farm_id)
    entry = LaborEntry(
        farm_id=farm_id,
        work_order_id=work_order_id,
        client_request_id=getattr(data, "client_request_id", None),
    )
    _apply_labor_values(entry, data, data.worker_id)
    return entry


def save_wage_entry(
    db: Session, data: WageSaveRequest, farm_id: int
) -> tuple[LaborEntry, int | None]:
    """保存独立工资记录，并同步一条唯一人工成本账单。"""
    cycle = _get_cycle(db, data.cycle_id, farm_id)
    worker = _resolve_wage_worker(db, data, farm_id)
    entry = _find_existing_wage_entry(db, data, farm_id)
    if entry is None:
        work_order = _create_wage_work_order(db, data, farm_id)
        entry = LaborEntry(
            farm_id=farm_id,
            work_order_id=work_order.id,
            worker_id=worker.id,
            client_request_id=data.client_request_id,
        )
        db.add(entry)
    else:
        work_order = entry.work_order
        if not work_order:
            raise ValueError("工资记录缺少作业上下文")
        work_order.cycle_id = data.cycle_id
        work_order.operation_type = data.operation_type
        work_order.operation_date = data.work_date
        work_order.note = data.note

    try:
        _apply_labor_values(entry, data, worker.id)
        db.flush()
        cost_record_id = sync_labor_entry_cost_record(
            db,
            entry,
            cycle.id,
            data.operation_type,
            data.work_date,
            data.recorded_at,
            data.worker_name,
            farm_id,
        )
        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(entry)
    except IntegrityError:
        db.rollback()
        existing_entry = _find_existing_wage_entry(db, data, farm_id)
        if existing_entry is None:
            raise
        return existing_entry, _get_labor_entry_cost_record_id(
            db, existing_entry, farm_id
        )
    except Exception:
        db.rollback()
        raise
    return entry, cost_record_id


def update_wage_entry(
    db: Session, labor_entry_id: int, data: WageUpdateRequest, farm_id: int
) -> tuple[LaborEntry, int | None]:
    """按工资记录 ID 更新工资和上下文，并同步人工成本账单。"""
    entry = _get_wage_entry(db, labor_entry_id, farm_id)
    work_order = entry.work_order
    if not work_order:
        raise ValueError("工资记录缺少作业上下文")

    cycle_id = data.cycle_id if data.cycle_id is not None else work_order.cycle_id
    if cycle_id is None:
        raise ValueError("工资记录必须关联种植批次")
    cycle = _get_cycle(db, cycle_id, farm_id)

    worker = _resolve_updated_wage_worker(db, data, entry.worker_id, farm_id)
    work_order.cycle_id = cycle.id
    if data.operation_type is not None:
        work_order.operation_type = data.operation_type
    if data.work_date is not None:
        work_order.operation_date = data.work_date
    if "note" in data.model_fields_set:
        work_order.note = data.note

    wage_values = _merge_wage_values(entry, data)
    _apply_labor_values(entry, wage_values, worker.id)
    db.flush()
    cost_record_id = sync_labor_entry_cost_record(
        db,
        entry,
        cycle.id,
        work_order.operation_type,
        work_order.operation_date,
        data.recorded_at,
        worker.name,
        farm_id,
    )

    try:
        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(entry)
    except Exception:
        db.rollback()
        raise
    return entry, cost_record_id


def sync_work_order_labor_cost_record(
    db: Session, work_order: OperationWorkOrder, cycle: CropCycle | None, farm_id: int
) -> None:
    """同步作业单聚合人工成本账单。"""
    total_payable = sum(
        (entry.payable_amount for entry in work_order.labor_entries),
        Decimal("0"),
    )
    total_paid = sum(
        (entry.paid_amount for entry in work_order.labor_entries),
        Decimal("0"),
    )
    settled_amount = min(total_paid, total_payable)
    existing = _get_single_source_cost_record(
        db, farm_id, WORK_ORDER_SOURCE, work_order.id
    )
    if total_payable <= 0:
        if existing:
            existing.deleted_at = datetime.now(timezone.utc)
            existing.source_active_key = None
        work_order.labor_cost_record_id = None
        db.flush()
        return
    category = _ensure_labor_category(db, farm_id)
    scope_text = _format_scope_text(work_order)
    note = f"{work_order.operation_type}人工费"
    if scope_text:
        note = f"{note}（{scope_text}）"
    record = existing or CostRecord(
        farm_id=farm_id,
        source_type=WORK_ORDER_SOURCE,
        source_id=work_order.id,
    )
    _apply_labor_cost_record(
        record=record,
        cycle_id=cycle.id if cycle else None,
        category=category,
        amount=total_payable,
        settled_amount=settled_amount,
        record_date=work_order.operation_date,
        recorded_at=None,
        note=note,
        subtype="作业单人工",
    )
    if existing is None:
        db.add(record)
    db.flush()
    work_order.labor_cost_record_id = record.id


def sync_labor_entry_cost_record(
    db: Session,
    entry: LaborEntry,
    cycle_id: int,
    operation_type: str,
    record_date,
    recorded_at,
    worker_name_hint: str | None,
    farm_id: int,
) -> int | None:
    """同步独立工资记录对应的人工成本账单。"""
    existing = _get_single_source_cost_record(db, farm_id, LABOR_ENTRY_SOURCE, entry.id)
    if entry.payable_amount <= 0:
        if existing:
            existing.deleted_at = datetime.now(timezone.utc)
            existing.source_active_key = None
            db.flush()
        return None
    category = _ensure_labor_category(db, farm_id)
    worker_name = entry.worker.name if entry.worker else worker_name_hint or "工人"
    record = existing or CostRecord(
        farm_id=farm_id,
        source_type=LABOR_ENTRY_SOURCE,
        source_id=entry.id,
    )
    record.deleted_at = None
    record.source_active_key = ACTIVE_SOURCE_KEY
    _apply_labor_cost_record(
        record=record,
        cycle_id=cycle_id,
        category=category,
        amount=entry.payable_amount,
        settled_amount=min(entry.paid_amount, entry.payable_amount),
        record_date=record_date,
        recorded_at=recorded_at,
        note=f"{worker_name}{operation_type}工资",
        subtype="工资记录人工",
    )
    if existing is None:
        db.add(record)
    db.flush()
    return record.id


def find_or_create_worker_by_name(
    db: Session,
    farm_id: int,
    name: str,
    default_unit_price: Decimal | None = None,
) -> Worker:
    """按农场和姓名复用工人，不存在时创建轻档案。"""
    worker = _find_worker_by_name(db, name, farm_id)
    if worker:
        return worker
    worker = Worker(
        farm_id=farm_id,
        name=name.strip(),
        default_pay_type="daily",
        default_unit_price=default_unit_price,
        status="active",
    )
    db.add(worker)
    db.flush()
    return worker


def _get_cycle(db: Session, cycle_id: int, farm_id: int) -> CropCycle:
    cycle = (
        db.query(CropCycle)
        .filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id)
        .first()
    )
    if not cycle:
        raise ValueError("种植批次不存在")
    return cycle


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


def _get_wage_entry(db: Session, labor_entry_id: int, farm_id: int) -> LaborEntry:
    entry = (
        db.query(LaborEntry)
        .join(OperationWorkOrder, OperationWorkOrder.id == LaborEntry.work_order_id)
        .filter(
            LaborEntry.id == labor_entry_id,
            LaborEntry.farm_id == farm_id,
            OperationWorkOrder.source_type == WAGE_WORK_ORDER_SOURCE,
        )
        .first()
    )
    if not entry:
        raise ValueError("工资记录不存在")
    return entry


def _resolve_updated_wage_worker(
    db: Session, data: WageUpdateRequest, current_worker_id: int, farm_id: int
) -> Worker:
    if data.worker_id is not None:
        return _get_worker(db, data.worker_id, farm_id)
    if data.worker_name is not None:
        return find_or_create_worker_by_name(
            db, farm_id, data.worker_name, data.unit_price
        )
    return _get_worker(db, current_worker_id, farm_id)


def _merge_wage_values(entry: LaborEntry, data: WageUpdateRequest) -> LaborEntryCreate:
    return LaborEntryCreate(
        worker_id=entry.worker_id,
        pay_type=data.pay_type if data.pay_type is not None else entry.pay_type,
        quantity=data.quantity if data.quantity is not None else entry.quantity,
        unit_price=data.unit_price if data.unit_price is not None else entry.unit_price,
        paid_amount=(
            data.paid_amount if data.paid_amount is not None else entry.paid_amount
        ),
        note=data.note if "note" in data.model_fields_set else entry.note,
    )


def _resolve_wage_worker(db: Session, data: WageSaveRequest, farm_id: int) -> Worker:
    if data.worker_id is not None:
        return _get_worker(db, data.worker_id, farm_id)
    if not data.worker_name:
        raise ValueError("必须选择或填写工人")
    return find_or_create_worker_by_name(db, farm_id, data.worker_name, data.unit_price)


def _find_existing_wage_entry(
    db: Session, data: WageSaveRequest, farm_id: int
) -> LaborEntry | None:
    return (
        db.query(LaborEntry)
        .join(OperationWorkOrder, OperationWorkOrder.id == LaborEntry.work_order_id)
        .filter(
            LaborEntry.farm_id == farm_id,
            LaborEntry.client_request_id == data.client_request_id,
            OperationWorkOrder.source_type == WAGE_WORK_ORDER_SOURCE,
        )
        .order_by(LaborEntry.id)
        .first()
    )


def _get_labor_entry_cost_record_id(
    db: Session, entry: LaborEntry, farm_id: int
) -> int | None:
    record = _get_single_source_cost_record(db, farm_id, LABOR_ENTRY_SOURCE, entry.id)
    return record.id if record else None


def _create_wage_work_order(
    db: Session, data: WageSaveRequest, farm_id: int
) -> OperationWorkOrder:
    work_order = OperationWorkOrder(
        farm_id=farm_id,
        cycle_id=data.cycle_id,
        operation_type=data.operation_type,
        operation_date=data.work_date,
        scope_type="cycle",
        note=data.note,
        source_type=WAGE_WORK_ORDER_SOURCE,
    )
    db.add(work_order)
    db.flush()
    work_order.source_id = work_order.id
    return work_order


def _apply_labor_values(
    entry: LaborEntry, data: WageSaveRequest | LaborEntryCreate, worker_id: int
) -> None:
    payable = getattr(data, "payable_amount", None) or (data.quantity * data.unit_price)
    paid = data.paid_amount
    unpaid = max(payable - paid, Decimal("0"))
    if paid <= 0:
        status = "unpaid"
    elif unpaid <= 0:
        status = "settled"
    else:
        status = "partial"
    entry.worker_id = worker_id
    entry.pay_type = data.pay_type
    entry.quantity = data.quantity
    entry.unit_price = data.unit_price
    entry.payable_amount = payable
    entry.paid_amount = paid
    entry.unpaid_amount = unpaid
    entry.settlement_status = status
    entry.note = data.note


def _get_single_source_cost_record(
    db: Session, farm_id: int, source_type: str, source_id: int
) -> CostRecord | None:
    records = (
        db.query(CostRecord)
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.source_type == source_type,
            CostRecord.source_id == source_id,
            CostRecord.deleted_at.is_(None),
        )
        .order_by(CostRecord.id)
        .all()
    )
    if len(records) > 1:
        raise ValueError("同一来源存在多条人工成本账单，请先处理重复数据")
    return records[0] if records else None


def _apply_labor_cost_record(
    record: CostRecord,
    cycle_id: int | None,
    category: CostCategory | None,
    amount: Decimal,
    settled_amount: Decimal,
    record_date,
    recorded_at,
    note: str,
    subtype: str,
) -> None:
    record.cycle_id = cycle_id
    record.record_type = "cost"
    record.category = LABOR_CATEGORY
    record.category_id = category.id if category else None
    record.category_name_snapshot = LABOR_CATEGORY
    record.amount = amount
    record.settled_amount = settled_amount
    record.settlement_status = settlement_status_for(amount, settled_amount)
    record.record_date = record_date
    if recorded_at is not None:
        record.recorded_at = ensure_beijing_timezone(recorded_at)
    record.note = note
    record.record_subtype = subtype
    record.source_active_key = ACTIVE_SOURCE_KEY


def _format_scope_text(work_order: OperationWorkOrder) -> str:
    """格式化作业单作用范围，用于人工成本备注。"""
    if work_order.scope_type == "farm":
        return "全农场"
    if work_order.scope_type == "unit":
        names = [link.unit.name for link in work_order.unit_links if link.unit]
        return "、".join(names)
    if work_order.cycle:
        return work_order.cycle.name
    return ""


def _ensure_labor_category(db: Session, farm_id: int) -> CostCategory | None:
    category = _find_category(db, farm_id, LABOR_CATEGORY, "cost")
    if category:
        return category
    category = CostCategory(
        farm_id=farm_id,
        name=LABOR_CATEGORY,
        type="cost",
        icon="users",
        sort_order=4,
        is_default=True,
    )
    db.add(category)
    db.flush()
    return category
