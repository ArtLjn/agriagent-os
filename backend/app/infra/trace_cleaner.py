"""Trace TTL 自动清理。"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.exc import ProgrammingError

from app.shared.config import settings
from app.shared.database import SessionLocal
from app.models.token_stats import TokenDailyStats
from app.models.trace import TraceRecord

logger = logging.getLogger(__name__)


def clean_expired_traces() -> dict[str, int]:
    """清理过期的 trace 和 token 统计数据。"""
    trace_cutoff = datetime.now() - timedelta(days=settings.trace.trace_ttl_days)
    stats_cutoff = datetime.now() - timedelta(days=settings.trace.token_stats_ttl_days)

    db = SessionLocal()
    try:
        trace_deleted = _delete_expired_trace_records(db, trace_cutoff)
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


def _delete_expired_trace_records(db, trace_cutoff: datetime) -> int:
    try:
        return int(
            db.query(TraceRecord)
            .filter(TraceRecord.created_at < trace_cutoff)
            .delete(synchronize_session=False)
            or 0
        )
    except ProgrammingError as exc:
        if not _is_missing_table_error(exc):
            raise
        db.rollback()
        logger.warning(
            "Trace TTL 跳过缺失的 MySQL 表 | code=trace_records_table_missing"
        )
        return 0


def _is_missing_table_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "trace_records" in message and (
        "doesn't exist" in message
        or "does not exist" in message
        or "no such table" in message
        or "missing table" in message
    )


__all__ = ["clean_expired_traces"]
