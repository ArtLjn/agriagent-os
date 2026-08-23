"""农事作业单 + 种植单元 Service（从 archive planting/service.py 复用）。

提供：
  - 作业单 CRUD：create_work_order / list_work_orders / count_work_orders /
    get_work_order / update_work_order / settle_labor_payment
  - 种植单元 CRUD：create_unit / list_units / get_unit / update_unit / delete_unit
  - 内部辅助：_validate_work_order_scope / _get_work_order_or_raise /
    _replace_work_order_units / _replace_work_order_labor_entries /
    _quantize_money / _settlement_status / _get_unit / _get_cycle

改造点（相比 archive）：
  - 导入改为 business.models / business.context_runtime / business.services.labor_service
  - 移除 pydantic schema 依赖，create/update 接受显式关键字参数；用 _UNSET 哨兵区分
    "未提供" 和 "显式置空"（对应 archive 的 model_fields_set 语义）
  - labor_entries 为 list[dict]，每个 dict 含 worker_id/worker_name/pay_type/quantity/
    unit_price/paid_amount/note/client_request_id
  - 返回 dict（含 labor_entries 和 unit_names），Decimal → float
  - 保留 db: Session 第一参数；db.commit()/rollback() 改 db.flush()，由外层 session_scope 统一提交
  - settle_labor_payment 里 archive 调用 read_service.list_labor_payables，
    改为函数内从 recent_operation_service 导入（避免循环导入）
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from business.context_runtime import invalidate_farm_context
from business.models import (
    CropCycle,
    OperationWorkOrder,
    OperationWorkOrderUnit,
    PlantingUnit,
)
from business.services import labor_service
from business.services.labor_service import _labor_entry_to_dict

logger = logging.getLogger(__name__)

# 哨兵：用于 update 函数区分"未提供该字段"（保持原值）和"显式传 None"（清空）。
# 对应 archive pydantic 的 model_fields_set 语义。
_UNSET: Any = object()


class PlantingUnitConflictError(ValueError):
    """种植单元在同一茬口内违反名称唯一性。"""

    code = "duplicate_planting_unit_name"


def _normalize_unit_name(value: str) -> str:
    """统一地块/棚名称空白和兼容字符，作为同一茬口内的比较值。"""
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", "", normalized).strip()


def _planting_unit_to_dict(unit: PlantingUnit) -> dict[str, Any]:
    """ORM PlantingUnit → dict（Decimal 转 float）。"""
    return {
        "id": unit.id,
        "farm_id": unit.farm_id,
        "cycle_id": unit.cycle_id,
        "name": unit.name,
        "area_mu": float(unit.area_mu) if unit.area_mu is not None else None,
        "planted_date": unit.planted_date.isoformat() if unit.planted_date else None,
        "status": unit.status,
        "note": unit.note,
        "created_at": unit.created_at.isoformat() if unit.created_at else None,
    }


def _work_order_to_dict(work_order: OperationWorkOrder) -> dict[str, Any]:
    """ORM OperationWorkOrder → dict（含 labor_entries 和 unit_names）。

    字段结构参考 archive read_service.to_work_order_response，Decimal 统一转 float。
    """
    entries: list[dict[str, Any]] = []
    total_payable = Decimal("0")
    total_paid = Decimal("0")
    total_unpaid = Decimal("0")
    for entry in work_order.labor_entries:
        total_payable += entry.payable_amount or Decimal("0")
        total_paid += entry.paid_amount or Decimal("0")
        total_unpaid += entry.unpaid_amount or Decimal("0")
        entries.append(_labor_entry_to_dict(entry))
    unit_names = [link.unit.name for link in work_order.unit_links if link.unit]
    return {
        "id": work_order.id,
        "farm_id": work_order.farm_id,
        "cycle_id": work_order.cycle_id,
        "cycle_name": work_order.cycle.name if work_order.cycle else None,
        "operation_type": work_order.operation_type,
        "operation_date": work_order.operation_date.isoformat()
        if work_order.operation_date
        else None,
        "scope_type": work_order.scope_type,
        "unit_ids": [link.unit_id for link in work_order.unit_links],
        "unit_names": unit_names,
        "note": work_order.note,
        "photo_urls": work_order.photo_urls,
        "labor_entries": entries,
        "labor_cost_record_id": work_order.labor_cost_record_id,
        "total_payable_amount": float(total_payable),
        "total_paid_amount": float(total_paid),
        "total_unpaid_amount": float(total_unpaid),
        "created_at": work_order.created_at.isoformat()
        if work_order.created_at
        else None,
    }


# ─────────────────────────────────────────────────────────────
# 种植单元 CRUD
# ─────────────────────────────────────────────────────────────


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


def create_unit(
    db: Session,
    *,
    farm_id: int,
    cycle_id: int,
    name: str,
    area_mu: Decimal | float | None = None,
    planted_date: date | str | None = None,
    status: str = "active",
    note: str | None = None,
) -> dict[str, Any]:
    """创建种植单元；同一农场茬口内名称必须唯一。"""
    _get_cycle(db, cycle_id, farm_id)
    normalized_name = _normalize_unit_name(name)
    if not normalized_name:
        raise ValueError("种植单元名称不能为空")
    duplicate = next(
        (
            unit
            for unit in db.query(PlantingUnit)
            .filter(
                PlantingUnit.farm_id == farm_id,
                PlantingUnit.cycle_id == cycle_id,
            )
            .all()
            if _normalize_unit_name(unit.name) == normalized_name
        ),
        None,
    )
    if duplicate is not None:
        raise PlantingUnitConflictError(
            f"当前茬口已存在名为 {normalized_name} 的种植单元（ID={duplicate.id}）"
        )
    unit = PlantingUnit(
        farm_id=farm_id,
        cycle_id=cycle_id,
        name=normalized_name,
        area_mu=area_mu,
        planted_date=planted_date,
        status=status,
        note=note,
    )
    db.add(unit)
    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(unit)
    return _planting_unit_to_dict(unit)


def list_units(
    db: Session, farm_id: int, cycle_id: int | None = None
) -> list[dict[str, Any]]:
    """查询种植单元列表，可按 cycle_id 过滤。"""
    query = db.query(PlantingUnit).filter(PlantingUnit.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(PlantingUnit.cycle_id == cycle_id)
    units = query.order_by(PlantingUnit.id).all()
    return [_planting_unit_to_dict(u) for u in units]


def get_unit(db: Session, unit_id: int, farm_id: int) -> dict[str, Any]:
    """查询单个种植单元，并强制校验农场归属。"""
    return _planting_unit_to_dict(_get_unit(db, unit_id, farm_id))


def update_unit(
    db: Session,
    unit_id: int,
    *,
    farm_id: int,
    name: Any = _UNSET,
    area_mu: Any = _UNSET,
    planted_date: Any = _UNSET,
    status: Any = _UNSET,
    note: Any = _UNSET,
) -> dict[str, Any]:
    """更新种植单元；只更新非 _UNSET 字段（_UNSET 表示保持原值，None 表示清空）。"""
    unit = _get_unit(db, unit_id, farm_id)
    if name is not _UNSET:
        normalized_name = _normalize_unit_name(name)
        if not normalized_name:
            raise ValueError("种植单元名称不能为空")
        duplicate = next(
            (
                candidate
                for candidate in db.query(PlantingUnit)
                .filter(
                    PlantingUnit.farm_id == farm_id,
                    PlantingUnit.cycle_id == unit.cycle_id,
                    PlantingUnit.id != unit_id,
                )
                .all()
                if _normalize_unit_name(candidate.name) == normalized_name
            ),
            None,
        )
        if duplicate is not None:
            raise PlantingUnitConflictError(
                f"当前茬口已存在名为 {normalized_name} 的种植单元（ID={duplicate.id}）"
            )
        unit.name = normalized_name
    if area_mu is not _UNSET:
        unit.area_mu = area_mu
    if planted_date is not _UNSET:
        unit.planted_date = planted_date
    if status is not _UNSET:
        unit.status = status
    if note is not _UNSET:
        unit.note = note
    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(unit)
    return _planting_unit_to_dict(unit)


def delete_unit(db: Session, unit_id: int, farm_id: int) -> dict[str, Any]:
    """物理删除种植单元（archive 行为）。"""
    unit = _get_unit(db, unit_id, farm_id)
    db.delete(unit)
    db.flush()
    invalidate_farm_context(farm_id)
    return {"deleted": unit_id}


# ─────────────────────────────────────────────────────────────
# 作业单 CRUD
# ─────────────────────────────────────────────────────────────


def create_work_order(
    db: Session,
    *,
    farm_id: int,
    operation_type: str,
    operation_date: date,
    cycle_id: int | None = None,
    scope_type: str = "cycle",
    unit_ids: list[int] | None = None,
    labor_entries: list[dict] | None = None,
    note: str | None = None,
    photo_urls: str | None = None,
) -> dict[str, Any]:
    """创建作业单，含用工明细时自动生成人工成本账单。"""
    unit_ids = unit_ids or []
    labor_entries = labor_entries or []
    cycle = _validate_work_order_scope(
        db,
        cycle_id=cycle_id,
        operation_type=operation_type,
        operation_date=operation_date,
        scope_type=scope_type,
        unit_ids=unit_ids,
        farm_id=farm_id,
    )
    work_order = OperationWorkOrder(
        farm_id=farm_id,
        cycle_id=cycle_id,
        operation_type=operation_type,
        operation_date=operation_date,
        scope_type=scope_type,
        note=note,
        photo_urls=photo_urls,
    )
    db.add(work_order)
    db.flush()

    for unit_id in unit_ids:
        db.add(OperationWorkOrderUnit(work_order_id=work_order.id, unit_id=unit_id))

    for labor in labor_entries:
        db.add(labor_service.build_labor_entry(db, labor, work_order.id, farm_id))

    db.flush()
    labor_service.sync_work_order_labor_cost_record(db, work_order, cycle, farm_id)

    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(work_order)
    return _work_order_to_dict(work_order)


def _validate_work_order_scope(
    db: Session,
    *,
    cycle_id: int | None,
    operation_type: str,
    operation_date: date,
    scope_type: str,
    unit_ids: list[int],
    farm_id: int,
) -> CropCycle | None:
    """校验作业单作用域：farm/cycle/unit 三类，unit 级必须选种植单元且属于当前批次。

    作用域校验是业务硬约束：farm 级作业可无批次，cycle/unit 级必须有批次，
    unit 级必须选择种植单元且单元须属于当前批次，避免跨农场或跨批次误关联。
    """
    cycle = _get_cycle(db, cycle_id, farm_id) if cycle_id else None
    if scope_type not in {"cycle", "unit", "farm"}:
        raise ValueError("作业范围类型不合法")
    if scope_type in {"cycle", "unit"} and not cycle:
        raise ValueError("批次级或单元级作业必须关联种植批次")
    if scope_type == "unit" and not unit_ids:
        raise ValueError("单元级作业必须选择种植单元")
    if unit_ids:
        units = (
            db.query(PlantingUnit)
            .filter(
                PlantingUnit.farm_id == farm_id,
                PlantingUnit.id.in_(unit_ids),
            )
            .all()
        )
        if len(units) != len(set(unit_ids)):
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
) -> list[dict[str, Any]]:
    """查询作业单列表，按作业日期和 id 倒序。"""
    query = db.query(OperationWorkOrder).filter(OperationWorkOrder.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(OperationWorkOrder.cycle_id == cycle_id)
    work_orders = (
        query.order_by(
            OperationWorkOrder.operation_date.desc(),
            OperationWorkOrder.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_work_order_to_dict(w) for w in work_orders]


def count_work_orders(db: Session, farm_id: int, cycle_id: int | None = None) -> int:
    """统计作业单数量。"""
    query = db.query(OperationWorkOrder).filter(OperationWorkOrder.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(OperationWorkOrder.cycle_id == cycle_id)
    return query.count()


def get_work_order(
    db: Session, work_order_id: int, farm_id: int
) -> dict[str, Any] | None:
    """查询单个作业单详情；不存在返回 None。"""
    work_order = (
        db.query(OperationWorkOrder)
        .filter(
            OperationWorkOrder.id == work_order_id,
            OperationWorkOrder.farm_id == farm_id,
        )
        .first()
    )
    return _work_order_to_dict(work_order) if work_order else None


def update_work_order(
    db: Session,
    work_order_id: int,
    *,
    farm_id: int,
    cycle_id: Any = _UNSET,
    operation_type: Any = _UNSET,
    operation_date: Any = _UNSET,
    scope_type: Any = _UNSET,
    unit_ids: Any = _UNSET,
    labor_entries: Any = _UNSET,
    note: Any = _UNSET,
    photo_urls: Any = _UNSET,
) -> dict[str, Any]:
    """更新作业单和可选用工明细；_UNSET 表示保持原值，None/[] 表示清空。

    流程：先合并出"目标态"用于作用域校验，再写入字段，最后同步人工成本账单。
    """
    work_order = _get_work_order_or_raise(db, work_order_id, farm_id)

    new_cycle_id = work_order.cycle_id if cycle_id is _UNSET else cycle_id
    new_scope_type = work_order.scope_type if scope_type is _UNSET else scope_type
    if unit_ids is _UNSET:
        new_unit_ids = [link.unit_id for link in work_order.unit_links]
    else:
        new_unit_ids = unit_ids or []
    new_operation_type = (
        work_order.operation_type if operation_type is _UNSET else operation_type
    )
    new_operation_date = (
        work_order.operation_date if operation_date is _UNSET else operation_date
    )
    cycle = _validate_work_order_scope(
        db,
        cycle_id=new_cycle_id,
        operation_type=new_operation_type,
        operation_date=new_operation_date,
        scope_type=new_scope_type,
        unit_ids=new_unit_ids,
        farm_id=farm_id,
    )

    if cycle_id is not _UNSET:
        work_order.cycle_id = cycle_id
    if operation_type is not _UNSET:
        work_order.operation_type = operation_type
    if operation_date is not _UNSET:
        work_order.operation_date = operation_date
    if scope_type is not _UNSET:
        work_order.scope_type = scope_type
    if note is not _UNSET:
        work_order.note = note
    if photo_urls is not _UNSET:
        work_order.photo_urls = photo_urls
    if unit_ids is not _UNSET:
        _replace_work_order_units(db, work_order, new_unit_ids)
    if labor_entries is not _UNSET:
        _replace_work_order_labor_entries(db, work_order, labor_entries or [], farm_id)

    db.flush()
    if labor_entries is not _UNSET:
        db.expire(work_order, ["labor_entries"])
    labor_service.sync_work_order_labor_cost_record(db, work_order, cycle, farm_id)

    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(work_order)
    return _work_order_to_dict(work_order)


def settle_labor_payment(
    db: Session,
    farm_id: int,
    amount: Decimal | float | None = None,
    worker_id: int | None = None,
    worker_name: str | None = None,
    cycle_id: int | None = None,
    work_order_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """按筛选条件结算未付人工，amount 为空时全额结算。

    按条件结算的核心逻辑：先按筛选条件查出未付人工明细（按日期升序），
    然后从 amount 开始递减分配到每条明细，更新每条的 paid_amount/unpaid_amount/
    settlement_status，最后重新同步关联作业单的人工成本账单。
    """
    # 函数内导入避免循环依赖：recent_operation_service 不导入本模块，
    # 但本模块与其相互引用时仍走函数内导入更安全。
    from business.services.recent_operation_service import list_labor_payables

    entries = list_labor_payables(
        db,
        farm_id=farm_id,
        worker_id=worker_id,
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
        entry.unpaid_amount = _quantize_money(
            max(entry.payable_amount - entry.paid_amount, Decimal("0"))
        )
        entry.settlement_status = _settlement_status(
            entry.paid_amount, entry.unpaid_amount
        )
        remaining -= pay_amount
        paid_total += pay_amount
        affected.append(
            {
                "entry_id": entry.id,
                "work_order_id": entry.work_order_id,
                "worker_name": entry.worker.name if entry.worker else "",
                "paid_amount": float(_quantize_money(pay_amount)),
                "remaining_unpaid": float(entry.unpaid_amount),
            }
        )

    db.flush()
    for entry in entries:
        if entry.work_order:
            labor_service.sync_work_order_labor_cost_record(
                db, entry.work_order, entry.work_order.cycle, farm_id
            )
    db.flush()
    invalidate_farm_context(farm_id)
    # 按工人汇总
    worker_map: dict[str, dict] = {}
    for a in affected:
        wn = a["worker_name"]
        if wn not in worker_map:
            worker_map[wn] = {
                "worker_name": wn,
                "settled_amount": 0.0,
                "entry_count": 0,
            }
        worker_map[wn]["settled_amount"] += a["paid_amount"]
        worker_map[wn]["entry_count"] += 1
    return {
        "paid_amount": float(_quantize_money(paid_total)),
        "total_unpaid_before": float(_quantize_money(total_unpaid)),
        "remaining_unpaid": float(_quantize_money(total_unpaid - paid_total)),
        "settled_worker_count": len(worker_map),
        "worker_summary": sorted(
            worker_map.values(),
            key=lambda w: w["settled_amount"],
            reverse=True,
        ),
        "affected_entries": affected,
    }


def _get_work_order_or_raise(
    db: Session, work_order_id: int, farm_id: int
) -> OperationWorkOrder:
    work_order = (
        db.query(OperationWorkOrder)
        .filter(
            OperationWorkOrder.id == work_order_id,
            OperationWorkOrder.farm_id == farm_id,
        )
        .first()
    )
    if not work_order:
        raise ValueError("农事作业单不存在")
    return work_order


def _replace_work_order_units(
    db: Session, work_order: OperationWorkOrder, unit_ids: list[int]
) -> None:
    """全量替换作业单关联的种植单元。"""
    for link in list(work_order.unit_links):
        db.delete(link)
    db.flush()
    for unit_id in unit_ids:
        db.add(OperationWorkOrderUnit(work_order_id=work_order.id, unit_id=unit_id))


def _replace_work_order_labor_entries(
    db: Session,
    work_order: OperationWorkOrder,
    labor_entries: list[dict],
    farm_id: int,
) -> None:
    """全量替换作业单用工明细；删除旧明细后按 dict 列表重建。"""
    for entry in list(work_order.labor_entries):
        db.delete(entry)
    db.flush()
    work_order.labor_entries = []
    for data in labor_entries:
        entry = labor_service.build_labor_entry(db, data, work_order.id, farm_id)
        db.add(entry)
        work_order.labor_entries.append(entry)
    db.flush()


def _quantize_money(value: Decimal | float | int) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _settlement_status(paid: Decimal, unpaid: Decimal) -> str:
    if paid <= 0:
        return "unpaid"
    if unpaid <= 0:
        return "settled"
    return "partial"


__all__ = [
    "create_work_order",
    "list_work_orders",
    "count_work_orders",
    "get_work_order",
    "update_work_order",
    "settle_labor_payment",
    "create_unit",
    "list_units",
    "get_unit",
    "update_unit",
    "delete_unit",
    "PlantingUnitConflictError",
]
