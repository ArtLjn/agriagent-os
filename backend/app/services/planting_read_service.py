"""种植作业读模型与汇总视图服务。"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased

from app.models.cycle import CropCycle
from app.models.log import FarmLog
from app.models.planting import (
    LaborEntry,
    OperationWorkOrder,
    OperationWorkOrderUnit,
    PlantingUnit,
    Worker,
)
from app.schemas.planting import (
    OperationWorkOrderResponse,
    RecentOperationResponse,
    WageSaveResponse,
    WorkerLaborSummary,
)
from app.services.labor_service import WORK_ORDER_SOURCE


def to_work_order_response(
    work_order: OperationWorkOrder,
) -> OperationWorkOrderResponse:
    """将 ORM 作业单转换为 API 响应。"""
    entries = []
    total_payable = Decimal("0")
    total_paid = Decimal("0")
    total_unpaid = Decimal("0")
    for entry in work_order.labor_entries:
        total_payable += entry.payable_amount
        total_paid += entry.paid_amount
        total_unpaid += entry.unpaid_amount
        entries.append(
            {
                "id": entry.id,
                "farm_id": entry.farm_id,
                "work_order_id": entry.work_order_id,
                "worker_id": entry.worker_id,
                "worker_name": entry.worker.name if entry.worker else None,
                "pay_type": entry.pay_type,
                "quantity": entry.quantity,
                "unit_price": entry.unit_price,
                "payable_amount": entry.payable_amount,
                "paid_amount": entry.paid_amount,
                "unpaid_amount": entry.unpaid_amount,
                "settlement_status": entry.settlement_status,
                "note": entry.note,
            }
        )
    unit_names = [link.unit.name for link in work_order.unit_links if link.unit]
    return OperationWorkOrderResponse(
        id=work_order.id,
        farm_id=work_order.farm_id,
        cycle_id=work_order.cycle_id,
        cycle_name=work_order.cycle.name if work_order.cycle else None,
        operation_type=work_order.operation_type,
        operation_date=work_order.operation_date,
        scope_type=work_order.scope_type,
        unit_ids=[link.unit_id for link in work_order.unit_links],
        unit_names=unit_names,
        note=work_order.note,
        photo_urls=work_order.photo_urls,
        labor_entries=entries,
        labor_cost_record_id=work_order.labor_cost_record_id,
        total_payable_amount=total_payable,
        total_paid_amount=total_paid,
        total_unpaid_amount=total_unpaid,
        created_at=work_order.created_at,
    )


def to_wage_response(entry: LaborEntry, cost_record_id: int | None) -> WageSaveResponse:
    """将用工记录转换为独立工资响应。"""
    work_order = entry.work_order
    return WageSaveResponse(
        id=entry.id,
        farm_id=entry.farm_id,
        work_order_id=entry.work_order_id,
        cycle_id=work_order.cycle_id if work_order else 0,
        operation_type=work_order.operation_type if work_order else "",
        worker_id=entry.worker_id,
        worker_name=entry.worker.name if entry.worker else "",
        pay_type=entry.pay_type,
        quantity=entry.quantity,
        unit_price=entry.unit_price,
        payable_amount=entry.payable_amount,
        paid_amount=entry.paid_amount,
        unpaid_amount=entry.unpaid_amount,
        settlement_status=entry.settlement_status,
        note=entry.note,
        cost_record_id=cost_record_id,
    )


def format_scope_text(work_order: OperationWorkOrder) -> str:
    """格式化作业单作用范围。"""
    if work_order.scope_type == "farm":
        return "全农场"
    if work_order.scope_type == "unit":
        names = [link.unit.name for link in work_order.unit_links if link.unit]
        return "、".join(names)
    if work_order.cycle:
        return work_order.cycle.name
    return ""


def list_recent_operations(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    days: int = 30,
    limit: int = 20,
) -> list[RecentOperationResponse]:
    """合并新作业单和旧农事日志，提供近期农事视图。"""
    start_date = date.today() - timedelta(days=days)
    work_query = db.query(OperationWorkOrder).filter(
        OperationWorkOrder.farm_id == farm_id,
        OperationWorkOrder.operation_date >= start_date,
    )
    log_query = db.query(FarmLog).filter(
        FarmLog.farm_id == farm_id,
        FarmLog.operation_date >= start_date,
    )
    if cycle_id is not None:
        work_query = work_query.filter(OperationWorkOrder.cycle_id == cycle_id)
        log_query = log_query.filter(FarmLog.cycle_id == cycle_id)

    items: list[RecentOperationResponse] = []
    for work_order in work_query.all():
        items.append(
            RecentOperationResponse(
                source_type=WORK_ORDER_SOURCE,
                source_id=work_order.id,
                cycle_id=work_order.cycle_id,
                cycle_name=work_order.cycle.name if work_order.cycle else None,
                operation_type=work_order.operation_type,
                operation_date=work_order.operation_date,
                scope_text=format_scope_text(work_order),
                note=work_order.note,
            )
        )
    for log in log_query.all():
        items.append(
            RecentOperationResponse(
                source_type="farm_log",
                source_id=log.id,
                cycle_id=log.cycle_id,
                cycle_name=log.cycle.name if getattr(log, "cycle", None) else None,
                operation_type=log.operation_type,
                operation_date=log.operation_date,
                scope_text=None,
                note=log.note,
            )
        )
    items.sort(key=lambda item: (item.operation_date, item.source_id), reverse=True)
    return items[:limit]


def list_operation_work_orders(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    cycle_name: str | None = None,
    unit_id: int | None = None,
    unit_name: str | None = None,
    operation_type: str | None = None,
    worker_name: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    payment_status: str | None = None,
    limit: int = 20,
) -> list[OperationWorkOrder]:
    """按业务条件查询农事作业单。"""
    query = db.query(OperationWorkOrder).filter(OperationWorkOrder.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(OperationWorkOrder.cycle_id == cycle_id)
    if cycle_name:
        query = query.join(CropCycle).filter(
            CropCycle.name.contains(cycle_name.strip())
        )
    if unit_id is not None:
        query = query.join(OperationWorkOrderUnit).filter(
            OperationWorkOrderUnit.unit_id == unit_id
        )
    if unit_name:
        query = (
            query.join(OperationWorkOrderUnit)
            .join(PlantingUnit)
            .filter(PlantingUnit.name.contains(unit_name.strip()))
        )
    if operation_type:
        query = query.filter(
            OperationWorkOrder.operation_type.contains(operation_type.strip())
        )
    if worker_name:
        query = (
            query.join(LaborEntry)
            .join(Worker)
            .filter(Worker.name.contains(worker_name.strip()))
        )
    if start_date is not None:
        query = query.filter(OperationWorkOrder.operation_date >= start_date)
    if end_date is not None:
        query = query.filter(OperationWorkOrder.operation_date <= end_date)
    status = (payment_status or "").strip().lower()
    if status:
        query = _apply_work_order_payment_status_filter(query, status)

    items = (
        query.distinct()
        .order_by(
            OperationWorkOrder.operation_date.desc(), OperationWorkOrder.id.desc()
        )
        .limit(limit)
        .all()
    )
    return items


def list_labor_payables(
    db: Session,
    farm_id: int,
    worker_name: str | None = None,
    cycle_id: int | None = None,
    cycle_name: str | None = None,
    work_order_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 50,
) -> list[LaborEntry]:
    """查询未付人工明细。"""
    query = (
        db.query(LaborEntry)
        .join(OperationWorkOrder, OperationWorkOrder.id == LaborEntry.work_order_id)
        .join(Worker, Worker.id == LaborEntry.worker_id)
        .filter(
            LaborEntry.farm_id == farm_id,
            LaborEntry.unpaid_amount > 0,
        )
    )
    if worker_name:
        query = query.filter(Worker.name.contains(worker_name.strip()))
    if cycle_id is not None:
        query = query.filter(OperationWorkOrder.cycle_id == cycle_id)
    if cycle_name:
        query = query.join(CropCycle).filter(
            CropCycle.name.contains(cycle_name.strip())
        )
    if work_order_id is not None:
        query = query.filter(LaborEntry.work_order_id == work_order_id)
    if start_date is not None:
        query = query.filter(OperationWorkOrder.operation_date >= start_date)
    if end_date is not None:
        query = query.filter(OperationWorkOrder.operation_date <= end_date)
    return (
        query.order_by(OperationWorkOrder.operation_date, LaborEntry.id)
        .limit(limit)
        .all()
    )


def get_unsettled_labor_summary(db: Session, farm_id: int) -> dict:
    """汇总未结人工。"""
    rows = (
        db.query(
            Worker.name, func.sum(LaborEntry.unpaid_amount), func.count(LaborEntry.id)
        )
        .join(Worker, Worker.id == LaborEntry.worker_id)
        .filter(
            LaborEntry.farm_id == farm_id,
            LaborEntry.unpaid_amount > 0,
            or_(
                LaborEntry.settlement_status == "unpaid",
                LaborEntry.settlement_status == "partial",
            ),
        )
        .group_by(Worker.name)
        .all()
    )
    total = sum((amount or Decimal("0") for _, amount, _ in rows), Decimal("0"))
    return {
        "total_unpaid": total,
        "workers": [
            {
                "worker_name": name,
                "unpaid_amount": amount or Decimal("0"),
                "entry_count": count,
            }
            for name, amount, count in rows
        ],
    }


def _apply_work_order_payment_status_filter(query, payment_status: str):
    payment_entry = aliased(LaborEntry)
    payable = func.coalesce(func.sum(payment_entry.payable_amount), 0)
    paid = func.coalesce(func.sum(payment_entry.paid_amount), 0)
    unpaid = func.coalesce(func.sum(payment_entry.unpaid_amount), 0)
    query = query.outerjoin(
        payment_entry,
        payment_entry.work_order_id == OperationWorkOrder.id,
    ).group_by(OperationWorkOrder.id)
    if payment_status in {"unpaid", "未付"}:
        return query.having(payable > 0).having(paid <= 0).having(unpaid > 0)
    if payment_status in {"partial", "partially_paid", "部分", "部分支付"}:
        return query.having(paid > 0).having(unpaid > 0)
    if payment_status in {"settled", "paid", "已付", "已结清"}:
        return query.having(payable > 0).having(unpaid <= 0)
    if payment_status in {"has_unpaid", "欠款", "未结清"}:
        return query.having(unpaid > 0)
    return query


def list_worker_labor_summaries(
    db: Session, farm_id: int, active_only: bool = False
) -> list[WorkerLaborSummary]:
    """返回工人管理页所需的全场用工摘要。"""
    worker_query = db.query(Worker).filter(Worker.farm_id == farm_id)
    if active_only:
        worker_query = worker_query.filter(Worker.status == "active")
    workers = worker_query.order_by(Worker.id).all()

    rows = (
        db.query(
            LaborEntry.worker_id,
            OperationWorkOrder.cycle_id,
            func.sum(LaborEntry.payable_amount),
            func.sum(LaborEntry.paid_amount),
            func.sum(LaborEntry.unpaid_amount),
            func.count(LaborEntry.id),
        )
        .join(OperationWorkOrder, OperationWorkOrder.id == LaborEntry.work_order_id)
        .filter(LaborEntry.farm_id == farm_id)
        .group_by(LaborEntry.worker_id, OperationWorkOrder.cycle_id)
        .all()
    )
    cycles_by_id = _get_cycle_names(db, farm_id)
    by_worker: dict[int, list[dict]] = {}
    for worker_id, cycle_id, payable, paid, unpaid, count in rows:
        by_worker.setdefault(worker_id, []).append(
            {
                "cycle_id": cycle_id,
                "cycle_name": cycles_by_id.get(cycle_id),
                "total_payable": payable or Decimal("0"),
                "total_paid": paid or Decimal("0"),
                "total_unpaid": unpaid or Decimal("0"),
                "entry_count": count,
            }
        )

    summaries: list[WorkerLaborSummary] = []
    for worker in workers:
        cycle_summaries = by_worker.get(worker.id, [])
        summaries.append(
            WorkerLaborSummary(
                id=worker.id,
                farm_id=worker.farm_id,
                name=worker.name,
                phone=worker.phone,
                default_pay_type=worker.default_pay_type,
                default_unit_price=worker.default_unit_price,
                note=worker.note,
                status=worker.status,
                created_at=worker.created_at,
                total_payable=sum(
                    (item["total_payable"] for item in cycle_summaries), Decimal("0")
                ),
                total_paid=sum(
                    (item["total_paid"] for item in cycle_summaries), Decimal("0")
                ),
                total_unpaid=sum(
                    (item["total_unpaid"] for item in cycle_summaries), Decimal("0")
                ),
                entry_count=sum(item["entry_count"] for item in cycle_summaries),
                cycle_summaries=cycle_summaries,
            )
        )
    return summaries


def _get_cycle_names(db: Session, farm_id: int) -> dict[int, str]:
    from app.models.cycle import CropCycle

    return {
        cycle_id: name
        for cycle_id, name in db.query(CropCycle.id, CropCycle.name)
        .filter(CropCycle.farm_id == farm_id)
        .all()
    }
