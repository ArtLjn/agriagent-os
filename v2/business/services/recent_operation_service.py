"""种植作业读模型与汇总视图 Service（从 archive planting/read_service.py 复用）。

提供：
  - list_recent_operations：合并新作业单和旧农事日志的近期农事视图
  - list_operation_work_orders：按业务条件查询作业单（返回 dict）
  - list_labor_payables：查询未付人工明细（返回 ORM LaborEntry，供 settle_labor_payment 改写）
  - get_unsettled_labor_summary：汇总未结人工按工人分组
  - list_worker_labor_summaries：工人管理页用工摘要（含按茬口分组）
  - format_scope_text / _get_cycle_names / _apply_work_order_payment_status_filter 辅助

改造点（相比 archive）：
  - 导入改为 business.models / business.services.cost_service（WORK_ORDER_SOURCE）
  - 去掉 Response schema，返回 dict；Decimal → float
  - list_operation_work_orders 用 work_order_service._work_order_to_dict 序列化
  - list_labor_payables 保留返回 ORM LaborEntry（供 settle_labor_payment 直接改写 paid_amount 等字段，
    避免先转 dict 再回查 ORM 的无谓往返）
  - 保留 db: Session 第一参数
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased

from business.models import (
    CropCycle,
    FarmLog,
    LaborEntry,
    OperationWorkOrder,
    OperationWorkOrderUnit,
    PlantingUnit,
    Worker,
)
from business.services.cost_service import WORK_ORDER_SOURCE
from business.services.work_order_service import _work_order_to_dict

logger = logging.getLogger(__name__)


def format_scope_text(work_order: OperationWorkOrder) -> str:
    """格式化作业单作用范围（farm→全农场；unit→单元名拼接；cycle→批次名）。"""
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
) -> list[dict[str, Any]]:
    """合并新作业单和旧农事日志，提供近期农事视图。

    旧 FarmLog 是 v1 时代的农事记录，新作业单是 v2 的工单 + 用工 + 成本联动模型。
    两者合并按 operation_date 倒序返回，方便首页时间线展示。
    """
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

    items: list[dict[str, Any]] = []
    for work_order in work_query.all():
        items.append(
            {
                "source_type": WORK_ORDER_SOURCE,
                "source_id": work_order.id,
                "cycle_id": work_order.cycle_id,
                "cycle_name": work_order.cycle.name if work_order.cycle else None,
                "operation_type": work_order.operation_type,
                "operation_date": work_order.operation_date.isoformat()
                if work_order.operation_date
                else None,
                "scope_text": format_scope_text(work_order),
                "note": work_order.note,
            }
        )
    for log in log_query.all():
        items.append(
            {
                "source_type": "farm_log",
                "source_id": log.id,
                "cycle_id": log.cycle_id,
                "cycle_name": log.cycle.name if getattr(log, "cycle", None) else None,
                "operation_type": log.operation_type,
                "operation_date": log.operation_date.isoformat()
                if log.operation_date
                else None,
                "scope_text": None,
                "note": log.note,
            }
        )
    items.sort(
        key=lambda item: (item["operation_date"] or "", item["source_id"]),
        reverse=True,
    )
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
) -> list[dict[str, Any]]:
    """按业务条件查询农事作业单，返回 dict 列表。"""
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
            OperationWorkOrder.operation_date.desc(),
            OperationWorkOrder.id.desc(),
        )
        .limit(limit)
        .all()
    )
    return [_work_order_to_dict(w) for w in items]


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
    """查询未付人工明细，返回 ORM LaborEntry 列表（供 settle_labor_payment 直接改写）。

    注意：本函数刻意返回 ORM 而非 dict，因为 settle_labor_payment 需要直接修改
    entry.paid_amount / unpaid_amount / settlement_status 后 flush。转 dict 再回查
    会引入无谓的往返且破坏原子性。
    """
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


def get_unsettled_labor_summary(db: Session, farm_id: int) -> dict[str, Any]:
    """汇总未结人工，按工人分组返回未付总额和条目数。"""
    rows = (
        db.query(
            Worker.name,
            func.sum(LaborEntry.unpaid_amount),
            func.count(LaborEntry.id),
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
        "total_unpaid": float(total),
        "workers": [
            {
                "worker_name": name,
                "unpaid_amount": float(amount or Decimal("0")),
                "entry_count": count,
            }
            for name, amount, count in rows
        ],
    }


def list_worker_labor_summaries(
    db: Session, farm_id: int, active_only: bool = False
) -> list[dict[str, Any]]:
    """返回工人管理页所需的全场用工摘要（含按茬口分组）。"""
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
    by_worker: dict[int, list[dict[str, Any]]] = {}
    for worker_id, cycle_id, payable, paid, unpaid, count in rows:
        by_worker.setdefault(worker_id, []).append(
            {
                "cycle_id": cycle_id,
                "cycle_name": cycles_by_id.get(cycle_id),
                "total_payable": float(payable or Decimal("0")),
                "total_paid": float(paid or Decimal("0")),
                "total_unpaid": float(unpaid or Decimal("0")),
                "entry_count": count,
            }
        )

    summaries: list[dict[str, Any]] = []
    for worker in workers:
        cycle_summaries = by_worker.get(worker.id, [])
        total_payable = sum(
            (Decimal(str(item["total_payable"])) for item in cycle_summaries),
            Decimal("0"),
        )
        total_paid = sum(
            (Decimal(str(item["total_paid"])) for item in cycle_summaries),
            Decimal("0"),
        )
        total_unpaid = sum(
            (Decimal(str(item["total_unpaid"])) for item in cycle_summaries),
            Decimal("0"),
        )
        entry_count = sum(item["entry_count"] for item in cycle_summaries)
        summaries.append(
            {
                "id": worker.id,
                "farm_id": worker.farm_id,
                "name": worker.name,
                "phone": worker.phone,
                "default_pay_type": worker.default_pay_type,
                "default_unit_price": float(worker.default_unit_price)
                if worker.default_unit_price is not None
                else None,
                "note": worker.note,
                "status": worker.status,
                "created_at": worker.created_at.isoformat()
                if worker.created_at
                else None,
                "total_payable": float(total_payable),
                "total_paid": float(total_paid),
                "total_unpaid": float(total_unpaid),
                "entry_count": entry_count,
                "cycle_summaries": cycle_summaries,
            }
        )
    return summaries


def _apply_work_order_payment_status_filter(query, payment_status: str):
    """按结算状态过滤作业单（基于用工明细聚合 having）。

    支持中英文：unpaid/未付、partial/部分、settled/paid/已付、has_unpaid/欠款。
    通过 outerjoin + group_by + having 实现，避免子查询。
    """
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


def _get_cycle_names(db: Session, farm_id: int) -> dict[int, str]:
    """查询农场下所有茬口 id→name 映射，用于用工摘要回填茬口名。"""
    return {
        cycle_id: name
        for cycle_id, name in db.query(CropCycle.id, CropCycle.name)
        .filter(CropCycle.farm_id == farm_id)
        .all()
    }


__all__ = [
    "list_recent_operations",
    "list_operation_work_orders",
    "list_labor_payables",
    "get_unsettled_labor_summary",
    "list_worker_labor_summaries",
    "format_scope_text",
]
