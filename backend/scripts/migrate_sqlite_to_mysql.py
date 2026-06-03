"""SQLite 到 MySQL 数据迁移脚本。

用法:
    python scripts/migrate_sqlite_to_mysql.py \
        --source ./farm_manager.db \
        --target "mysql+pymysql://user:pass@host:3306/farm_manager?charset=utf8mb4"
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

TABLE_ORDER = [
    "users",
    "idempotency_keys",
    "guardrails_logs",
    "trace_records",
    "token_daily_stats",
    "user_settings",
    "cost_categories",
    "simulation_runs",
    "simulation_results",
    "farms",
    "crop_templates",
    "growth_stages",
    "crop_cycles",
    "cycle_stages",
    "farm_logs",
    "cost_records",
    "conversations",
    "conversation_messages",
    "feedback_records",
    "agent_records",
]


def backup_sqlite(source_path: Path) -> Path:
    """备份 SQLite 主数据库文件。"""
    if not source_path.exists():
        raise FileNotFoundError(f"SQLite 文件不存在: {source_path}")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = source_path.with_suffix(source_path.suffix + f".{timestamp}.bak")
    shutil.copy2(source_path, backup_path)
    print(f"已备份 SQLite: {backup_path}")
    return backup_path


def _quote(table: str) -> str:
    return f"`{table}`"


def count_rows(engine: Engine, table: str, quoted: bool = False) -> int:
    table_name = _quote(table) if quoted else table
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar())


def target_has_data(engine: Engine) -> bool:
    inspector = inspect(engine)
    for table in inspector.get_table_names():
        if count_rows(engine, table, quoted=True) > 0:
            return True
    return False


def read_rows(
    session: Session, table: str, where_clause: str | None = None
) -> list[dict]:
    sql = f"SELECT * FROM {table}"
    if where_clause:
        sql = f"{sql} WHERE {where_clause}"
    return [dict(row) for row in session.execute(text(sql)).mappings().all()]


def insert_rows(session: Session, table: str, rows: list[dict]) -> int:
    if not rows:
        return 0

    columns = list(rows[0].keys())
    column_list = ", ".join(_quote(column) for column in columns)
    placeholders = ", ".join(f":{column}" for column in columns)
    session.execute(
        text(f"INSERT INTO {_quote(table)} ({column_list}) VALUES ({placeholders})"),
        rows,
    )
    return len(rows)


def migrate_regular_table(
    source_session: Session,
    target_session: Session,
    table: str,
) -> int:
    rows = read_rows(source_session, table)
    inserted = insert_rows(target_session, table, rows)
    target_session.commit()
    return inserted


def migrate_cost_records(source_session: Session, target_session: Session) -> int:
    root_rows = read_rows(
        source_session,
        "cost_records",
        "parent_record_id IS NULL",
    )
    child_rows = read_rows(
        source_session,
        "cost_records",
        "parent_record_id IS NOT NULL",
    )
    inserted = insert_rows(target_session, "cost_records", root_rows)
    inserted += insert_rows(target_session, "cost_records", child_rows)
    target_session.commit()
    return inserted


def migrate(source_engine: Engine, target_engine: Engine) -> None:
    source_tables = set(inspect(source_engine).get_table_names())
    target_tables = set(inspect(target_engine).get_table_names())
    missing_target = [
        table
        for table in TABLE_ORDER
        if table in source_tables and table not in target_tables
    ]
    if missing_target:
        raise RuntimeError(
            "目标 MySQL 缺少表，请先执行 alembic upgrade head: "
            + ", ".join(missing_target)
        )

    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)

    print("开始迁移数据:")
    total = 0
    for table in TABLE_ORDER:
        if table not in source_tables:
            print(f"  {table}: 源表不存在，跳过")
            continue

        source_session = SourceSession()
        target_session = TargetSession()
        try:
            if table == "cost_records":
                inserted = migrate_cost_records(source_session, target_session)
            else:
                inserted = migrate_regular_table(source_session, target_session, table)
        except Exception:
            target_session.rollback()
            raise
        finally:
            source_session.close()
            target_session.close()

        total += inserted
        print(f"  {table}: {inserted} 行")

    print(f"迁移完成，共 {total} 行")


def verify(source_engine: Engine, target_engine: Engine) -> bool:
    source_tables = set(inspect(source_engine).get_table_names())
    print("校验行数:")
    passed = True
    for table in TABLE_ORDER:
        if table not in source_tables:
            continue
        source_count = count_rows(source_engine, table)
        target_count = count_rows(target_engine, table, quoted=True)
        ok = source_count == target_count
        passed = passed and ok
        status = "OK" if ok else "FAIL"
        print(f"  {status} {table}: SQLite={source_count} MySQL={target_count}")
    return passed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SQLite 到 MySQL 数据迁移")
    parser.add_argument("--source", required=True, help="SQLite 数据库文件路径")
    parser.add_argument("--target", required=True, help="MySQL SQLAlchemy 连接串")
    parser.add_argument("--skip-backup", action="store_true", help="跳过 SQLite 备份")
    parser.add_argument("--force", action="store_true", help="目标库已有数据时仍继续")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_path = Path(args.source).resolve()

    if not args.skip_backup:
        backup_sqlite(source_path)

    source_engine = create_engine(f"sqlite:///{source_path}")
    target_engine = create_engine(args.target, pool_pre_ping=True)
    try:
        if target_has_data(target_engine) and not args.force:
            print("错误: 目标 MySQL 已有数据。确认覆盖风险后加 --force 重试。")
            return 2

        migrate(source_engine, target_engine)
        if verify(source_engine, target_engine):
            print("迁移校验通过")
            return 0

        print("迁移校验失败")
        return 3
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
