"""Token 配额检查 Service（从 archive quota_service.py 复用并简化）。

archive 版本依赖 TokenDailyStats（MongoDB 聚合），agri_backend_v2 暂未实现该统计层，
这里提供简化版本：
  - get_user_quota_limits: 获取用户配额限制
  - check_user_quota: 校验配额（当前总是 allowed=True，待接入 TokenDailyStats 后启用）

后续接入 agent trace 数据后，可基于 trace 的 token_usage 字段聚合。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from business.config import settings
from business.models import User

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
    """返回当月 [start, end] 日期。"""
    current = today or date.today()
    start = current.replace(day=1)
    if current.month == 12:
        next_month = current.replace(year=current.year + 1, month=1, day=1)
    else:
        next_month = current.replace(month=current.month + 1, day=1)
    return start, next_month - timedelta(days=1)


def get_week_range(today: date | None = None) -> tuple[date, date]:
    """返回本周 [start, end] 日期（周一开始）。"""
    current = today or date.today()
    start = current - timedelta(days=current.weekday())
    return start, start + timedelta(days=6)


def get_user_quota_limits(user_id: str, db: Session) -> QuotaLimits:
    """读取用户配额限制，未自定义则用 config.token_quota 默认值。"""
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


def get_period_usage(
    user_id: str, start: date, end: date, db: Session
) -> int:
    """查询某时段内的 Token 使用量。

    agri_backend_v2 暂未实现 TokenDailyStats 统计层，返回 0。
    TODO: 后续基于 agent trace 的 token_usage 聚合。
    """
    return 0


def check_user_quota(
    user_id: str | None,
    db: Session,
    today: date | None = None,
) -> QuotaCheckResult:
    """校验用户配额。

    agri_backend_v2 简化版本：未接入 TokenDailyStats，总是返回 allowed=True。
    后续接入 trace 数据后实现真实检查。
    """
    if not user_id:
        return QuotaCheckResult(allowed=False, exceeded_period="identity")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return QuotaCheckResult(allowed=False, exceeded_period="identity")

    current = today or date.today()
    month_start, _ = get_month_range(current)
    _, week_end = get_week_range(current)
    limits = get_user_quota_limits(user_id, db)
    monthly_usage = get_period_usage(user_id, month_start, current, db)
    weekly_usage = get_period_usage(user_id, week_end - timedelta(days=6), current, db)

    result = QuotaCheckResult(
        allowed=True,
        monthly_usage=monthly_usage,
        monthly_limit=limits.monthly_limit,
        monthly_remaining=max(0, limits.monthly_limit - monthly_usage),
        weekly_usage=weekly_usage,
        weekly_limit=limits.weekly_limit,
        weekly_remaining=max(0, limits.weekly_limit - weekly_usage),
    )

    # 真实检查（待 TokenDailyStats 接入后启用）
    # if monthly_usage >= limits.monthly_limit:
    #     result.allowed = False
    #     result.exceeded_period = "month"
    #     result.reset_at = (month_end + timedelta(days=1)).isoformat()
    # elif weekly_usage >= limits.weekly_limit:
    #     result.allowed = False
    #     result.exceeded_period = "week"
    #     result.reset_at = (week_end + timedelta(days=1)).isoformat()
    return result


__all__ = [
    "QuotaCheckResult",
    "QuotaLimits",
    "check_user_quota",
    "get_month_range",
    "get_period_usage",
    "get_user_quota_limits",
    "get_week_range",
]
