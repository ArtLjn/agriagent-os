"""Admin 业务运营仪表盘 API — 平台聚合指标。"""

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.domains.conversation.models import Conversation
from app.domains.finance.cost_models import CostRecord
from app.domains.farm.models import Farm
from app.domains.planting.log_models import FarmLog
from app.domains.users.models import User
from app.domains.users.dependencies import require_admin

router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    """平台规模与今日活跃度汇总（KPI 卡片）。"""
    today = date.today()
    today_start = datetime.combine(today, time.min)

    farm_count = db.query(func.count(Farm.id)).scalar() or 0
    user_count = db.query(func.count(User.id)).scalar() or 0

    dau_today = (
        db.query(func.count(func.distinct(Conversation.user_id)))
        .filter(
            Conversation.last_active_at >= today_start,
            Conversation.user_id.isnot(None),
        )
        .scalar()
        or 0
    )

    log_count_today = (
        db.query(func.count(FarmLog.id))
        .filter(FarmLog.operation_date == today)
        .scalar()
        or 0
    )
    cost_count_today = (
        db.query(func.count(CostRecord.id))
        .filter(CostRecord.record_date == today, CostRecord.deleted_at.is_(None))
        .scalar()
        or 0
    )

    return {
        "farm_count": farm_count,
        "user_count": user_count,
        "dau_today": dau_today,
        "records_today": log_count_today + cost_count_today,
    }


@router.get("/trend")
def dashboard_trend(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    """近 N 天业务记录数（农事日志 + 成本记账）。"""
    today = date.today()
    start = today - timedelta(days=days - 1)

    log_rows = (
        db.query(
            FarmLog.operation_date.label("d"),
            func.count(FarmLog.id).label("c"),
        )
        .filter(FarmLog.operation_date.between(start, today))
        .group_by(FarmLog.operation_date)
        .all()
    )
    cost_rows = (
        db.query(
            CostRecord.record_date.label("d"),
            func.count(CostRecord.id).label("c"),
        )
        .filter(
            CostRecord.record_date.between(start, today),
            CostRecord.deleted_at.is_(None),
        )
        .group_by(CostRecord.record_date)
        .all()
    )

    counts = {start + timedelta(days=i): 0 for i in range(days)}
    for row in [*log_rows, *cost_rows]:
        if row.d in counts:
            counts[row.d] += row.c

    return {
        "days": [
            {"date": d.isoformat(), "count": counts[d]}
            for d in sorted(counts)
        ]
    }


def _mask_phone(phone: str | None) -> str:
    if not phone or len(phone) < 7:
        return phone or ""
    return f"{phone[:3]}****{phone[-4:]}"


@router.get("/active-users")
def dashboard_active_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    """今日活跃用户列表（基于会话最后活跃时间）。"""
    today_start = datetime.combine(date.today(), time.min)

    rows = (
        db.query(
            User.id.label("user_id"),
            User.nickname,
            User.phone,
            func.max(Conversation.last_active_at).label("last_active_at"),
            func.max(Farm.name).label("farm_name"),
        )
        .join(Conversation, Conversation.user_id == User.id)
        .outerjoin(Farm, Farm.user_id == User.id)
        .filter(
            Conversation.last_active_at >= today_start,
            Conversation.user_id.isnot(None),
        )
        .group_by(User.id, User.nickname, User.phone)
        .order_by(func.max(Conversation.last_active_at).desc())
        .all()
    )

    return {
        "items": [
            {
                "user_id": row.user_id,
                "nickname": row.nickname,
                "phone_masked": _mask_phone(row.phone),
                "last_active_at": row.last_active_at.isoformat()
                if row.last_active_at
                else None,
                "farm_name": row.farm_name,
            }
            for row in rows
        ]
    }


__all__ = ["router"]
