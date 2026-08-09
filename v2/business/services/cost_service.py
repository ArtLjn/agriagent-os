"""成本记账 Service（从 archive/backend/app/domains/finance/cost_service.py 直接复用）。

复用来源：archive/backend/app/domains/finance/cost_service.py

改造点：
  - 导入路径改为 v2 包：business.models（CostRecord/CostCategory 合并导入）、
    shared.time、business.context_runtime
  - 移除 pydantic schema 依赖（CostRecordCreate/CycleProfit/YearlySummary），
    create_record 改为显式关键字参数；get_cycle_profit/get_yearly_summary 返回 dict
  - 返回 dict 而非 ORM/pydantic 对象（_record_to_dict 序列化，金额 Decimal 转 float）
  - db.commit()/rollback() 改为 db.flush()，由外层 session_scope 统一提交
  - 保留 invalidate_farm_context 调用与 archive 的业务"为什么"注释
  - _find_category 在本模块内实现（不导入 cost_category_service，避免循环依赖）
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, extract
from sqlalchemy.orm import Session

from business.context_runtime import invalidate_farm_context
from business.models import CostCategory, CostRecord
from shared.time import beijing_now

ACTIVE_SOURCE_KEY = "active"
LABOR_CATEGORY = "人工"
LABOR_ENTRY_SOURCE = "labor_entry"
WORK_ORDER_SOURCE = "operation_work_order"
REPAY_CATEGORY = "还款"
SETTLED = "settled"
PARTIAL = "partial"
UNSETTLED = "unsettled"


class DuplicateSourceRecordError(ValueError):
    """同一来源已存在活动账单。"""


def _quantize_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def is_legacy_repayment(record: CostRecord) -> bool:
    """兼容旧还款记录：旧版本通过 parent_record_id 关联一条 income/还款 子记录，
    统计利润/年度汇总时需排除，否则会与原账单的结算金额重复计算。"""
    return (
        record.record_type == "income"
        and record.category == REPAY_CATEGORY
        and record.parent_record_id is not None
    )


def _active_business_records(records: list[CostRecord]) -> list[CostRecord]:
    return [record for record in records if not is_legacy_repayment(record)]


def _settled_amount(record: CostRecord) -> Decimal:
    amount = _quantize_money(record.amount or Decimal("0"))
    settled_amount = _quantize_money(record.settled_amount or Decimal("0"))
    return min(max(settled_amount, Decimal("0.00")), amount)


def _unsettled_amount(record: CostRecord) -> Decimal:
    amount = _quantize_money(record.amount or Decimal("0"))
    return max(amount - _settled_amount(record), Decimal("0.00"))


def settlement_status_for(amount: Decimal, settled_amount: Decimal) -> str:
    """三态判断：按 settled_amount 与 amount 的比较得出未结清/部分结清/已结清。"""
    amount = _quantize_money(amount)
    settled_amount = _quantize_money(settled_amount)
    if settled_amount <= 0:
        return UNSETTLED
    if settled_amount >= amount:
        return SETTLED
    return PARTIAL


def default_settled_amount(
    *,
    amount: Decimal,
    settled_amount: Decimal | None,
    record_subtype: str | None,
) -> Decimal:
    """默认结算金额：显式指定则用之；赊账默认 0；其余默认全额结清。"""
    if settled_amount is not None:
        return _quantize_money(settled_amount)
    if record_subtype == "赊账":
        return Decimal("0.00")
    return _quantize_money(amount)


def _find_category(
    db: Session, farm_id: int, category_name: str, record_type: str
) -> CostCategory | None:
    """按农场、分类名和收支类型查找分类。"""
    return (
        db.query(CostCategory)
        .filter(
            CostCategory.farm_id == farm_id,
            CostCategory.name == category_name,
            CostCategory.type == record_type,
        )
        .first()
    )


def _record_to_dict(record: CostRecord) -> dict[str, Any]:
    """ORM CostRecord → dict（金额字段转 float，便于 JSON 序列化）。"""
    return {
        "id": record.id,
        "farm_id": record.farm_id,
        "cycle_id": record.cycle_id,
        "record_type": record.record_type,
        "category": record.category,
        "category_id": record.category_id,
        "amount": float(record.amount) if record.amount is not None else None,
        "settled_amount": float(record.settled_amount)
        if record.settled_amount is not None
        else None,
        "unsettled_amount": float(record.unsettled_amount),
        "settlement_status": record.settlement_status,
        "record_date": record.record_date.isoformat() if record.record_date else None,
        "recorded_at": record.recorded_at.isoformat() if record.recorded_at else None,
        "note": record.note,
        "record_subtype": record.record_subtype,
        "counterparty": record.counterparty,
        "due_date": record.due_date.isoformat() if record.due_date else None,
        "settled_at": record.settled_at.isoformat() if record.settled_at else None,
        "parent_record_id": record.parent_record_id,
        "source_type": record.source_type,
        "source_id": record.source_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def create_record(
    db: Session,
    *,
    farm_id: int,
    record_type: str,
    category: str,
    amount: Decimal,
    record_date: date,
    cycle_id: int | None = None,
    settled_amount: Decimal | None = None,
    recorded_at: datetime | None = None,
    note: str | None = None,
    record_subtype: str | None = None,
    counterparty: str | None = None,
    due_date: date | None = None,
    settled_at: datetime | None = None,
    parent_record_id: int | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
) -> dict:
    """创建一条成本或收入记录。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        record_type: cost 或 income。
        category: 分类名。
        amount: 金额。
        record_date: 记录日期。
        cycle_id: 种植周期 ID（可选）。
        settled_amount: 已结清金额（可选，未传则按 record_subtype 推断）。
        recorded_at: 记录时间（可选，默认北京时间当前时刻）。
        note: 备注。
        record_subtype: 子类型（如"赊账"）。
        counterparty: 交易对手。
        due_date: 到期日期。
        settled_at: 结清时间。
        parent_record_id: 父记录 ID（兼容旧还款记录）。
        source_type: 来源类型（如 operation_work_order / labor_entry）。
        source_id: 来源 ID。

    Returns:
        新创建记录的 dict。
    """
    category_obj = _find_category(db, farm_id, category, record_type)
    source_active_key = _source_active_key(source_type, source_id)
    if source_active_key:
        _ensure_source_record_unique(db, farm_id, source_type, source_id)
    settled = default_settled_amount(
        amount=amount,
        settled_amount=settled_amount,
        record_subtype=record_subtype,
    )
    status = settlement_status_for(amount, settled)
    db_record = CostRecord(
        farm_id=farm_id,
        cycle_id=cycle_id,
        record_type=record_type,
        category=category,
        category_id=category_obj.id if category_obj else None,
        category_name_snapshot=category_obj.name if category_obj else category,
        amount=amount,
        settled_amount=settled,
        settlement_status=status,
        record_date=record_date,
        recorded_at=recorded_at or beijing_now(),
        note=note,
        record_subtype=record_subtype,
        counterparty=counterparty,
        due_date=due_date,
        settled_at=settled_at,
        parent_record_id=parent_record_id,
        source_type=source_type,
        source_id=source_id,
        source_active_key=source_active_key,
    )
    db.add(db_record)
    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(db_record)
    return _record_to_dict(db_record)


def _source_active_key(source_type: str | None, source_id: int | None) -> str | None:
    if source_type is not None and source_id is not None:
        return ACTIVE_SOURCE_KEY
    return None


def _ensure_source_record_unique(
    db: Session, farm_id: int, source_type: str | None, source_id: int | None
) -> None:
    exists = (
        db.query(CostRecord.id)
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.source_type == source_type,
            CostRecord.source_id == source_id,
            CostRecord.source_active_key == ACTIVE_SOURCE_KEY,
            CostRecord.deleted_at.is_(None),
        )
        .first()
    )
    if exists:
        raise DuplicateSourceRecordError("同一来源已存在活动账单")


def get_records(
    db: Session,
    *,
    farm_id: int,
    cycle_id: int | None = None,
    record_type: str | None = None,
    category: str | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[dict]:
    """查询成本记账记录列表（分页），返回 dict 列表，按记录日期倒序排列。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        cycle_id: 按种植周期 ID 筛选（可选）。
        category: 按类别筛选（可选）。
        source_type: 按来源类型筛选（可选）。
        source_id: 按来源 ID 筛选（可选）。
        date_from: 按记录日期起始筛选（可选）。
        date_to: 按记录日期结束筛选（可选）。
        skip: 跳过记录数。
        limit: 返回最大记录数。
    """
    query = db.query(CostRecord).filter(
        CostRecord.farm_id == farm_id,
        CostRecord.deleted_at.is_(None),
    )
    if cycle_id is not None:
        query = query.filter(CostRecord.cycle_id == cycle_id)
    if record_type is not None:
        query = query.filter(CostRecord.record_type == record_type)
    if category is not None:
        query = query.filter(CostRecord.category == category)
    if source_type is not None:
        query = query.filter(CostRecord.source_type == source_type)
    if source_id is not None:
        query = query.filter(CostRecord.source_id == source_id)
    if date_from is not None:
        query = query.filter(CostRecord.record_date >= date_from)
    if date_to is not None:
        query = query.filter(CostRecord.record_date <= date_to)
    records = (
        query.order_by(
            CostRecord.settled_at.is_(None).asc(),
            desc(CostRecord.settled_at),
            CostRecord.record_date.desc(),
            CostRecord.recorded_at.desc(),
            CostRecord.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_record_to_dict(r) for r in records]


def count_records(
    db: Session,
    *,
    farm_id: int,
    cycle_id: int | None = None,
    record_type: str | None = None,
    category: str | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> int:
    """查询成本记账记录总数。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        cycle_id: 按种植周期 ID 筛选（可选）。
        category: 按类别筛选（可选）。
        source_type: 按来源类型筛选（可选）。
        source_id: 按来源 ID 筛选（可选）。
        date_from: 按记录日期起始筛选（可选）。
        date_to: 按记录日期结束筛选（可选）。
    """
    query = db.query(CostRecord).filter(
        CostRecord.farm_id == farm_id,
        CostRecord.deleted_at.is_(None),
    )
    if cycle_id is not None:
        query = query.filter(CostRecord.cycle_id == cycle_id)
    if record_type is not None:
        query = query.filter(CostRecord.record_type == record_type)
    if category is not None:
        query = query.filter(CostRecord.category == category)
    if source_type is not None:
        query = query.filter(CostRecord.source_type == source_type)
    if source_id is not None:
        query = query.filter(CostRecord.source_id == source_id)
    if date_from is not None:
        query = query.filter(CostRecord.record_date >= date_from)
    if date_to is not None:
        query = query.filter(CostRecord.record_date <= date_to)
    return query.count()


def get_cycle_profit(db: Session, *, farm_id: int, cycle_id: int) -> dict:
    """计算指定种植周期的利润，返回 dict。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        cycle_id: 种植周期 ID。
    """
    records = (
        db.query(CostRecord)
        .filter(
            CostRecord.cycle_id == cycle_id,
            CostRecord.farm_id == farm_id,
            CostRecord.deleted_at.is_(None),
        )
        .all()
    )
    records = _active_business_records(records)
    total_cost = sum(
        (r.amount for r in records if r.record_type == "cost"),
        Decimal("0"),
    )
    total_income = sum(
        (r.amount for r in records if r.record_type == "income"),
        Decimal("0"),
    )
    settled_cost = _sum_by_type(records, "cost", _settled_amount)
    settled_income = _sum_by_type(records, "income", _settled_amount)
    unsettled_cost = _sum_by_type(records, "cost", _unsettled_amount)
    unsettled_income = _sum_by_type(records, "income", _unsettled_amount)
    labor_entry_cost = _sum_labor_source(records, LABOR_ENTRY_SOURCE)
    operation_labor_cost = _sum_labor_source(records, WORK_ORDER_SOURCE)
    labor_cost = labor_entry_cost + operation_labor_cost
    return {
        "cycle_id": cycle_id,
        "total_cost": float(total_cost),
        "total_income": float(total_income),
        "net_profit": float(total_income - total_cost),
        "settled_cost": float(settled_cost),
        "settled_income": float(settled_income),
        "unsettled_cost": float(unsettled_cost),
        "unsettled_income": float(unsettled_income),
        "labor_cost": float(labor_cost),
        "labor_entry_cost": float(labor_entry_cost),
        "operation_labor_cost": float(operation_labor_cost),
    }


def _sum_by_type(records: list[CostRecord], record_type: str, amount_getter) -> Decimal:
    return sum(
        (
            amount_getter(record)
            for record in records
            if record.record_type == record_type
        ),
        Decimal("0"),
    )


def _sum_labor_source(records: list[CostRecord], source_type: str) -> Decimal:
    return sum(
        (
            record.amount
            for record in records
            if record.record_type == "cost"
            and record.category == LABOR_CATEGORY
            and record.source_type == source_type
        ),
        Decimal("0"),
    )


def delete_record(db: Session, *, farm_id: int, record_id: int) -> dict | None:
    """软删除一条成本记录，返回删除后的 dict 或 None（记录不存在时）。"""
    record = (
        db.query(CostRecord)
        .filter(
            CostRecord.id == record_id,
            CostRecord.farm_id == farm_id,
            CostRecord.deleted_at.is_(None),
        )
        .first()
    )
    if not record:
        return None
    record.deleted_at = beijing_now()
    record.source_active_key = None
    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(record)
    return _record_to_dict(record)


def get_yearly_summary(db: Session, *, farm_id: int, year: int) -> dict:
    """计算指定年度的收支汇总，返回 dict（含 by_category 按类别分组）。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        year: 年份。
    """
    records = (
        db.query(CostRecord)
        .filter(
            extract("year", CostRecord.record_date) == year,
            CostRecord.farm_id == farm_id,
            CostRecord.deleted_at.is_(None),
        )
        .all()
    )
    records = _active_business_records(records)
    total_cost = Decimal("0")
    total_income = Decimal("0")
    settled_cost = Decimal("0")
    settled_income = Decimal("0")
    unsettled_cost = Decimal("0")
    unsettled_income = Decimal("0")
    by_category: dict[str, Decimal] = {}

    for r in records:
        if r.record_type == "cost":
            total_cost += r.amount
            settled_cost += _settled_amount(r)
            unsettled_cost += _unsettled_amount(r)
        elif r.record_type == "income":
            total_income += r.amount
            settled_income += _settled_amount(r)
            unsettled_income += _unsettled_amount(r)
        cat = f"{r.record_type}:{r.category}"
        by_category[cat] = by_category.get(cat, Decimal("0")) + r.amount

    return {
        "year": year,
        "total_cost": float(total_cost),
        "total_income": float(total_income),
        "net_profit": float(total_income - total_cost),
        "settled_cost": float(settled_cost),
        "settled_income": float(settled_income),
        "unsettled_cost": float(unsettled_cost),
        "unsettled_income": float(unsettled_income),
        "by_category": {k: float(v) for k, v in by_category.items()},
    }


__all__ = [
    "ACTIVE_SOURCE_KEY",
    "LABOR_CATEGORY",
    "LABOR_ENTRY_SOURCE",
    "WORK_ORDER_SOURCE",
    "REPAY_CATEGORY",
    "SETTLED",
    "PARTIAL",
    "UNSETTLED",
    "DuplicateSourceRecordError",
    "settlement_status_for",
    "is_legacy_repayment",
    "create_record",
    "get_records",
    "count_records",
    "get_cycle_profit",
    "get_yearly_summary",
    "delete_record",
]
