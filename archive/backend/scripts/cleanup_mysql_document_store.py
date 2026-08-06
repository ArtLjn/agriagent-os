"""MongoDB 文档存储三期 MySQL 清库 CLI。"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.infra.mongo import create_mongo_client
from app.core.config import settings
from app.infra.mysql_document_cleanup import (
    build_plan,
    cleanup_table,
    create_backup,
    load_verify_report,
    post_verify,
    rollback_import,
    write_report,
)
from app.infra.mysql_document_cleanup_types import CleanupError, table_names

DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "var" / "mongodb-cleanup"


async def _run(args: argparse.Namespace) -> int:
    db = SessionLocal()
    database = _connect_database() if args.command in {"plan", "post-verify"} else None
    try:
        if args.command == "plan":
            rows = await build_plan(
                db,
                database,
                tables=_selected_tables(args.table),
                verify_reports=_load_verify_reports(args.verify_report_dir),
            )
            payload = {"tables": [row.to_dict() for row in rows]}
            _print_json(payload)
            _write_optional_report(args.report_dir, "plan", payload)
            return 0
        if args.command == "backup":
            result = create_backup(
                db,
                table=args.table,
                output_dir=Path(args.output_dir),
            )
            _print_json(result.to_dict())
            return 0
        if args.command == "cleanup":
            verify_report = (
                load_verify_report(Path(args.verify_report), table=args.table)
                if args.execute
                else None
            )
            result = cleanup_table(
                db,
                table=args.table,
                strategy=args.strategy,
                execute=args.execute,
                backup_file=Path(args.backup_file) if args.backup_file else None,
                confirm_token=args.confirm_token,
                verify_report=verify_report,
                batch_size=args.batch_size,
                sleep_seconds=args.sleep_ms / 1000,
            )
            _print_json(result.to_dict())
            _write_optional_report(args.report_dir, "cleanup", result.to_dict())
            return 0 if not result.stopped_on_error else 2
        if args.command == "post-verify":
            result = await post_verify(
                db,
                database,
                table=args.table,
                strategy=args.strategy,
                expected_mongo_count=args.expected_mongo_count,
            )
            _print_json(result)
            _write_optional_report(args.report_dir, "post-verify", result)
            return 0 if result["ok"] else 3
        if args.command == "rollback-import":
            result = rollback_import(
                db,
                table=args.table,
                backup_file=Path(args.backup_file),
                execute=args.execute,
                confirm_token=args.confirm_token,
            )
            _print_json(result.to_dict())
            _write_optional_report(args.report_dir, "rollback-import", result.to_dict())
            return 0
        raise ValueError(f"未知命令: {args.command}")
    except CleanupError as exc:
        _print_json({"code": exc.code, **exc.context})
        return 4
    finally:
        db.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MongoDB 三期 MySQL 文档表清库工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan", help="生成清库计划，不修改数据库")
    plan.add_argument("--table", default="all")
    plan.add_argument("--verify-report-dir")
    _add_report_dir(plan)

    backup = subparsers.add_parser("backup", help="导出目标表 JSONL 备份")
    _add_table_arg(backup)
    backup.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR / "backups"),
        help="默认位于 backend/var/mongodb-cleanup/backups",
    )

    cleanup = subparsers.add_parser("cleanup", help="清理 dry-run 或显式 execute")
    _add_table_arg(cleanup)
    cleanup.add_argument("--strategy", required=True, choices=("delete", "slim"))
    cleanup.add_argument("--execute", action="store_true")
    cleanup.add_argument("--backup-file")
    cleanup.add_argument("--verify-report")
    cleanup.add_argument("--confirm-token")
    cleanup.add_argument("--batch-size", type=int, default=500)
    cleanup.add_argument("--sleep-ms", type=int, default=0)
    _add_report_dir(cleanup)

    post = subparsers.add_parser("post-verify", help="清理后校验")
    _add_table_arg(post)
    post.add_argument("--strategy", choices=("delete", "slim"))
    post.add_argument("--expected-mongo-count", type=int)
    _add_report_dir(post)

    rollback = subparsers.add_parser("rollback-import", help="从 JSONL 备份恢复")
    _add_table_arg(rollback)
    rollback.add_argument("--backup-file", required=True)
    rollback.add_argument("--execute", action="store_true")
    rollback.add_argument("--confirm-token")
    _add_report_dir(rollback)
    return parser.parse_args(argv)


def _add_table_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--table", required=True, choices=table_names())


def _add_report_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--report-dir",
        default=str(DEFAULT_OUTPUT_DIR / "reports"),
        help="清库审计报告目录",
    )


def _selected_tables(table: str) -> list[str] | None:
    return None if table == "all" else [table]


def _load_verify_reports(report_dir: str | None) -> dict[str, dict[str, Any]]:
    if not report_dir:
        return {}
    reports: dict[str, dict[str, Any]] = {}
    for path in Path(report_dir).glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        table = payload.get("table")
        if isinstance(table, str):
            reports[table] = payload
    return reports


def _connect_database() -> Any | None:
    if not settings.mongodb.enabled:
        return None
    client = create_mongo_client(settings.mongodb)
    return client[settings.mongodb.database]


def _write_optional_report(
    report_dir: str | None, prefix: str, payload: dict[str, Any]
) -> None:
    if report_dir:
        write_report(payload, Path(report_dir), prefix=prefix)


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str, indent=2))


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_run(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
