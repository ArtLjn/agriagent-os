"""Token 配额检查服务。"""

import logging
from datetime import date

from sqlalchemy import func

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.token_stats import TokenDailyStats

logger = logging.getLogger(__name__)


def get_today_usage(farm_id: int) -> int:
    """获取今日 token 用量。"""
    today = date.today().isoformat()
    db = SessionLocal()
    try:
        total = (
            db.query(func.coalesce(func.sum(TokenDailyStats.total_tokens), 0))
            .filter(
                TokenDailyStats.farm_id == farm_id,
                TokenDailyStats.date == today,
            )
            .scalar()
        )
        return int(total)
    finally:
        db.close()


def check_quota(farm_id: int) -> bool:
    """检查是否在配额内。True=可继续调用。"""
    usage = get_today_usage(farm_id)
    limit = settings.token_quota.daily_limit
    if usage >= limit:
        logger.warning(
            "Token 配额超限 | farm=%s usage=%d limit=%d action=%s",
            farm_id,
            usage,
            limit,
            settings.token_quota.over_quota_action,
        )
        return False
    return True


__all__ = ["check_quota", "get_today_usage"]
