"""MongoDB 文档迁移后三期 MySQL 清库工具核心逻辑。"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import null, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infra.mysql_document_cleanup_types import (
    BackupResult,
    CleanupError,
    CleanupResult,
    CleanupTable,
    PlanRow,
    RollbackResult,
    confirmation_token,
    deserialize_row,
    require_allowed_table,
    serialize_row,
    sha256_file,
    table_names,
)
from app.models.conversation import ConversationMessage
from app.models.mongo_compensation import MongoCompensationTask

BACKLOG_STATUSES = ("pending", "failed")


async def build_plan(
    db: Session,
    database: Any | None,
    *,
    tables: list[str] | None = None,
    backend_overrides: dict[str, str] | None = None,
    verify_reports: dict[str, dict[str, Any]] | None = None,
) -> list[PlanRow]:
    selected = tables or table_names()
    return [
        await _plan_one(
            db,
            database,
            table=table,
            backend_overrides=backend_overrides,
            verify_reports=verify_reports,
        )
        for table in selected
    ]


def create_backup(db: Session, *, table: str, output_dir: Path) -> BackupResult:
    plan = require_allowed_table(table)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_file = output_dir / f"{table}-{timestamp}.jsonl"
    rows = db.query(plan.model).order_by(plan.model.id.asc()).all()
    with backup_file.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(serialize_row(row), ensure_ascii=False) + "\n")
    sha256 = sha256_file(backup_file)
    metadata_file = _write_backup_metadata(table, backup_file, len(rows), sha256)
    return BackupResult(
        table=table,
        row_count=len(rows),
        backup_file=str(backup_file),
        metadata_file=str(metadata_file),
        sha256=sha256,
        cleanup_confirm_token=confirmation_token("CLEANUP", table, sha256),
        rollback_confirm_token=confirmation_token("ROLLBACK", table, sha256),
    )


def cleanup_table(
    db: Session,
    *,
    table: str,
    strategy: str | None = None,
    execute: bool = False,
    backup_file: Path | None = None,
    confirm_token: str | None = None,
    verify_report: dict[str, Any] | None = None,
    backend_overrides: dict[str, str] | None = None,
    batch_size: int = 500,
    sleep_seconds: float = 0,
) -> CleanupResult:
    plan = require_allowed_table(table)
    selected_strategy = strategy or plan.default_strategy
    _validate_strategy(table, selected_strategy)
    total = _target_count(db, plan, selected_strategy)
    batches = math.ceil(total / max(batch_size, 1)) if total else 0
    if not execute:
        return CleanupResult(
            table, "dry-run", selected_strategy, total, 0, batch_size, batches
        )
    sha256 = _require_execute_guards(
        db,
        table=table,
        plan=plan,
        backup_file=backup_file,
        confirm_token=confirm_token,
        verify_report=verify_report,
        backend_overrides=backend_overrides,
    )
    return _execute_cleanup(
        db,
        plan=plan,
        table=table,
        strategy=selected_strategy,
        planned_count=total,
        batch_size=batch_size,
        batches=batches,
        backup_sha256=sha256,
        sleep_seconds=sleep_seconds,
    )


async def post_verify(
    db: Session,
    database: Any | None,
    *,
    table: str,
    strategy: str | None = None,
    expected_mongo_count: int | None = None,
) -> dict[str, Any]:
    plan = require_allowed_table(table)
    selected_strategy = strategy or plan.default_strategy
    mysql_count = db.query(plan.model).count()
    mongo_count = await _mongo_count(database, plan.collection)
    mysql_ok = mysql_count == 0
    if selected_strategy == "slim":
        mysql_ok = _slimmed_count(db) == mysql_count
    mongo_ok = expected_mongo_count is None or (
        mongo_count is not None and mongo_count >= expected_mongo_count
    )
    return {
        "table": table,
        "strategy": selected_strategy,
        "mysql_count": mysql_count,
        "mongo_count": mongo_count,
        "ok": bool(mysql_ok and mongo_ok),
    }


def rollback_import(
    db: Session,
    *,
    table: str,
    backup_file: Path,
    execute: bool = False,
    confirm_token: str | None = None,
) -> RollbackResult:
    plan = require_allowed_table(table)
    sha256 = sha256_file(_require_backup_file(backup_file))
    if execute and confirm_token != confirmation_token("ROLLBACK", table, sha256):
        raise CleanupError("MYSQL_CLEANUP_CONFIRMATION_REQUIRED", table=table)
    result = RollbackResult(table, "execute" if execute else "dry-run", 0, 0, 0, sha256)
    for payload in _read_backup_rows(backup_file):
        result.scanned += 1
        if _row_exists(db, plan, payload):
            result.skipped_existing += 1
            continue
        if execute:
            db.add(plan.model(**deserialize_row(plan.model, payload)))
            result.inserted += 1
    if execute:
        db.commit()
    return result


def write_report(payload: dict[str, Any], output_dir: Path, *, prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = dict(payload)
    report["generated_at"] = datetime.now().isoformat()
    path = output_dir / f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_verify_report(path: Path | None, *, table: str) -> dict[str, Any]:
    if path is None or not path.exists():
        raise CleanupError("MYSQL_CLEANUP_VERIFY_REQUIRED", table=table)
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("table") != table or report.get("ok") is not True:
        raise CleanupError("MYSQL_CLEANUP_VERIFY_REQUIRED", table=table)
    return report


async def _plan_one(
    db: Session,
    database: Any | None,
    *,
    table: str,
    backend_overrides: dict[str, str] | None,
    verify_reports: dict[str, dict[str, Any]] | None,
) -> PlanRow:
    plan = require_allowed_table(table)
    verify = (verify_reports or {}).get(table, {})
    row = PlanRow(
        table=table,
        strategy=plan.default_strategy,
        mysql_count=db.query(plan.model).count(),
        mongo_count=await _mongo_count(database, plan.collection),
        backend=_backend_for(plan, backend_overrides),
        verify_status="passed" if verify.get("ok") is True else "missing_or_failed",
        compensation_backlog=_compensation_backlog(db, plan.object_type),
    )
    _append_plan_blocks(row)
    return row


def _write_backup_metadata(
    table: str, backup_file: Path, row_count: int, sha256: str
) -> Path:
    metadata = {
        "table": table,
        "row_count": row_count,
        "backup_file": str(backup_file),
        "sha256": sha256,
        "created_at": datetime.now().isoformat(),
        "format": "jsonl",
    }
    metadata_file = backup_file.with_suffix(".metadata.json")
    metadata_file.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata_file


def _append_plan_blocks(row: PlanRow) -> None:
    if row.backend != "mongo":
        row.blocked_reasons.append(
            {"code": "MYSQL_CLEANUP_BACKEND_NOT_MONGO", "backend": row.backend}
        )
    if row.verify_status != "passed":
        row.blocked_reasons.append({"code": "MYSQL_CLEANUP_VERIFY_REQUIRED"})
    if row.compensation_backlog:
        row.blocked_reasons.append(
            {
                "code": "MYSQL_CLEANUP_COMPENSATION_BACKLOG",
                "count": row.compensation_backlog,
            }
        )


async def _mongo_count(database: Any | None, collection: str) -> int | None:
    if database is None:
        return None
    return int(await database[collection].count_documents({}))


def _backend_for(plan: CleanupTable, overrides: dict[str, str] | None) -> str:
    if overrides and plan.storage_key in overrides:
        return overrides[plan.storage_key]
    return str(getattr(settings.storage, plan.storage_key))


def _compensation_backlog(db: Session, object_type: str) -> int:
    return (
        db.query(MongoCompensationTask)
        .filter(
            MongoCompensationTask.object_type == object_type,
            MongoCompensationTask.status.in_(BACKLOG_STATUSES),
        )
        .count()
    )


def _target_count(db: Session, plan: CleanupTable, strategy: str) -> int:
    if plan.model is ConversationMessage and strategy == "slim":
        return (
            db.query(ConversationMessage)
            .filter(_conversation_message_has_body())
            .count()
        )
    return db.query(plan.model).count()


def _conversation_message_has_body() -> Any:
    return or_(
        ConversationMessage.content != "",
        ConversationMessage.meta.is_not(None),
        ConversationMessage.meta_json.is_not(None),
    )


def _slimmed_count(db: Session) -> int:
    return (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.content == "",
            ConversationMessage.meta.is_(None),
            ConversationMessage.meta_json.is_(None),
        )
        .count()
    )


def _validate_strategy(table: str, strategy: str) -> None:
    allowed = {"slim"} if table == "conversation_messages" else {"delete"}
    if strategy not in allowed:
        raise CleanupError(
            "MYSQL_CLEANUP_STRATEGY_NOT_ALLOWED", table=table, strategy=strategy
        )


def _require_execute_guards(
    db: Session,
    *,
    table: str,
    plan: CleanupTable,
    backup_file: Path | None,
    confirm_token: str | None,
    verify_report: dict[str, Any] | None,
    backend_overrides: dict[str, str] | None,
) -> str:
    if _backend_for(plan, backend_overrides) != "mongo":
        raise CleanupError("MYSQL_CLEANUP_BACKEND_NOT_MONGO", table=table)
    if (
        not verify_report
        or verify_report.get("table") != table
        or not verify_report.get("ok")
    ):
        raise CleanupError("MYSQL_CLEANUP_VERIFY_REQUIRED", table=table)
    backlog = _compensation_backlog(db, plan.object_type)
    if backlog:
        raise CleanupError(
            "MYSQL_CLEANUP_COMPENSATION_BACKLOG", table=table, count=backlog
        )
    backup = _require_backup_file(backup_file)
    sha256 = sha256_file(backup)
    if confirm_token != confirmation_token("CLEANUP", table, sha256):
        raise CleanupError("MYSQL_CLEANUP_CONFIRMATION_REQUIRED", table=table)
    return sha256


def _require_backup_file(path: Path | None) -> Path:
    if path is None or not path.exists():
        raise CleanupError("MYSQL_CLEANUP_BACKUP_REQUIRED")
    return path


def _execute_cleanup(
    db: Session,
    *,
    plan: CleanupTable,
    table: str,
    strategy: str,
    planned_count: int,
    batch_size: int,
    batches: int,
    backup_sha256: str,
    sleep_seconds: float,
) -> CleanupResult:
    result = CleanupResult(
        table, "execute", strategy, planned_count, 0, batch_size, batches, backup_sha256
    )
    try:
        while True:
            ids = _next_cleanup_ids(db, plan, strategy, batch_size)
            if not ids:
                break
            result.affected_count += _apply_batch(db, plan, strategy, ids)
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
    except Exception as exc:
        db.rollback()
        result.stopped_on_error = True
        result.errors.append(
            {"code": "MYSQL_CLEANUP_BATCH_FAILED", "error": str(exc)[:300]}
        )
    return result


def _next_cleanup_ids(
    db: Session, plan: CleanupTable, strategy: str, batch_size: int
) -> list[int]:
    query = db.query(plan.model.id)
    if plan.model is ConversationMessage and strategy == "slim":
        query = query.filter(_conversation_message_has_body())
    return [
        row_id for (row_id,) in query.order_by(plan.model.id.asc()).limit(batch_size)
    ]


def _apply_batch(db: Session, plan: CleanupTable, strategy: str, ids: list[int]) -> int:
    if strategy == "delete":
        affected = (
            db.query(plan.model)
            .filter(plan.model.id.in_(ids))
            .delete(synchronize_session=False)
        )
    else:
        affected = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.id.in_(ids))
            .update(
                {
                    ConversationMessage.content: "",
                    ConversationMessage.meta: None,
                    ConversationMessage.meta_json: null(),
                },
                synchronize_session=False,
            )
        )
    db.commit()
    return int(affected)


def _read_backup_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _row_exists(db: Session, plan: CleanupTable, payload: dict[str, Any]) -> bool:
    primary_id = payload.get("id")
    return primary_id is not None and db.get(plan.model, primary_id) is not None
