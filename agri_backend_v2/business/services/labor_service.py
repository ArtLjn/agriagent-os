"""轻量用工和人工成本账单同步 Service（从 archive planting/labor_service.py 复用）。

提供：
  - build_labor_entry：构建作业单用工明细（ORM，供 work_order_service 内部 add）
  - save_wage_entry / update_wage_entry：独立工资记录 CRUD，同步人工成本账单
  - sync_work_order_labor_cost_record：聚合作业单所有用工为单条人工成本账单
  - sync_labor_entry_cost_record：单条工资记录对应的人工成本账单
  - 内部辅助：_get_cycle / _get_wage_entry / _resolve_wage_worker / _find_existing_wage_entry /
    _get_labor_entry_cost_record_id / _create_wage_work_order / _apply_labor_values /
    _get_single_source_cost_record / _apply_labor_cost_record / _format_scope_text /
    _ensure_labor_category
  - _labor_entry_to_dict：LaborEntry 序列化（供 work_order_service 复用）

改造点（相比 archive）：
  - 导入改为 business.models / business.context_runtime / shared.time
  - cost_service 常量和函数从 business.services.cost_service 导入（并行依赖，
    若 ImportError 说明 cost_service 未就绪，最终统一自检）
  - _get_worker / resolve_worker_by_name 从 worker_service 导入
  - WageSaveRequest / WageUpdateRequest / LaborEntryCreate 改为 dict 参数
  - db.commit() 改 db.flush()（IntegrityError 恢复路径保留 db.rollback() 以清理 session 重试）
  - save_wage_entry / update_wage_entry 返回 tuple[dict, int|None]（dict 替代 ORM）
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session

from business.context_runtime import invalidate_farm_context
from business.models import (
    CostCategory,
    CostRecord,
    CropCycle,
    LaborEntry,
    OperationWorkOrder,
    Worker,
)
from business.services.cost_service import (
    ACTIVE_SOURCE_KEY,
    LABOR_CATEGORY,
    LABOR_ENTRY_SOURCE,
    WORK_ORDER_SOURCE,
    _find_category,
    settlement_status_for,
)
from business.services.worker_service import (
    _get_worker,
    resolve_worker_by_name,
)
from shared.time import ensure_beijing_timezone

logger = logging.getLogger(__name__)

# 独立工资记录的作业单 source_type，与普通作业单区分以便查询时过滤。
WAGE_WORK_ORDER_SOURCE = "wage_entry"


def _to_decimal(value: Any, default: Decimal | None = None) -> Decimal:
    """将 dict 中的数值字段规范化为 Decimal（兼容 float/int/str/Decimal）。"""
    if value is None or value == "":
        return default if default is not None else Decimal("0")
    return Decimal(str(value))


def _labor_entry_to_dict(entry: LaborEntry) -> dict[str, Any]:
    """ORM LaborEntry → dict（Decimal 转 float，便于 JSON 序列化）。"""
    return {
        "id": entry.id,
        "farm_id": entry.farm_id,
        "work_order_id": entry.work_order_id,
        "worker_id": entry.worker_id,
        "worker_name": entry.worker.name if entry.worker else None,
        "pay_type": entry.pay_type,
        "quantity": float(entry.quantity) if entry.quantity is not None else None,
        "unit_price": float(entry.unit_price) if entry.unit_price is not None else None,
        "payable_amount": float(entry.payable_amount)
        if entry.payable_amount is not None
        else None,
        "paid_amount": float(entry.paid_amount)
        if entry.paid_amount is not None
        else None,
        "unpaid_amount": float(entry.unpaid_amount)
        if entry.unpaid_amount is not None
        else None,
        "settlement_status": entry.settlement_status,
        "note": entry.note,
    }


def _wage_entry_to_dict(
    entry: LaborEntry, cost_record_id: int | None
) -> dict[str, Any]:
    """工资记录 → dict（在 _labor_entry_to_dict 基础上补 cycle_id/operation_type/cost_record_id）。"""
    result = _labor_entry_to_dict(entry)
    work_order = entry.work_order
    result.update(
        {
            "cycle_id": work_order.cycle_id if work_order else 0,
            "operation_type": work_order.operation_type if work_order else "",
            "cost_record_id": cost_record_id,
        }
    )
    return result


def build_labor_entry(
    db: Session, data: dict, work_order_id: int, farm_id: int
) -> LaborEntry:
    """构建作业单用工明细（返回 ORM LaborEntry，供 work_order_service 加入 session）。

    data 字段：worker_id / worker_name / pay_type / quantity / unit_price /
    paid_amount / payable_amount（可选，缺省按 quantity*unit_price 计算）/ note /
    client_request_id。worker_id 优先；仅在姓名能唯一匹配已有档案时兼容解析。

    unit_price / pay_type 未传时自动从工人档案 default_unit_price /
    default_pay_type 回填，避免日结工工资金额为 0。
    """
    worker_id = data.get("worker_id")
    worker_name = data.get("worker_name")
    if worker_id is not None:
        worker = _get_worker(db, int(worker_id), farm_id)
        resolved_worker_id = worker.id
    elif worker_name:
        worker = resolve_worker_by_name(db, farm_id, str(worker_name))
        resolved_worker_id = worker.id
    else:
        raise ValueError("必须选择或填写工人")

    # 从工人档案回填缺省的 unit_price / pay_type
    data = dict(data)  # 不修改调用方传入的 dict
    if data.get("unit_price") is None and worker.default_unit_price:
        data["unit_price"] = float(worker.default_unit_price)
    if data.get("pay_type") is None and worker.default_pay_type:
        data["pay_type"] = worker.default_pay_type

    entry = LaborEntry(
        farm_id=farm_id,
        work_order_id=work_order_id,
        client_request_id=data.get("client_request_id"),
    )
    _apply_labor_values(entry, data, resolved_worker_id)
    return entry


def save_wage_entry(
    db: Session, data: dict, farm_id: int
) -> tuple[dict[str, Any], int | None]:
    """保存独立工资记录，并同步一条唯一人工成本账单。

    幂等：按 client_request_id 复用既有 entry。IntegrityError 时 rollback 后重查
    （并发场景下另一事务可能已创建同 client_request_id 的 entry）。
    """
    cycle = _get_cycle(db, int(data["cycle_id"]), farm_id)
    worker = _resolve_wage_worker(db, data, farm_id)
    entry = _find_existing_wage_entry(db, data, farm_id)
    if entry is None:
        work_order = _create_wage_work_order(db, data, farm_id)
        entry = LaborEntry(
            farm_id=farm_id,
            work_order_id=work_order.id,
            worker_id=worker.id,
            client_request_id=data.get("client_request_id"),
        )
        db.add(entry)
    else:
        work_order = entry.work_order
        if not work_order:
            raise ValueError("工资记录缺少作业上下文")
        work_order.cycle_id = int(data["cycle_id"])
        work_order.operation_type = data["operation_type"]
        work_order.operation_date = data["work_date"]
        work_order.note = data.get("note")

    try:
        _apply_labor_values(entry, data, worker.id)
        db.flush()
        cost_record_id = sync_labor_entry_cost_record(
            db,
            entry,
            cycle.id,
            data["operation_type"],
            data["work_date"],
            data.get("recorded_at"),
            data.get("worker_name"),
            farm_id,
        )
        db.flush()
        invalidate_farm_context(farm_id)
        db.refresh(entry)
    except IntegrityError:
        # 并发场景：另一事务已插入同 client_request_id 的 entry，rollback 后重查复用。
        db.rollback()
        existing_entry = _find_existing_wage_entry(db, data, farm_id)
        if existing_entry is None:
            raise
        return _wage_entry_to_dict(
            existing_entry,
            _get_labor_entry_cost_record_id(db, existing_entry, farm_id),
        )
    return _wage_entry_to_dict(entry, cost_record_id)


def update_wage_entry(
    db: Session, labor_entry_id: int, data: dict, farm_id: int
) -> tuple[dict[str, Any], int | None]:
    """按工资记录 ID 更新工资和上下文，并同步人工成本账单。

    data 字段均可选（None 表示不改；note 等 key 缺省表示不改，传 None 表示清空）。
    """
    entry = _get_wage_entry(db, labor_entry_id, farm_id)
    work_order = entry.work_order
    if not work_order:
        raise ValueError("工资记录缺少作业上下文")

    cycle_id = data.get("cycle_id")
    if cycle_id is None:
        cycle_id = work_order.cycle_id
    if cycle_id is None:
        raise ValueError("工资记录必须关联种植批次")
    cycle = _get_cycle(db, int(cycle_id), farm_id)

    worker = _resolve_wage_worker_for_update(db, data, entry.worker_id, farm_id)
    work_order.cycle_id = cycle.id
    if data.get("operation_type") is not None:
        work_order.operation_type = data["operation_type"]
    if data.get("work_date") is not None:
        work_order.operation_date = data["work_date"]
    if "note" in data:
        work_order.note = data["note"]

    merged = _merge_wage_values(entry, data)
    _apply_labor_values(entry, merged, worker.id)
    db.flush()
    cost_record_id = sync_labor_entry_cost_record(
        db,
        entry,
        cycle.id,
        work_order.operation_type,
        work_order.operation_date,
        data.get("recorded_at"),
        worker.name,
        farm_id,
    )

    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(entry)
    return _wage_entry_to_dict(entry, cost_record_id)


def sync_work_order_labor_cost_record(
    db: Session, work_order: OperationWorkOrder, cycle: CropCycle | None, farm_id: int
) -> None:
    """同步作业单聚合人工成本账单。

    聚合逻辑：把作业单下所有用工明细的 payable/paid 求和，作为单条 CostRecord
    （source_type=operation_work_order）的 amount/settled_amount。若无用工则软删除
    该账单（设 deleted_at）。这样作业单维度的人工成本始终与明细一致，避免散落多条。
    """
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
    """同步独立工资记录对应的人工成本账单（source_type=labor_entry）。

    与作业单聚合账单不同，工资记录每条对应一条 CostRecord，便于按工资条目结算。
    payable 为 0 时软删除账单。
    """
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


def _get_cycle(db: Session, cycle_id: int, farm_id: int) -> CropCycle:
    cycle = (
        db.query(CropCycle)
        .filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id)
        .first()
    )
    if not cycle:
        raise ValueError("种植批次不存在")
    return cycle


def _get_wage_entry(db: Session, labor_entry_id: int, farm_id: int) -> LaborEntry:
    """按 id 查工资记录（必须挂在 source_type=wage_entry 的作业单下）。"""
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


def _resolve_wage_worker(db: Session, data: dict, farm_id: int) -> Any:
    """save 时解析工人：worker_id 优先，否则只解析唯一姓名候选。"""
    worker_id = data.get("worker_id")
    if worker_id is not None:
        return _get_worker(db, int(worker_id), farm_id)
    worker_name = data.get("worker_name")
    if not worker_name:
        raise ValueError("必须选择或填写工人")
    return resolve_worker_by_name(db, farm_id, str(worker_name))


def _resolve_wage_worker_for_update(
    db: Session, data: dict, current_worker_id: int, farm_id: int
) -> Any:
    """update 时解析工人：worker_id 优先，其次唯一姓名，最后保持原工人。"""
    worker_id = data.get("worker_id")
    if worker_id is not None:
        return _get_worker(db, int(worker_id), farm_id)
    worker_name = data.get("worker_name")
    if worker_name:
        return resolve_worker_by_name(db, farm_id, str(worker_name))
    return _get_worker(db, current_worker_id, farm_id)


def _merge_wage_values(entry: LaborEntry, data: dict) -> dict:
    """将 entry 当前值与 update dict 合并出完整工资字段 dict（供 _apply_labor_values）。

    None 字段表示"不改"，沿用 entry 当前值；note 走 key 缺省判断（key 存在则覆盖，含 None）。
    """
    return {
        "worker_id": entry.worker_id,
        "pay_type": data["pay_type"]
        if data.get("pay_type") is not None
        else entry.pay_type,
        "quantity": data["quantity"]
        if data.get("quantity") is not None
        else entry.quantity,
        "unit_price": data["unit_price"]
        if data.get("unit_price") is not None
        else entry.unit_price,
        "paid_amount": data["paid_amount"]
        if data.get("paid_amount") is not None
        else entry.paid_amount,
        "payable_amount": data.get("payable_amount")
        if "payable_amount" in data
        else entry.payable_amount,
        "note": data["note"] if "note" in data else entry.note,
    }


def _find_existing_wage_entry(
    db: Session, data: dict, farm_id: int
) -> LaborEntry | None:
    """按 client_request_id 查既有工资记录（用于幂等去重）。"""
    client_request_id = data.get("client_request_id")
    if not client_request_id:
        return None
    return (
        db.query(LaborEntry)
        .join(OperationWorkOrder, OperationWorkOrder.id == LaborEntry.work_order_id)
        .filter(
            LaborEntry.farm_id == farm_id,
            LaborEntry.client_request_id == client_request_id,
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
    db: Session, data: dict, farm_id: int
) -> OperationWorkOrder:
    """为独立工资记录创建挂载作业单（source_type=wage_entry，自引用 source_id）。"""
    work_order = OperationWorkOrder(
        farm_id=farm_id,
        cycle_id=int(data["cycle_id"]),
        operation_type=data["operation_type"],
        operation_date=data["work_date"],
        scope_type="cycle",
        note=data.get("note"),
        source_type=WAGE_WORK_ORDER_SOURCE,
    )
    db.add(work_order)
    db.flush()
    work_order.source_id = work_order.id
    return work_order


def _apply_labor_values(entry: LaborEntry, data: dict, worker_id: int) -> None:
    """把 dict 中的工资字段写入 LaborEntry，计算 payable/paid/unpaid/status。

    payable_amount 缺省时按 quantity * unit_price 计算。结算状态按 paid/unpaid
    自动判定：全未付→unpaid，部分付→partial，全付→settled。
    """
    quantity = _to_decimal(data.get("quantity"), Decimal("1"))
    unit_price = _to_decimal(data.get("unit_price"), Decimal("0"))
    payable_raw = data.get("payable_amount")
    payable = (
        _to_decimal(payable_raw) if payable_raw is not None else quantity * unit_price
    )
    paid = _to_decimal(data.get("paid_amount"), Decimal("0"))
    unpaid = max(payable - paid, Decimal("0"))
    if paid <= 0:
        status = "unpaid"
    elif unpaid <= 0:
        status = "settled"
    else:
        status = "partial"
    entry.worker_id = worker_id
    entry.pay_type = data.get("pay_type") or "daily"
    entry.quantity = quantity
    entry.unit_price = unit_price
    entry.payable_amount = payable
    entry.paid_amount = paid
    entry.unpaid_amount = unpaid
    entry.settlement_status = status
    entry.note = data.get("note")


def _get_single_source_cost_record(
    db: Session, farm_id: int, source_type: str, source_id: int
) -> CostRecord | None:
    """按来源查唯一活动账单；多条时报错避免误覆盖。"""
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
    """把人工成本字段写入 CostRecord（不 add，由调用方决定是否新增）。"""
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
    """确保农场有人工分类，缺失则创建（与系统预设分类保持一致）。"""
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


# ── 工资查询 ──────────────────────────────────────────────


def query_wages(
    db: Session,
    farm_id: int,
    mode: str,
    worker_id: int | None = None,
    worker_name: str | None = None,
    month: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """查询工人工资汇总，三种模式。

    mode="unpaid":   查所有工人未结款汇总（settlement_status IN unpaid/partial）
    mode="monthly":  按月份查历史账单（含已结/未结），month 格式 "2026-08"
        mode="worker":   按工人+日期范围查明细，worker_id 必填；worker_name 仅兼容唯一匹配
    """
    if mode == "unpaid":
        return _query_unpaid_wages(db, farm_id)
    if mode == "monthly":
        if not month:
            raise ValueError("monthly 模式必须提供 month (YYYY-MM)")
        return _query_monthly_wages(db, farm_id, month)
    if mode == "worker":
        if worker_id is not None:
            worker = _get_worker(db, int(worker_id), farm_id)
        elif worker_name:
            worker = resolve_worker_by_name(db, farm_id, worker_name)
        else:
            raise ValueError("worker 模式必须提供 worker_id 或 worker_name")
        return _query_worker_wages(
            db, farm_id, worker.id, worker.name, start_date, end_date
        )
    raise ValueError(f"未知 query mode: {mode}，支持 unpaid/monthly/worker")


def _query_unpaid_wages(db: Session, farm_id: int) -> dict[str, Any]:
    """查所有工人未结款汇总。"""
    rows = (
        db.query(
            LaborEntry.worker_id,
            Worker.name.label("worker_name"),
            func.count(LaborEntry.id).label("entry_count"),
            func.sum(LaborEntry.payable_amount).label("total_payable"),
            func.sum(LaborEntry.paid_amount).label("total_paid"),
            func.sum(LaborEntry.unpaid_amount).label("total_unpaid"),
        )
        .join(Worker, LaborEntry.worker_id == Worker.id)
        .filter(
            LaborEntry.farm_id == farm_id,
            LaborEntry.settlement_status.in_(("unpaid", "partial")),
        )
        .group_by(LaborEntry.worker_id, Worker.name)
        .order_by(func.sum(LaborEntry.unpaid_amount).desc())
        .all()
    )
    workers = [
        {
            "worker_id": r.worker_id,
            "worker_name": r.worker_name,
            "entry_count": int(r.entry_count or 0),
            "total_payable": float(r.total_payable or 0),
            "total_paid": float(r.total_paid or 0),
            "total_unpaid": float(r.total_unpaid or 0),
        }
        for r in rows
    ]
    total_unpaid = sum(w["total_unpaid"] for w in workers)
    return {
        "mode": "unpaid",
        "summary": {
            "total_unpaid": total_unpaid,
            "worker_count": len(workers),
        },
        "workers": workers,
    }


def _query_monthly_wages(db: Session, farm_id: int, month: str) -> dict[str, Any]:
    """按月份查历史账单。"""
    try:
        year, mon = month.split("-")
        y, m = int(year), int(mon)
        m_start = date(y, m, 1)
        m_end = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    except (ValueError, IndexError):
        raise ValueError(f"month 格式应为 YYYY-MM，收到: {month!r}")

    rows = (
        db.query(
            LaborEntry.worker_id,
            Worker.name.label("worker_name"),
            func.count(LaborEntry.id).label("entry_count"),
            func.sum(LaborEntry.payable_amount).label("total_payable"),
            func.sum(LaborEntry.paid_amount).label("total_paid"),
            func.sum(LaborEntry.unpaid_amount).label("total_unpaid"),
        )
        .join(Worker, LaborEntry.worker_id == Worker.id)
        .join(
            OperationWorkOrder,
            LaborEntry.work_order_id == OperationWorkOrder.id,
        )
        .filter(
            LaborEntry.farm_id == farm_id,
            OperationWorkOrder.operation_date >= m_start,
            OperationWorkOrder.operation_date < m_end,
        )
        .group_by(LaborEntry.worker_id, Worker.name)
        .order_by(Worker.name)
        .all()
    )
    workers = [
        {
            "worker_id": r.worker_id,
            "worker_name": r.worker_name,
            "entry_count": int(r.entry_count or 0),
            "total_payable": float(r.total_payable or 0),
            "total_paid": float(r.total_paid or 0),
            "total_unpaid": float(r.total_unpaid or 0),
            "status": "settled"
            if float(r.total_unpaid or 0) == 0
            else ("partial" if float(r.total_paid or 0) > 0 else "unpaid"),
        }
        for r in rows
    ]
    return {
        "mode": "monthly",
        "month": month,
        "summary": {
            "total_payable": sum(w["total_payable"] for w in workers),
            "total_paid": sum(w["total_paid"] for w in workers),
            "total_unpaid": sum(w["total_unpaid"] for w in workers),
            "worker_count": len(workers),
        },
        "workers": workers,
    }


def _query_worker_wages(
    db: Session,
    farm_id: int,
    worker_id: int,
    worker_name: str,
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    """按工人+日期范围查明细。"""
    query = (
        db.query(LaborEntry, OperationWorkOrder)
        .join(
            OperationWorkOrder,
            LaborEntry.work_order_id == OperationWorkOrder.id,
        )
        .join(Worker, LaborEntry.worker_id == Worker.id)
        .filter(
            LaborEntry.farm_id == farm_id,
            Worker.id == worker_id,
        )
    )
    if start_date:
        query = query.filter(OperationWorkOrder.operation_date >= start_date)
    if end_date:
        query = query.filter(OperationWorkOrder.operation_date <= end_date)
    rows = query.order_by(OperationWorkOrder.operation_date.desc()).all()

    entries = [
        {
            "work_order_id": entry.work_order_id,
            "operation_type": wo.operation_type if wo else "",
            "operation_date": str(wo.operation_date)
            if wo and wo.operation_date
            else None,
            "pay_type": entry.pay_type,
            "quantity": float(entry.quantity) if entry.quantity else None,
            "unit_price": float(entry.unit_price) if entry.unit_price else None,
            "payable_amount": float(entry.payable_amount)
            if entry.payable_amount
            else 0,
            "paid_amount": float(entry.paid_amount) if entry.paid_amount else 0,
            "settlement_status": entry.settlement_status,
        }
        for entry, wo in rows
    ]
    date_range = None
    if start_date or end_date:
        date_range = f"{start_date or '…'} ~ {end_date or '…'}"
    return {
        "mode": "worker",
        "worker_name": worker_name,
        "date_range": date_range,
        "summary": {
            "entry_count": len(entries),
            "total_payable": sum(e["payable_amount"] for e in entries),
            "total_paid": sum(e["paid_amount"] for e in entries),
            "total_unpaid": sum(
                e["payable_amount"] - e["paid_amount"] for e in entries
            ),
        },
        "entries": entries,
    }


__all__ = [
    "WAGE_WORK_ORDER_SOURCE",
    "build_labor_entry",
    "save_wage_entry",
    "update_wage_entry",
    "sync_work_order_labor_cost_record",
    "sync_labor_entry_cost_record",
    "_labor_entry_to_dict",
]
