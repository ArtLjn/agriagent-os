from datetime import date
from decimal import Decimal

from sqlalchemy import desc, extract
from sqlalchemy.orm import Session

from app.context.invalidation import invalidate_farm_context
from app.core.timezone import beijing_now  # harness-exempt: 迁移期 service 复用统一北京时间工具，后续下沉 shared 时间工具
from app.models.cost import CostRecord
from app.models.cost_category import CostCategory
from app.schemas.cost import CostRecordCreate, CycleProfit, YearlySummary

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
    amount = _quantize_money(amount)
    settled_amount = _quantize_money(settled_amount)
    if settled_amount <= 0:
        return UNSETTLED
    if settled_amount >= amount:
        return SETTLED
    return PARTIAL


def default_settled_amount(record: CostRecordCreate) -> Decimal:
    if record.settled_amount is not None:
        return _quantize_money(record.settled_amount)
    if record.record_subtype == "赊账":
        return Decimal("0.00")
    return _quantize_money(record.amount)


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


def create_record(db: Session, record: CostRecordCreate, farm_id: int) -> CostRecord:
    """创建一条成本或收入记录。

    Args:
        db: 数据库会话。
        record: 创建请求数据。
        farm_id: 农场 ID。

    Returns:
        新创建的 CostRecord 实例。
    """
    category = _find_category(db, farm_id, record.category, record.record_type)
    source_active_key = _source_active_key(record.source_type, record.source_id)
    if source_active_key:
        _ensure_source_record_unique(db, farm_id, record.source_type, record.source_id)
    settled_amount = default_settled_amount(record)
    settlement_status = settlement_status_for(
        record.amount,
        settled_amount,
    )
    db_record = CostRecord(
        cycle_id=record.cycle_id,
        record_type=record.record_type,
        category=record.category,
        category_id=category.id if category else None,
        category_name_snapshot=category.name if category else record.category,
        amount=record.amount,
        settled_amount=settled_amount,
        settlement_status=settlement_status,
        record_date=record.record_date,
        recorded_at=record.recorded_at or beijing_now(),
        note=record.note,
        farm_id=farm_id,
        record_subtype=record.record_subtype,
        counterparty=record.counterparty,
        due_date=record.due_date,
        settled_at=record.settled_at,
        parent_record_id=record.parent_record_id,
        source_type=record.source_type,
        source_id=record.source_id,
        source_active_key=source_active_key,
    )
    db.add(db_record)
    try:
        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(db_record)
    except Exception:
        db.rollback()
        raise
    return db_record


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
    farm_id: int,
    cycle_id: int | None = None,
    category: str | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[CostRecord]:
    """查询成本记账记录列表（分页）。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        cycle_id: 按种植周期 ID 筛选（可选）。
        category: 按类别筛选（可选）。
        date_from: 按记录日期起始筛选（可选）。
        date_to: 按记录日期结束筛选（可选）。
        skip: 跳过记录数。
        limit: 返回最大记录数。

    Returns:
        符合条件的 CostRecord 列表，按记录日期倒序排列。
    """
    query = db.query(CostRecord).filter(
        CostRecord.farm_id == farm_id,
        CostRecord.deleted_at.is_(None),
    )
    if cycle_id is not None:
        query = query.filter(CostRecord.cycle_id == cycle_id)
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
    return (
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


def count_records(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
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
        date_from: 按记录日期起始筛选（可选）。
        date_to: 按记录日期结束筛选（可选）。

    Returns:
        符合条件的记录总数。
    """
    query = db.query(CostRecord).filter(
        CostRecord.farm_id == farm_id,
        CostRecord.deleted_at.is_(None),
    )
    if cycle_id is not None:
        query = query.filter(CostRecord.cycle_id == cycle_id)
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


def get_cycle_profit(db: Session, cycle_id: int, farm_id: int) -> CycleProfit:
    """计算指定种植周期的利润。

    Args:
        db: 数据库会话。
        cycle_id: 种植周期 ID。
        farm_id: 农场 ID。

    Returns:
        周期利润统计对象。
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
    return CycleProfit(
        cycle_id=cycle_id,
        total_cost=total_cost,
        total_income=total_income,
        net_profit=total_income - total_cost,
        settled_cost=settled_cost,
        settled_income=settled_income,
        unsettled_cost=unsettled_cost,
        unsettled_income=unsettled_income,
        labor_cost=labor_cost,
        labor_entry_cost=labor_entry_cost,
        operation_labor_cost=operation_labor_cost,
    )


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


def delete_record(db: Session, record_id: int, farm_id: int) -> CostRecord | None:
    """软删除一条成本记录。"""
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
    try:
        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(record)
    except Exception:
        db.rollback()
        raise
    return record


def get_yearly_summary(db: Session, year: int, farm_id: int) -> YearlySummary:
    """计算指定年度的收支汇总。

    Args:
        db: 数据库会话。
        year: 年份。
        farm_id: 农场 ID。

    Returns:
        年度收支汇总对象，包含按类别分组统计。
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

    return YearlySummary(
        year=year,
        total_cost=total_cost,
        total_income=total_income,
        net_profit=total_income - total_cost,
        settled_cost=settled_cost,
        settled_income=settled_income,
        unsettled_cost=unsettled_cost,
        unsettled_income=unsettled_income,
        by_category=by_category,
    )


__all__ = [
    "create_record",
    "get_records",
    "count_records",
    "get_cycle_profit",
    "get_yearly_summary",
    "delete_record",
    "is_legacy_repayment",
]
