"""种植作业读模型与汇总视图服务。"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.log import FarmLog
from app.models.planting import LaborEntry, OperationWorkOrder, Worker
from app.schemas.planting import OperationWorkOrderResponse, RecentOperationResponse
from app.services.planting_service import WORK_ORDER_SOURCE


def to_work_order_response(work_order: OperationWorkOrder) -> OperationWorkOrderResponse:
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


def get_unsettled_labor_summary(db: Session, farm_id: int) -> dict:
    """汇总未结人工。"""
    rows = (
        db.query(Worker.name, func.sum(LaborEntry.unpaid_amount), func.count(LaborEntry.id))
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
