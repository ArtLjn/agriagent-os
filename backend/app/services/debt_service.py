"""债务管理 Service，处理赊账记录的业务逻辑。"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.context.invalidation import invalidate_farm_context
from app.models.cost import CostRecord
from app.schemas.cost import CostRecordCreate, DebtSummary
from app.services.cost_service import (
    SETTLED,
    UNSETTLED,
    _find_category,
    _quantize_money,
    settlement_status_for,
)

SUBTYPE_DEBT = "赊账"
CATEGORY_REPAY = "还款"


class InvalidSettlementAmountError(ValueError):
    """结算金额无效。"""


def _normalize_settlement_amount(amount) -> Decimal | None:
    """校验并规范化结算金额，None 表示全额结清。"""
    if amount is None:
        return None
    try:
        normalized = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        raise InvalidSettlementAmountError("amount 必须是有效数字") from None
    if not normalized.is_finite():
        raise InvalidSettlementAmountError("amount 必须是有效数字")
    if normalized <= 0:
        raise InvalidSettlementAmountError("结算金额必须大于 0")
    return normalized


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
    category = _find_category(db, farm_id, record.category, record.record_type)
    db_record = CostRecord(
        farm_id=farm_id,
        cycle_id=record.cycle_id,
        record_type=record.record_type,
        category=record.category,
        category_id=category.id if category else None,
        category_name_snapshot=category.name if category else record.category,
        amount=record.amount,
        settled_amount=Decimal("0.00"),
        settlement_status=UNSETTLED,
        record_date=record.record_date,
        note=record.note,
        record_subtype=subtype,
        counterparty=record.counterparty,
        due_date=record.due_date,
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


def _build_debt_base_query(db: Session, farm_id: int, counterparty: str | None = None):
    """构建未结清赊账记录的基础查询。"""
    query = (
        db.query(CostRecord)
        .filter(CostRecord.farm_id == farm_id)
        .filter(CostRecord.record_subtype == SUBTYPE_DEBT)
        .filter(
            or_(
                CostRecord.settlement_status.is_(None),
                CostRecord.settlement_status != SETTLED,
            )
        )
        .filter(
            or_(
                CostRecord.settled_amount.is_(None),
                CostRecord.settled_amount < CostRecord.amount,
            )
        )
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
        _build_debt_base_query(db, farm_id)
        .with_entities(
            CostRecord.counterparty,
            func.sum(CostRecord.amount).label("total_debt"),
            func.sum(CostRecord.settled_amount).label("total_settled"),
            func.count(CostRecord.id).label("record_count"),
        )
        .group_by(CostRecord.counterparty)
        .all()
    )

    result = []
    for row in debt_rows:
        total_debt = Decimal(str(row.total_debt or 0))
        total_settled = Decimal(str(row.total_settled or 0))
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

    查找指定交易对手最早的未结清赊账记录，直接更新原账单结算字段。
    amount 为 None 则结清剩余金额；amount 小于剩余金额则部分结算。
    note 仅兼容旧 payload；当前不创建还款记录，也不写入原账单。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        counterparty: 交易对手名称（精确匹配）。
        amount: 还款金额，None 表示全额还清。
        note: 兼容旧 payload 的还款备注，当前不落库。

    Returns:
        已更新的原始账单记录。

    Raises:
        ValueError: 未找到未结清的赊账记录。
        InvalidSettlementAmountError: 结算金额无效。
    """
    settlement_amount = _normalize_settlement_amount(amount)

    debt = (
        _build_debt_base_query(db, farm_id)
        .filter(CostRecord.counterparty == counterparty)
        .order_by(CostRecord.record_date.asc())
        .with_for_update()
        .first()
    )
    if debt is None:
        raise ValueError(f"未找到 {counterparty} 的未结清账单")

    current_settled = Decimal(str(debt.settled_amount or 0))
    remaining = Decimal(str(debt.amount)) - current_settled
    settlement_amount = remaining if settlement_amount is None else settlement_amount
    if settlement_amount > remaining:
        settlement_amount = _quantize_money(remaining)

    debt.settled_amount = _quantize_money(current_settled + settlement_amount)
    debt.settlement_status = settlement_status_for(debt.amount, debt.settled_amount)
    if debt.settlement_status == "settled":
        debt.settled_at = datetime.now(timezone.utc)
    else:
        debt.settled_at = None

    try:
        db.commit()
        invalidate_farm_context(farm_id)
        db.refresh(debt)
    except Exception:
        db.rollback()
        raise
    return debt


__all__ = [
    "SUBTYPE_DEBT",
    "CATEGORY_REPAY",
    "InvalidSettlementAmountError",
    "create_debt_record",
    "get_debt_records",
    "count_debt_records",
    "get_debt_summary",
    "settle_debt",
]
