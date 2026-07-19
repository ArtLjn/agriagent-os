"""Token 配额检查服务。"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.shared.config import settings
from app.shared.database import SessionLocal
from app.models.farm import Farm
from app.models.token_stats import TokenDailyStats
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass
class QuotaLimits:
    monthly_limit: int
    weekly_limit: int


@dataclass
class QuotaCheckResult:
    allowed: bool
    exceeded_period: str | None = None
    monthly_usage: int = 0
    monthly_limit: int = 0
    monthly_remaining: int = 0
    weekly_usage: int = 0
    weekly_limit: int = 0
    weekly_remaining: int = 0
    reset_at: str | None = None


def get_month_range(today: date | None = None) -> tuple[date, date]:
    current = today or date.today()
    start = current.replace(day=1)
    if current.month == 12:
        next_month = current.replace(year=current.year + 1, month=1, day=1)
    else:
        next_month = current.replace(month=current.month + 1, day=1)
    return start, next_month - timedelta(days=1)


def get_week_range(today: date | None = None) -> tuple[date, date]:
    current = today or date.today()
    start = current - timedelta(days=current.weekday())
    return start, start + timedelta(days=6)


def get_user_quota_limits(user_id: str, db: Session) -> QuotaLimits:
    user = db.query(User).filter(User.id == user_id).first()
    monthly = (
        user.token_monthly_limit
        if user and user.token_monthly_limit is not None
        else None
    )
    weekly = (
        user.token_weekly_limit
        if user and user.token_weekly_limit is not None
        else None
    )
    return QuotaLimits(
        monthly_limit=monthly
        if monthly is not None
        else settings.token_quota.monthly_limit,
        weekly_limit=weekly
        if weekly is not None
        else settings.token_quota.weekly_limit,
    )


def get_period_usage(user_id: str, start: date, end: date, db: Session) -> int:
    total = (
        db.query(func.coalesce(func.sum(TokenDailyStats.total_tokens), 0))
        .filter(
            TokenDailyStats.user_id == user_id,
            TokenDailyStats.date >= start.isoformat(),
            TokenDailyStats.date <= end.isoformat(),
        )
        .scalar()
    )
    return int(total or 0)


def check_user_quota(
    user_id: str | None,
    db: Session,
    today: date | None = None,
) -> QuotaCheckResult:
    if not user_id:
        return QuotaCheckResult(allowed=False, exceeded_period="identity")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return QuotaCheckResult(allowed=False, exceeded_period="identity")

    current = today or date.today()
    month_start, month_end = get_month_range(current)
    week_start, week_end = get_week_range(current)
    limits = get_user_quota_limits(user_id, db)
    monthly_usage = get_period_usage(user_id, month_start, month_end, db)
    weekly_usage = get_period_usage(user_id, week_start, week_end, db)

    result = QuotaCheckResult(
        allowed=True,
        monthly_usage=monthly_usage,
        monthly_limit=limits.monthly_limit,
        monthly_remaining=max(0, limits.monthly_limit - monthly_usage),
        weekly_usage=weekly_usage,
        weekly_limit=limits.weekly_limit,
        weekly_remaining=max(0, limits.weekly_limit - weekly_usage),
    )
    if monthly_usage >= limits.monthly_limit:
        result.allowed = False
        result.exceeded_period = "month"
        result.reset_at = (month_end + timedelta(days=1)).isoformat()
    elif weekly_usage >= limits.weekly_limit:
        result.allowed = False
        result.exceeded_period = "week"
        result.reset_at = (week_end + timedelta(days=1)).isoformat()
    return result


def check_quota(farm_id: int) -> bool:
    db = SessionLocal()
    try:
        farm = db.query(Farm).filter(Farm.id == farm_id).first()
        result = check_user_quota(farm.user_id if farm else None, db)
        if not result.allowed:
            logger.warning(
                "Token 配额超限 | farm=%s user=%s period=%s action=%s",
                farm_id,
                farm.user_id if farm else "-",
                result.exceeded_period,
                settings.token_quota.over_quota_action,
            )
        return result.allowed
    finally:
        db.close()


__all__ = [
    "QuotaCheckResult",
    "QuotaLimits",
    "check_quota",
    "check_user_quota",
    "get_month_range",
    "get_period_usage",
    "get_user_quota_limits",
    "get_week_range",
]
