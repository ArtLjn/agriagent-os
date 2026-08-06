"""SQLAlchemy engine + Session factory.

每个 MCP tool 调用都通过 SessionLocal 拿一个短生命 session（FastMCP tool 是同步函数）。
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from business.config import settings
from business.models import Base

logger = logging.getLogger(__name__)

# 从 config 读默认 farm_id（archive 习惯：farm_id=2 是"管理员农场"）。
DEFAULT_FARM_ID = settings.default_farm_id


def _build_engine():
    if not settings.database.url:
        raise RuntimeError(
            "database.url is empty; configure v2/config.yaml or DATABASE__URL env"
        )
    cfg = settings.database
    return create_engine(
        cfg.url,
        pool_size=cfg.pool_size,
        max_overflow=cfg.max_overflow,
        pool_recycle=cfg.pool_recycle,
        pool_pre_ping=True,  # 避免 MySQL wait_timeout 后第一次调用报错
        echo=cfg.echo,
        future=True,
    )


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transaction scope.

    用法：
        with session_scope() as db:
            ...query...
    自动 commit / rollback / close。
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_connection() -> None:
    """启动时调用一次，确认 DB 可达。"""
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("database connection ok: %s", settings.database.url.split("@")[-1])
