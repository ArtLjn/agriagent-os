"""MySQL 文档清库工具的共享类型与表策略。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.inspection import inspect as sqlalchemy_inspect
from sqlalchemy.sql.sqltypes import Date, DateTime

from app.agent.models import AgentRecord
from app.domains.conversation.models import ConversationMessage
from app.platforms.data_flywheel.models import (
    AgentCaseDraft,
    AgentDataFlywheelPrelabel,
    AgentRepairPack,
    AgentReviewIssueChain,
)
from app.agent.guardrails.models import GuardrailsLog
from app.platforms.evaluation.trace_models import TraceRecord


@dataclass(frozen=True)
class CleanupTable:
    model: type
    collection: str
    storage_key: str
    object_type: str
    default_strategy: str


@dataclass
class PlanRow:
    table: str
    strategy: str
    mysql_count: int
    mongo_count: int | None
    backend: str
    verify_status: str
    compensation_backlog: int
    blocked_reasons: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = "blocked" if self.blocked_reasons else "ready"
        return payload


@dataclass
class BackupResult:
    table: str
    row_count: int
    backup_file: str
    metadata_file: str
    sha256: str
    cleanup_confirm_token: str
    rollback_confirm_token: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CleanupResult:
    table: str
    mode: str
    strategy: str
    planned_count: int
    affected_count: int
    batch_size: int
    batches: int
    backup_sha256: str | None = None
    stopped_on_error: bool = False
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RollbackResult:
    table: str
    mode: str
    scanned: int
    inserted: int
    skipped_existing: int
    backup_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CleanupError(RuntimeError):
    """带结构化 code 的清库错误。"""

    def __init__(self, code: str, **context: Any) -> None:
        super().__init__(json.dumps({"code": code, **context}, ensure_ascii=False))
        self.code = code
        self.context = context


TABLES: dict[str, CleanupTable] = {
    "trace_records": CleanupTable(
        TraceRecord, "traceRecords", "trace", "trace", "delete"
    ),
    "agent_case_drafts": CleanupTable(
        AgentCaseDraft, "caseDrafts", "case_drafts", "case_draft", "delete"
    ),
    "agent_repair_packs": CleanupTable(
        AgentRepairPack, "repairPacks", "repair_packs", "repair_pack", "delete"
    ),
    "agent_review_issue_chains": CleanupTable(
        AgentReviewIssueChain,
        "reviewIssueChains",
        "review_issue_chains",
        "review_issue_chain",
        "delete",
    ),
    "agent_data_flywheel_prelabels": CleanupTable(
        AgentDataFlywheelPrelabel, "prelabels", "prelabels", "prelabel", "delete"
    ),
    "conversation_messages": CleanupTable(
        ConversationMessage,
        "conversationMessages",
        "conversation_messages",
        "conversation_message",
        "slim",
    ),
    "agent_records": CleanupTable(
        AgentRecord, "agentRecords", "agent_records", "agent_record", "delete"
    ),
    "guardrails_logs": CleanupTable(
        GuardrailsLog, "guardrailsLogs", "guardrails_logs", "guardrails_log", "delete"
    ),
}

DENIED_TABLES = {
    "conversations",
    "agent_turns",
    "feedback_records",
    "token_daily_stats",
    "agent_data_flywheel_labels",
}


def table_names() -> list[str]:
    return list(TABLES)


def require_allowed_table(table: str) -> CleanupTable:
    if table in DENIED_TABLES or table not in TABLES:
        raise CleanupError("MYSQL_CLEANUP_TABLE_NOT_ALLOWED", table=table)
    return TABLES[table]


def confirmation_token(action: str, table: str, sha256: str) -> str:
    return f"{action}:{table}:{sha256[:12]}"


def serialize_row(row: Any) -> dict[str, Any]:
    return {
        column.key: serialize_value(getattr(row, column.key))
        for column in sqlalchemy_inspect(row).mapper.column_attrs
    }


def serialize_value(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def deserialize_row(model: type, payload: dict[str, Any]) -> dict[str, Any]:
    columns = model.__table__.columns
    values = {}
    for key, value in payload.items():
        if key not in columns:
            continue
        column_type = columns[key].type
        if value is not None and isinstance(column_type, DateTime):
            value = datetime.fromisoformat(value)
        elif value is not None and isinstance(column_type, Date):
            value = date.fromisoformat(value)
        values[key] = value
    return values


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
