"""债务（赊账）管理 Service（从 archive/backend/app/domains/finance/debt_service.py 直接复用）。

复用来源：archive/backend/app/domains/finance/debt_service.py

改造点：
  - 导入路径改为 agri_backend_v2 包：business.models、shared.time、business.context_runtime
  - 从 business.services.cost_service 复用 SETTLED/UNSETTLED/_find_category/
    _quantize_money/settlement_status_for/_record_to_dict（避免逻辑重复）
  - 移除 pydantic schema 依赖（CostRecordCreate/DebtSummary），create_debt_record
    改为显式关键字参数；get_debt_summary/settle_debt/get_debt_records 返回 dict
  - db.commit()/rollback() 改为 db.flush()，由外层 session_scope 统一提交
  - 保留 invalidate_farm_context 调用与 archive 的业务"为什么"注释
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from business.context_runtime import invalidate_farm_context
from business.models import CostRecord
from business.services.cost_service import (
    SETTLED,
    UNSETTLED,
    _find_category,
    _quantize_money,
    _record_to_dict,
    settlement_status_for,
)
from shared.time import beijing_now

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
    db: Session,
    *,
    farm_id: int,
    record_type: str,
    category: str,
    amount: Decimal,
    record_date: date,
    cycle_id: int | None = None,
    recorded_at: datetime | None = None,
    note: str | None = None,
    record_subtype: str | None = None,
    counterparty: str | None = None,
    due_date: date | None = None,
) -> dict:
    """创建赊账记录，自动将 record_subtype 设为赊账（如未指定）。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        record_type: cost 或 income。
        category: 分类名。
        amount: 金额。
        record_date: 记录日期。
        cycle_id: 种植周期 ID（可选）。
        recorded_at: 记录时间（可选，默认北京时间当前时刻）。
        note: 备注。
        record_subtype: 子类型（未指定则默认"赊账"）。
        counterparty: 交易对手。
        due_date: 到期日期。

    Returns:
        新创建赊账记录的 dict。
    """
    subtype = record_subtype or SUBTYPE_DEBT
    category_obj = _find_category(db, farm_id, category, record_type)
    db_record = CostRecord(
        farm_id=farm_id,
        cycle_id=cycle_id,
        record_type=record_type,
        category=category,
        category_id=category_obj.id if category_obj else None,
        category_name_snapshot=category_obj.name if category_obj else category,
        amount=amount,
        settled_amount=Decimal("0.00"),
        settlement_status=UNSETTLED,
        record_date=record_date,
        recorded_at=recorded_at or beijing_now(),
        note=note,
        record_subtype=subtype,
        counterparty=counterparty,
        due_date=due_date,
    )
    db.add(db_record)
    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(db_record)
    return _record_to_dict(db_record)


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
    *,
    farm_id: int,
    counterparty: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[dict]:
    """查询未结清的赊账记录列表（分页），返回 dict 列表，按记录日期倒序排列。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        counterparty: 按交易对手模糊筛选（可选）。
        skip: 跳过记录数。
        limit: 返回最大记录数。
    """
    records = (
        _build_debt_base_query(db, farm_id, counterparty)
        .order_by(
            CostRecord.record_date.desc(),
            CostRecord.recorded_at.desc(),
            CostRecord.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_record_to_dict(r) for r in records]


def count_debt_records(
    db: Session, *, farm_id: int, counterparty: str | None = None
) -> int:
    """查询未结清赊账记录总数。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        counterparty: 按交易对手模糊筛选（可选）。
    """
    return _build_debt_base_query(db, farm_id, counterparty).count()


def get_debt_summary(db: Session, *, farm_id: int) -> list[dict]:
    """按交易对手分组统计债务情况，返回 dict 列表。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
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
            {
                "counterparty": row.counterparty,
                "total_debt": float(total_debt),
                "total_settled": float(total_settled),
                "remaining": float(total_debt - total_settled),
                "record_count": row.record_count,
            }
        )
    return result


def settle_debt(
    db: Session,
    *,
    farm_id: int,
    counterparty: str,
    amount: Decimal | None = None,
    note: str | None = None,
) -> dict:
    """结清赊账记录。

    查找指定交易对手最早的未结清赊账记录，直接更新原账单结算字段。
    amount 为 None 则结清剩余金额；amount 小于剩余金额则部分结算
    （settlement_status 置为 partial，settled_at 清空，等待后续补结）。
    note 仅兼容旧 payload；当前不创建还款记录，也不写入原账单。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        counterparty: 交易对手名称（精确匹配）。
        amount: 还款金额，None 表示全额还清。
        note: 兼容旧 payload 的还款备注，当前不落库。

    Returns:
        已更新的原始账单记录 dict。

    Raises:
        ValueError: 未找到未结清的赊账记录。
        InvalidSettlementAmountError: 结算金额无效。
    """
    settlement_amount = _normalize_settlement_amount(amount)

    debt = (
        _build_debt_base_query(db, farm_id)
        .filter(CostRecord.counterparty == counterparty)
        .order_by(
            CostRecord.record_date.asc(),
            CostRecord.recorded_at.asc(),
            CostRecord.id.asc(),
        )
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
    if debt.settlement_status == SETTLED:
        debt.settled_at = beijing_now()
    else:
        debt.settled_at = None

    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(debt)
    return _record_to_dict(debt)


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
