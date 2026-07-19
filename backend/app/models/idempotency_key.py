"""幂等键模型 — 防止重复解析请求。"""

from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from app.shared.database import Base


class IdempotencyKey(Base):
    """幂等键缓存。"""

    __tablename__ = "idempotency_keys"

    key = Column(String(64), primary_key=True)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


def cleanup_old_keys(db=None, hours: int = 24) -> None:
    """删除 N 小时前的幂等键。"""
    import logging
    from datetime import timedelta

    logger = logging.getLogger(__name__)
    if db is None:
        return
    try:
        cutoff = datetime.now() - timedelta(hours=hours)
        db.query(IdempotencyKey).filter(IdempotencyKey.created_at < cutoff).delete(
            synchronize_session=False
        )
        db.commit()
        logger.info("幂等键清理完成 | cutoff=%s", cutoff)
    except Exception:
        logger.exception("幂等键清理失败")


__all__ = ["IdempotencyKey", "cleanup_old_keys"]
