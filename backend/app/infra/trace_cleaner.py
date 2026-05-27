"""Trace TTL 自动清理。"""

import logging
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.token_stats import TokenDailyStats
from app.models.trace import TraceRecord

logger = logging.getLogger(__name__)


def clean_expired_traces() -> dict[str, int]:
    """清理过期的 trace 和 token 统计数据。"""
    trace_cutoff = datetime.now() - timedelta(days=settings.trace.trace_ttl_days)
    stats_cutoff = datetime.now() - timedelta(days=settings.trace.token_stats_ttl_days)

    db = SessionLocal()
    try:
        trace_deleted = (
            db.query(TraceRecord)
            .filter(TraceRecord.created_at < trace_cutoff)
            .delete(synchronize_session=False)
        )
        stats_deleted = (
            db.query(TokenDailyStats)
            .filter(TokenDailyStats.created_at < stats_cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info(
            "TTL 清理完成 | trace_deleted=%d stats_deleted=%d",
            trace_deleted,
            stats_deleted,
        )
        return {
            "trace_records_deleted": trace_deleted,
            "token_stats_deleted": stats_deleted,
        }
    except Exception:
        db.rollback()
        logger.exception("TTL 清理失败")
        return {"trace_records_deleted": 0, "token_stats_deleted": 0}
    finally:
        db.close()


__all__ = ["clean_expired_traces"]
