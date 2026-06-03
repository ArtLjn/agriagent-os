from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.schemas.cost import CostRecordCreate, CycleProfit, YearlySummary


def create_record(db: Session, record: CostRecordCreate, farm_id: int) -> CostRecord:
    """创建一条成本或收入记录。

    Args:
        db: 数据库会话。
        record: 创建请求数据。
        farm_id: 农场 ID。

    Returns:
        新创建的 CostRecord 实例。
    """
    db_record = CostRecord(
        cycle_id=record.cycle_id,
        record_type=record.record_type,
        category=record.category,
        amount=record.amount,
        record_date=record.record_date,
        note=record.note,
        farm_id=farm_id,
        record_subtype=record.record_subtype,
        counterparty=record.counterparty,
        due_date=record.due_date,
        settled_at=record.settled_at,
        parent_record_id=record.parent_record_id,
    )
    db.add(db_record)
    try:
        db.commit()
        db.refresh(db_record)
    except Exception:
        db.rollback()
        raise
    return db_record


def get_records(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    category: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[CostRecord]:
    """查询成本记账记录列表（分页）。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        cycle_id: 按种植周期 ID 筛选（可选）。
        category: 按类别筛选（可选）。
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
    return query.order_by(CostRecord.record_date.desc()).offset(skip).limit(limit).all()


def count_records(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    category: str | None = None,
) -> int:
    """查询成本记账记录总数。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        cycle_id: 按种植周期 ID 筛选（可选）。
        category: 按类别筛选（可选）。

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
    total_cost = sum(
        (r.amount for r in records if r.record_type == "cost"),
        Decimal("0"),
    )
    total_income = sum(
        (r.amount for r in records if r.record_type == "income"),
        Decimal("0"),
    )
    return CycleProfit(
        cycle_id=cycle_id,
        total_cost=total_cost,
        total_income=total_income,
        net_profit=total_income - total_cost,
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
    record.deleted_at = datetime.now(timezone.utc)
    try:
        db.commit()
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
    total_cost = Decimal("0")
    total_income = Decimal("0")
    by_category: dict[str, Decimal] = {}

    for r in records:
        if r.record_type == "cost":
            total_cost += r.amount
        elif r.record_type == "income":
            total_income += r.amount
        cat = f"{r.record_type}:{r.category}"
        by_category[cat] = by_category.get(cat, Decimal("0")) + r.amount

    return YearlySummary(
        year=year,
        total_cost=total_cost,
        total_income=total_income,
        net_profit=total_income - total_cost,
        by_category=by_category,
    )


__all__ = [
    "create_record",
    "get_records",
    "count_records",
    "get_cycle_profit",
    "get_yearly_summary",
    "delete_record",
]
