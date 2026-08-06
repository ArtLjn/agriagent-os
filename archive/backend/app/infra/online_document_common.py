"""在线文档 Repository 通用协议与灰度辅助逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.infra.trace_repository import _handle_secondary_failure, _log_read_fallback
from app.infra.mongo_identity import ensure_doc_mysql_id


@dataclass(frozen=True)
class RepositoryPage:
    items: list[Any]
    total: int


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
