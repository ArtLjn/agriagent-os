"""账务 selector。"""

from datetime import date
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.context.models import ContextBlock
from app.models.cost import CostRecord


def _format_amount(amount: Decimal) -> str:
    if amount == amount.to_integral_value():
        return str(int(amount))
    return str(amount.normalize())


class LedgerSelector:
    """选择账务摘要。"""

    def select(self, db: Session, farm_id: int, **_kwargs) -> list[ContextBlock]:
        today = date.today()
        total = (
            db.query(func.sum(CostRecord.amount))
            .filter(
                CostRecord.farm_id == farm_id,
                CostRecord.record_type == "cost",
                extract("year", CostRecord.record_date) == today.year,
                extract("month", CostRecord.record_date) == today.month,
            )
            .scalar()
        ) or Decimal("0")
        recent = (
            db.query(CostRecord)
            .filter(CostRecord.farm_id == farm_id)
            .order_by(CostRecord.record_date.desc())
            .limit(3)
            .all()
        )
        recent_text = "、".join(
            f"{item.category}{_format_amount(item.amount)}元" for item in recent
        )
        content = f"本月花费：{_format_amount(total)}元"
        if recent_text:
            content += f"；近期账务：{recent_text}"
        return [
            ContextBlock(
                key="ledger",
                source="ledger",
                purpose="账务摘要",
                content=content,
                priority=65,
                ttl_seconds=300,
            )
        ]


__all__ = ["LedgerSelector"]
