"""数据库 WAL 模式和 PRAGMA 配置验证。"""

from sqlalchemy import text

from app.core.database import engine


def test_wal_mode_enabled():
    """连接时自动开启 WAL 模式。"""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert result == "wal"


def test_foreign_keys_enabled():
    """外键约束已开启。"""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA foreign_keys")).scalar()
    assert result == 1


def test_busy_timeout_set():
    """busy_timeout 已设为 5000ms。"""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA busy_timeout")).scalar()
    assert result == 5000
