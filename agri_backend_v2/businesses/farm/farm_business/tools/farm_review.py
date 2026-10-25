"""只读经营盘点：以业务记录汇总农事和未结款，不替用户结算。"""

from datetime import timedelta

from sqlalchemy import func

from farm_business.db import session_scope
from farm_business.mcp_app import mcp
from farm_business.models import CostRecord, FarmLog
from farm_business.services import debt_service, recent_operation_service
from farm_business.tools._headers import get_farm_id_from_headers
from shared.time import beijing_now

DEFAULT_REVIEW_DAYS = 7
MAX_REVIEW_DAYS = 90
PREVIEW_LIMIT = 20


@mcp.tool
def get_farm_review(days: int = DEFAULT_REVIEW_DAYS) -> dict:
    """汇总含今天在内的最近若干天农事，返回全量分类统计和有限条明细。"""
    farm_id = get_farm_id_from_headers()
    if not 1 <= days <= MAX_REVIEW_DAYS:
        return {
            "error": "validation_error",
            "code": "validation_error",
            "message": "回顾天数须为 1 至 90",
            "meta": {"days": days},
        }
    end = beijing_now().date()
    start = end - timedelta(days=days - 1)
    with session_scope() as db:
        query = db.query(FarmLog).filter(
            FarmLog.farm_id == farm_id,
            FarmLog.operation_date >= start,
            FarmLog.operation_date <= end,
        )
        counts = (
            query.with_entities(FarmLog.operation_type, func.count(FarmLog.id))
            .group_by(FarmLog.operation_type)
            .order_by(FarmLog.operation_type)
            .all()
        )
        rows = (
            query.order_by(FarmLog.operation_date.desc(), FarmLog.id.desc())
            .limit(PREVIEW_LIMIT)
            .all()
        )
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "total": sum(count for _, count in counts),
            "by_operation": [
                {"operation_type": name, "count": count} for name, count in counts
            ],
            "recent_logs": [
                {
                    "id": row.id,
                    "operation_type": row.operation_type,
                    "operation_date": row.operation_date.isoformat(),
                    "note": row.note,
                }
                for row in rows
            ],
            "preview_limit": PREVIEW_LIMIT,
        }


@mcp.tool
def get_payment_overview() -> dict:
    """分别盘点应收赊账、应付赊账和未付工资，避免混合收付方向或重复计入成本。"""
    farm_id = get_farm_id_from_headers()
    with session_scope() as db:
        # 赊账和工资单独展示：工资结算已有自动成本账单，不能相加后声称是总成本。
        rows = (
            db.query(
                CostRecord.record_type,
                CostRecord.counterparty,
                func.sum(CostRecord.amount - CostRecord.settled_amount),
            )
            .filter(
                CostRecord.farm_id == farm_id,
                CostRecord.record_subtype == debt_service.SUBTYPE_DEBT,
                CostRecord.deleted_at.is_(None),
                CostRecord.amount > CostRecord.settled_amount,
            )
            .group_by(CostRecord.record_type, CostRecord.counterparty)
            .order_by(CostRecord.record_type, CostRecord.counterparty)
            .all()
        )
        return {
            "debts": [
                {"record_type": kind, "counterparty": name, "remaining": float(amount)}
                for kind, name, amount in rows
            ],
            "unpaid_labor": recent_operation_service.get_unsettled_labor_summary(
                db, farm_id=farm_id
            ),
            "note": "income 为应收，cost 为应付；工资另列，不与赊账直接合计。",
        }
