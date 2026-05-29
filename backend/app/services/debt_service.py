"""债务管理 Service，处理赊账记录的业务逻辑。"""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.schemas.cost import CostRecordCreate, DebtSummary

SUBTYPE_DEBT = "赊账"
CATEGORY_REPAY = "还款"


def create_debt_record(
    db: Session, record: CostRecordCreate, farm_id: int
) -> CostRecord:
    """创建赊账记录，自动将 record_subtype 设为赊账（如未指定）。

    Args:
        db: 数据库会话。
        record: 创建请求数据。
        farm_id: 农场 ID。

    Returns:
        新创建的 CostRecord 实例。
    """
    subtype = record.record_subtype or SUBTYPE_DEBT
    db_record = CostRecord(
        farm_id=farm_id,
        cycle_id=record.cycle_id,
        record_type=record.record_type,
        category=record.category,
        amount=record.amount,
        record_date=record.record_date,
        note=record.note,
        record_subtype=subtype,
        counterparty=record.counterparty,
        due_date=record.due_date,
    )
    db.add(db_record)
    try:
        db.commit()
        db.refresh(db_record)
    except Exception:
        db.rollback()
        raise
    return db_record


def _build_debt_base_query(db: Session, farm_id: int, counterparty: str | None = None):
    """构建未结清赊账记录的基础查询。"""
    query = (
        db.query(CostRecord)
        .filter(CostRecord.farm_id == farm_id)
        .filter(CostRecord.record_subtype == SUBTYPE_DEBT)
        .filter(CostRecord.settled_at.is_(None))
        .filter(CostRecord.deleted_at.is_(None))
    )
    if counterparty is not None:
        query = query.filter(CostRecord.counterparty.like(f"%{counterparty}%"))
    return query


def get_debt_records(
    db: Session,
    farm_id: int,
    counterparty: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[CostRecord]:
    """查询未结清的赊账记录列表（分页）。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        counterparty: 按交易对手模糊筛选（可选）。
        skip: 跳过记录数。
        limit: 返回最大记录数。

    Returns:
        符合条件的 CostRecord 列表，按记录日期倒序排列。
    """
    return (
        _build_debt_base_query(db, farm_id, counterparty)
        .order_by(CostRecord.record_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_debt_records(
    db: Session, farm_id: int, counterparty: str | None = None
) -> int:
    """查询未结清赊账记录总数。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        counterparty: 按交易对手模糊筛选（可选）。

    Returns:
        符合条件的记录总数。
    """
    return _build_debt_base_query(db, farm_id, counterparty).count()


def get_debt_summary(db: Session, farm_id: int) -> list[DebtSummary]:
    """按交易对手分组统计债务情况。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。

    Returns:
        债务统计列表，包含总债务、已还款、剩余金额和记录数。
    """
    debt_rows = (
        db.query(
            CostRecord.counterparty,
            func.sum(CostRecord.amount).label("total_debt"),
            func.count(CostRecord.id).label("record_count"),
        )
        .filter(CostRecord.farm_id == farm_id)
        .filter(CostRecord.record_subtype == SUBTYPE_DEBT)
        .filter(CostRecord.deleted_at.is_(None))
        .group_by(CostRecord.counterparty)
        .all()
    )

    repay_rows = (
        db.query(
            CostRecord.counterparty,
            func.sum(CostRecord.amount).label("total_settled"),
        )
        .filter(CostRecord.farm_id == farm_id)
        .filter(CostRecord.record_type == "income")
        .filter(CostRecord.category == CATEGORY_REPAY)
        .filter(CostRecord.parent_record_id.isnot(None))
        .filter(CostRecord.deleted_at.is_(None))
        .group_by(CostRecord.counterparty)
        .all()
    )

    repay_map = {
        row.counterparty: Decimal(str(row.total_settled or 0)) for row in repay_rows
    }

    result = []
    for row in debt_rows:
        total_debt = Decimal(str(row.total_debt or 0))
        total_settled = repay_map.get(row.counterparty, Decimal("0"))
        result.append(
            DebtSummary(
                counterparty=row.counterparty,
                total_debt=total_debt,
                total_settled=total_settled,
                remaining=total_debt - total_settled,
                record_count=row.record_count,
            )
        )
    return result


def settle_debt(
    db: Session,
    farm_id: int,
    counterparty: str,
    amount: Decimal | None = None,
    note: str | None = None,
) -> CostRecord:
    """结清赊账记录。

    查找指定交易对手的未结清赊账记录，创建还款记录。
    amount 为 None 则全额还清并标记原记录结清；
    amount 小于债务金额则部分还款，不标记结清。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        counterparty: 交易对手名称（精确匹配）。
        amount: 还款金额，None 表示全额还清。
        note: 还款备注。

    Returns:
        新创建的还款记录。

    Raises:
        ValueError: 未找到未结清的赊账记录。
    """
    debt = (
        db.query(CostRecord)
        .filter(CostRecord.farm_id == farm_id)
        .filter(CostRecord.record_subtype == SUBTYPE_DEBT)
        .filter(CostRecord.settled_at.is_(None))
        .filter(CostRecord.deleted_at.is_(None))
        .filter(CostRecord.counterparty == counterparty)
        .order_by(CostRecord.record_date.asc())
        .first()
    )
    if debt is None:
        raise ValueError(f"未找到 {counterparty} 的未结清赊账记录")

    repay_amount = amount if amount is not None else debt.amount
    repay_record = CostRecord(
        farm_id=farm_id,
        record_type="income",
        category=CATEGORY_REPAY,
        amount=repay_amount,
        record_date=date.today(),
        note=note,
        counterparty=counterparty,
        parent_record_id=debt.id,
    )
    db.add(repay_record)

    if amount is None or Decimal(str(debt.amount)) <= Decimal(str(repay_amount)):
        debt.settled_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(repay_record)
    except Exception:
        db.rollback()
        raise
    return repay_record


__all__ = [
    "SUBTYPE_DEBT",
    "CATEGORY_REPAY",
    "create_debt_record",
    "get_debt_records",
    "count_debt_records",
    "get_debt_summary",
    "settle_debt",
]
