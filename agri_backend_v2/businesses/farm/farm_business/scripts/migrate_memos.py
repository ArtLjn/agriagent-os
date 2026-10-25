"""检查备忘录表；--apply 仅创建缺失表，不修改已有表或数据。"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from farm_business.models import Memo

logger = logging.getLogger(__name__)
MIGRATION = (
    Path(__file__).resolve().parents[1] / "migrations/20261023_memos_up.sql"
)
LOCK_NAME = "farm_manager:memos:20261023"
LOCK_TIMEOUT_SECONDS = 30


def check_schema(connection: Connection) -> None:
    """已有表也需验证列和隔离/幂等约束，不能把部分建表当作迁移成功。"""
    inspector = inspect(connection)
    if not inspector.has_table("memos"):
        raise RuntimeError(
            "memo_schema_missing: 请运行 python -B -m farm_business.scripts.migrate_memos --apply"
        )
    columns = {column["name"]: column for column in inspector.get_columns("memos")}
    for column in Memo.__table__.columns:
        actual = columns.get(column.name)
        if actual is None or actual["nullable"] != column.nullable:
            raise RuntimeError(
                f"memo_schema_mismatch: 列 {column.name} 缺失或可空约束不匹配"
            )
    primary = inspector.get_pk_constraint("memos")["constrained_columns"]
    unique = {
        tuple(item["column_names"])
        for item in inspector.get_unique_constraints("memos")
    }
    indexes = {tuple(item["column_names"]) for item in inspector.get_indexes("memos")}
    foreign = {
        (
            tuple(item["constrained_columns"]),
            item["referred_table"],
            tuple(item["referred_columns"]),
        )
        for item in inspector.get_foreign_keys("memos")
    }
    if (
        primary != ["id"]
        or ("farm_id", "user_id", "client_request_id") not in unique
        or ("farm_id", "user_id", "archived", "pinned", "updated_at") not in indexes
        or not {(("farm_id",), "farms", ("id",)), (("user_id",), "users", ("id",))}
        <= foreign
    ):
        raise RuntimeError(
            "memo_schema_mismatch: 主键、索引或外键与备忘录模型不一致，请人工检查"
        )


def migrate(engine: Engine, *, apply: bool = False) -> str:
    """MySQL 命名锁防止并发部署重复建表；DDL 自动提交，回滚代码时保留新表。"""
    if engine.dialect.name != "mysql":
        raise RuntimeError("memo_migration_unsupported: 此增量迁移仅支持 MySQL")
    with engine.connect() as connection:
        if not apply:
            check_schema(connection)
            return "ready"
        locked = connection.scalar(
            text("SELECT GET_LOCK(:name, :timeout)"),
            {"name": LOCK_NAME, "timeout": LOCK_TIMEOUT_SECONDS},
        )
        if locked != 1:
            raise RuntimeError("memo_migration_busy: 未获得迁移锁，请稍后重试")
        try:
            exists = inspect(connection).has_table("memos")
            if not exists:
                connection.exec_driver_sql(MIGRATION.read_text(encoding="utf-8"))
                connection.commit()
            check_schema(connection)
            return "ready" if exists else "created"
        finally:
            connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": LOCK_NAME})


def main() -> None:
    """部署入口沿用 Business 配置；失败只记录错误类型，不输出连接串或 SQL 参数。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    from farm_business.db import engine

    try:
        status = migrate(engine, apply=args.apply)
    except (SQLAlchemyError, RuntimeError) as exc:
        logger.error(
            "memo_migration_failed",
            extra={"code": "memo_migration_failed", "error_type": type(exc).__name__},
        )
        # 自有校验消息不含数据库原始异常；驱动异常由管理员检查数据库状态。
        raise SystemExit(
            str(exc)
            if isinstance(exc, RuntimeError)
            else "memo_migration_failed: 数据库迁移失败，请检查表结构及权限"
        ) from None
    logger.info("memo_migration_%s", status, extra={"code": "memo_migration_ready"})


if __name__ == "__main__":
    main()
