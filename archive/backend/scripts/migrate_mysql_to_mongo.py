"""MySQL 与 MongoDB 文档迁移工具。"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import SessionLocal
from app.infra.mongo import create_mongo_client
from app.infra.mongo_mappers import (
    agent_record_to_mongo_doc,
    case_draft_to_mongo_doc,
    conversation_message_to_mongo_doc,
    guardrails_log_to_mongo_doc,
    prelabel_to_mongo_doc,
    repair_pack_to_mongo_doc,
    review_issue_chain_to_mongo_doc,
    trace_record_to_mongo_doc,
)
from app.models.agent_record import AgentRecord
from app.models.conversation import ConversationMessage
from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelPrelabel,
    AgentRepairPack,
    AgentReviewIssueChain,
)
from app.models.guardrails_log import GuardrailsLog
from app.models.trace import TraceRecord


@dataclass(frozen=True)
class TablePlan:
    model: type
    collection: str
    mapper: Any
    business_field: str
    status_field: str | None = None


TABLE_PLANS: dict[str, TablePlan] = {
    "trace_records": TablePlan(
        TraceRecord,
        "traceRecords",
        trace_record_to_mongo_doc,
        "requestId",
        "status",
    ),
    "agent_case_drafts": TablePlan(
        AgentCaseDraft,
        "caseDrafts",
        case_draft_to_mongo_doc,
        "draftId",
        "status",
    ),
    "agent_repair_packs": TablePlan(
        AgentRepairPack,
        "repairPacks",
        repair_pack_to_mongo_doc,
        "packId",
        "status",
    ),
    "agent_review_issue_chains": TablePlan(
        AgentReviewIssueChain,
        "reviewIssueChains",
        review_issue_chain_to_mongo_doc,
        "chainId",
        "status",
    ),
    "agent_data_flywheel_prelabels": TablePlan(
        AgentDataFlywheelPrelabel,
        "prelabels",
        prelabel_to_mongo_doc,
        "sampleId",
        "status",
    ),
    "conversation_messages": TablePlan(
        ConversationMessage,
        "conversationMessages",
        conversation_message_to_mongo_doc,
        "conversationId",
    ),
    "agent_records": TablePlan(
        AgentRecord,
        "agentRecords",
        agent_record_to_mongo_doc,
        "recordType",
    ),
    "guardrails_logs": TablePlan(
        GuardrailsLog,
        "guardrailsLogs",
        guardrails_log_to_mongo_doc,
        "triggerType",
    ),
}


@dataclass
class MigrationStats:
    scanned: int = 0
    written: int = 0
    skipped: int = 0
    failed: int = 0
    failed_ranges: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConsistencyReport:
    table: str
    mysql_count: int
    mongo_count: int
    missing_mysql_ids: list[int]
    mismatches: list[dict[str, Any]]
    mismatch_rate: float
    ok: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def table_names() -> list[str]:
    return list(TABLE_PLANS)


async def backfill_table(
    db: Session,
    database: Any,
    *,
    table: str,
    batch_size: int = 500,
    start_id: int = 0,
    end_id: int | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    retry: int = 2,
    dry_run: bool = False,
) -> MigrationStats:
    """按 MySQL id 升序幂等回填单表。"""
    plan = TABLE_PLANS[table]
    stats = MigrationStats()
    last_id = start_id
    while True:
        rows = _next_batch(
            db,
            plan,
            last_id=last_id,
            batch_size=batch_size,
            end_id=end_id,
            since=since,
            until=until,
        )
        if not rows:
            break
        stats.scanned += len(rows)
        last_id = int(rows[-1].id)
        if dry_run:
            stats.skipped += len(rows)
            continue
        docs = [plan.mapper(row) for row in rows]
        try:
            await _write_docs(database[plan.collection], docs, retry=retry)
            stats.written += len(docs)
        except Exception as exc:
            stats.failed += len(docs)
            stats.failed_ranges.append(
                {
                    "start_id": int(rows[0].id),
                    "end_id": int(rows[-1].id),
                    "error": str(exc)[:300],
                }
            )
    return stats


async def verify_table(
    db: Session,
    database: Any,
    *,
    table: str,
    sample_size: int = 20,
    mismatch_threshold: float | None = None,
) -> ConsistencyReport:
    """校验 MySQL 与 Mongo 文档数量、缺失 mysqlId 和关键字段。"""
    plan = TABLE_PLANS[table]
    collection = database[plan.collection]
    mysql_ids = [
        row_id for (row_id,) in db.query(plan.model.id).order_by(plan.model.id)
    ]
    mongo_docs = await collection.find({"mysqlId": {"$in": mysql_ids}}).to_list(None)
    mongo_by_id = {int(doc["mysqlId"]): doc for doc in mongo_docs if "mysqlId" in doc}
    missing = [row_id for row_id in mysql_ids if row_id not in mongo_by_id]
    mismatches = _sample_mismatches(
        db,
        plan=plan,
        mysql_ids=mysql_ids,
        mongo_by_id=mongo_by_id,
        sample_size=sample_size,
    )
    mismatch_count = len(missing) + len(mismatches)
    mismatch_rate = mismatch_count / len(mysql_ids) if mysql_ids else 0.0
    threshold = (
        settings.storage.mongo_consistency_mismatch_rate_threshold
        if mismatch_threshold is None
        else mismatch_threshold
    )
    return ConsistencyReport(
        table=table,
        mysql_count=len(mysql_ids),
        mongo_count=await collection.count_documents({}),
        missing_mysql_ids=missing[:100],
        mismatches=mismatches,
        mismatch_rate=mismatch_rate,
        ok=mismatch_rate <= threshold,
    )


async def reverse_sync_preview(
    db: Session,
    database: Any,
    *,
    table: str,
    limit: int = 100,
) -> dict[str, Any]:
    """Mongo 到 MySQL 反向同步预案入口，默认只输出待人工处理摘要。"""
    plan = TABLE_PLANS[table]
    docs = (
        await database[plan.collection]
        .find({})
        .sort([("mysqlId", 1)])
        .limit(max(limit, 0))
        .to_list(None)
    )
    missing_mysql: list[int] = []
    conflicts: list[dict[str, Any]] = []
    for doc in docs:
        mysql_id = doc.get("mysqlId")
        if mysql_id is None:
            conflicts.append({"mysqlId": None, "reason": "missing_mysqlId"})
            continue
        row = db.get(plan.model, int(mysql_id))
        if row is None:
            missing_mysql.append(int(mysql_id))
            continue
        expected = _key_fields(plan.mapper(row), plan)
        actual = _key_fields(doc, plan)
        if expected != actual:
            conflicts.append(
                {"mysqlId": int(mysql_id), "expected": expected, "actual": actual}
            )
    return {
        "table": table,
        "scanned": len(docs),
        "missing_mysql_ids": missing_mysql,
        "conflicts": conflicts,
        "mode": "preview_only",
    }


def _next_batch(
    db: Session,
    plan: TablePlan,
    *,
    last_id: int,
    batch_size: int,
    end_id: int | None,
    since: datetime | None,
    until: datetime | None,
) -> list[Any]:
    query = db.query(plan.model).filter(plan.model.id > last_id)
    if plan.model is ConversationMessage:
        query = query.options(joinedload(ConversationMessage.conversation))
    if end_id is not None:
        query = query.filter(plan.model.id <= end_id)
    if since is not None and hasattr(plan.model, "created_at"):
        query = query.filter(plan.model.created_at >= since)
    if until is not None and hasattr(plan.model, "created_at"):
        query = query.filter(plan.model.created_at < until)
    return query.order_by(plan.model.id.asc()).limit(max(batch_size, 1)).all()


async def _write_docs(
    collection: Any, docs: list[dict[str, Any]], *, retry: int
) -> None:
    attempts = max(retry, 0) + 1
    last_error: Exception | None = None
    for _attempt in range(attempts):
        try:
            for doc in docs:
                await collection.replace_one(
                    {"mysqlId": doc["mysqlId"]},
                    doc,
                    upsert=True,
                )
            return
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error


def _sample_mismatches(
    db: Session,
    *,
    plan: TablePlan,
    mysql_ids: list[int],
    mongo_by_id: dict[int, dict[str, Any]],
    sample_size: int,
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for mysql_id in mysql_ids[: max(sample_size, 0)]:
        doc = mongo_by_id.get(mysql_id)
        if doc is None:
            continue
        row = _get_row_for_mapper(db, plan, mysql_id)
        if row is None:
            continue
        expected = _key_fields(plan.mapper(row), plan)
        actual = _key_fields(doc, plan)
        if expected != actual:
            mismatches.append(
                {"mysqlId": mysql_id, "expected": expected, "actual": actual}
            )
    return mismatches


def _key_fields(doc: dict[str, Any], plan: TablePlan) -> dict[str, Any]:
    keys = ["mysqlId", "farmId", plan.business_field]
    if plan.status_field:
        keys.append(plan.status_field)
    return {key: _json_normalized(doc.get(key)) for key in keys}


def _get_row_for_mapper(db: Session, plan: TablePlan, mysql_id: int) -> Any | None:
    if plan.model is ConversationMessage:
        return (
            db.query(ConversationMessage)
            .options(joinedload(ConversationMessage.conversation))
            .filter(ConversationMessage.id == mysql_id)
            .first()
        )
    return db.get(plan.model, mysql_id)


def _json_normalized(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_normalized(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_json_normalized(item) for item in value]
    return value


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _connect_database() -> Any:
    client = create_mongo_client(settings.mongodb)
    return client[settings.mongodb.database]


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str, indent=2))


async def _run(args: argparse.Namespace) -> int:
    db = SessionLocal()
    mongo_database = _connect_database()
    try:
        if args.command == "backfill":
            stats = await backfill_table(
                db,
                mongo_database,
                table=args.table,
                batch_size=args.batch_size,
                start_id=args.start_id,
                end_id=args.end_id,
                since=_parse_datetime(args.since),
                until=_parse_datetime(args.until),
                retry=args.retry,
                dry_run=args.dry_run,
            )
            _print_json(stats.to_dict())
            return 0 if not stats.failed else 2
        if args.command == "verify":
            report = await verify_table(
                db,
                mongo_database,
                table=args.table,
                sample_size=args.sample_size,
                mismatch_threshold=args.mismatch_threshold,
            )
            if args.report:
                Path(args.report).write_text(
                    json.dumps(report.to_dict(), ensure_ascii=False, default=str),
                    encoding="utf-8",
                )
            _print_json(report.to_dict())
            return 0 if report.ok else 3
        if args.command == "reverse-sync":
            _print_json(
                await reverse_sync_preview(
                    db,
                    mongo_database,
                    table=args.table,
                    limit=args.limit,
                )
            )
            return 0
        raise ValueError(f"未知命令: {args.command}")
    finally:
        db.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MySQL 与 MongoDB 文档迁移工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backfill = subparsers.add_parser("backfill", help="从 MySQL 幂等回填到 MongoDB")
    _add_table_arg(backfill)
    backfill.add_argument("--batch-size", type=int, default=500)
    backfill.add_argument("--start-id", type=int, default=0)
    backfill.add_argument("--end-id", type=int)
    backfill.add_argument("--since")
    backfill.add_argument("--until")
    backfill.add_argument("--retry", type=int, default=2)
    backfill.add_argument("--dry-run", action="store_true")

    verify = subparsers.add_parser("verify", help="校验 MySQL 与 MongoDB 一致性")
    _add_table_arg(verify)
    verify.add_argument("--sample-size", type=int, default=20)
    verify.add_argument("--mismatch-threshold", type=float)
    verify.add_argument("--report", help="差异报告输出路径")

    reverse = subparsers.add_parser("reverse-sync", help="Mongo 到 MySQL 反向同步预案")
    _add_table_arg(reverse)
    reverse.add_argument("--limit", type=int, default=100)
    return parser.parse_args(argv)


def _add_table_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--table", required=True, choices=table_names())


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_run(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
