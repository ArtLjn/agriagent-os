"""在线文档 Repository 通用协议与灰度辅助逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.infra.trace_repository import _handle_secondary_failure, _log_read_fallback
from app.infra.mongo_identity import ensure_doc_mysql_id
from app.models.agent_record import AgentRecord
from app.models.conversation import ConversationMessage
from app.models.guardrails_log import GuardrailsLog


@dataclass(frozen=True)
class RepositoryPage:
    items: list[Any]
    total: int


class ConversationMessageRepository(Protocol):
    def save_one(self, row: ConversationMessage) -> ConversationMessage: ...

    def save_batch(
        self, rows: list[ConversationMessage]
    ) -> list[ConversationMessage]: ...

    def get_recent(
        self, *, farm_id: int, conversation_id: int, limit: int
    ) -> list[ConversationMessage]: ...

    def list_by_session(
        self, *, farm_id: int, session_id: str
    ) -> list[ConversationMessage]: ...

    def list_by_turn_ids(
        self, *, farm_id: int, turn_ids: list[int]
    ) -> list[ConversationMessage]: ...

    def get_by_mysql_id(
        self, *, farm_id: int, mysql_id: int
    ) -> ConversationMessage | None: ...


class AgentRecordRepository(Protocol):
    def create(self, row: AgentRecord) -> AgentRecord: ...

    def delete_daily_cache(
        self,
        *,
        farm_id: int,
        cycle_id: int | None = None,
        since: datetime | None = None,
    ) -> int: ...

    def list_advice_history(
        self, *, farm_id: int, cycle_id: int | None = None, limit: int = 20
    ) -> list[AgentRecord]: ...

    def list_report_history(
        self, *, farm_id: int, cycle_id: int | None = None, limit: int = 20
    ) -> list[AgentRecord]: ...

    def list_report_page(
        self, *, farm_id: int, page: int, size: int
    ) -> RepositoryPage: ...

    def get_report_by_id(
        self, *, farm_id: int, report_id: int
    ) -> AgentRecord | None: ...

    def delete_report(self, *, farm_id: int, report_id: int) -> bool: ...

    def find_daily_cache(
        self, *, farm_id: int, since: datetime
    ) -> AgentRecord | None: ...

    def clear_cycle_reference(self, *, cycle_id: int) -> int: ...


class GuardrailsLogRepository(Protocol):
    def create(self, row: GuardrailsLog) -> GuardrailsLog: ...

    def list_admin_page(
        self,
        *,
        trigger_type: str | None,
        page: int,
        size: int,
        farm_id: int | None = None,
    ) -> RepositoryPage: ...

    def cleanup_before(self, *, cutoff: datetime) -> int: ...


class DualWriteBase:
    object_type = "document"

    def __init__(self, mysql_repo: Any, mongo_repo: Any, hook: Any = None) -> None:
        self._mysql = mysql_repo
        self._mongo = mongo_repo
        self._hook = hook

    async def _write_secondary(self, operation: str, row: Any) -> None:
        try:
            method = getattr(self._mongo, operation)
            await method(row)
        except Exception as exc:
            _handle_secondary_failure(
                hook=self._hook,
                object_type=self.object_type,
                farm_id=_row_farm_id(row),
                business_id=str(getattr(row, "id", "")),
                mysql_id=getattr(row, "id", None),
                operation=operation,
                exc=exc,
            )


async def replace_doc(collection: Any, doc: dict[str, Any]) -> None:
    ensure_doc_mysql_id(doc)
    await collection.replace_one({"mysqlId": doc["mysqlId"]}, doc, upsert=True)


def report_filter(farm_id: int) -> dict[str, Any]:
    return {"farmId": farm_id, "recordType": {"$in": ["report", "weekly", "monthly"]}}


async def mongo_read_many(mongo_method, mysql_method, object_type, kwargs):
    farm_id = kwargs.get("farm_id", 0)
    try:
        rows = await mongo_method(**kwargs)
        if rows:
            return rows
        _log_read_fallback(object_type, farm_id, str(kwargs), "mongo_miss")
    except Exception as exc:
        _log_read_fallback(object_type, farm_id, str(kwargs), str(exc))
    return mysql_method(**kwargs)


async def mongo_read_one(mongo_method, mysql_method, object_type, kwargs):
    farm_id = kwargs.get("farm_id", 0)
    try:
        row = await mongo_method(**kwargs)
        if row is not None:
            return row
        _log_read_fallback(object_type, farm_id, str(kwargs), "mongo_miss")
    except Exception as exc:
        _log_read_fallback(object_type, farm_id, str(kwargs), str(exc))
    return mysql_method(**kwargs)


async def mongo_read_page(mongo_method, mysql_method, object_type, kwargs):
    farm_id = kwargs.get("farm_id", 0)
    try:
        page = await mongo_method(**kwargs)
        if page.total:
            return page
        _log_read_fallback(object_type, farm_id, str(kwargs), "mongo_miss")
    except Exception as exc:
        _log_read_fallback(object_type, farm_id, str(kwargs), str(exc))
    return mysql_method(**kwargs)


def log_secondary_failure(
    object_type: str, farm_id: int, operation: str, exc: Exception
) -> None:
    _log_read_fallback(object_type, farm_id, operation, str(exc))


def _row_farm_id(row: Any) -> int | None:
    farm_id = getattr(row, "farm_id", None)
    if farm_id is not None:
        return farm_id
    conversation = getattr(row, "conversation", None)
    return getattr(conversation, "farm_id", None)
