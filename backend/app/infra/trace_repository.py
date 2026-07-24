"""Trace 记录 Repository 抽象与存储后端实现。"""

from __future__ import annotations

import logging
import re
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.infra.mongo_mappers import (
    trace_record_from_mongo_doc,
    trace_record_to_mongo_doc,
)
from app.infra.mongo_identity import ensure_row_mysql_id
from app.infra.trace_summary import (
    build_trace_request_summary,
    trace_request_summary_to_mongo_doc,
)
from app.platforms.evaluation.trace_models import TraceRecord

logger = logging.getLogger(__name__)

FailureHook = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class TracePage:
    """Trace 列表分页结果。"""

    items: list[TraceRecord]
    total: int


class TraceRepository(Protocol):
    """Trace 存储接口，覆盖写入、详情、列表和节点聚合。"""

    def insert(self, record: TraceRecord) -> TraceRecord: ...

    def get_by_request_id(
        self, *, farm_id: int, request_id: str
    ) -> list[TraceRecord]: ...

    def list_by_session(
        self,
        *,
        farm_id: int,
        session_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> TracePage: ...

    def aggregate_by_node(
        self, *, farm_id: int, session_id: str
    ) -> list[dict[str, Any]]: ...


class TraceMySQLRepository:
    """基于 SQLAlchemy Session 的 Trace Repository。"""

    def __init__(self, db: Session) -> None:
        self._db = db

    def insert(self, record: TraceRecord) -> TraceRecord:
        self._db.add(record)
        self._db.commit()
        self._db.refresh(record)
        return record

    def get_by_request_id(self, *, farm_id: int, request_id: str) -> list[TraceRecord]:
        return (
            self._db.query(TraceRecord)
            .filter(
                TraceRecord.farm_id == farm_id,
                TraceRecord.request_id == request_id,
            )
            .order_by(TraceRecord.round_index.asc(), TraceRecord.id.asc())
            .all()
        )

    def list_by_session(
        self,
        *,
        farm_id: int,
        session_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> TracePage:
        query = self._db.query(TraceRecord).filter(
            TraceRecord.farm_id == farm_id,
            TraceRecord.session_id == session_id,
        )
        total = query.count()
        items = (
            query.order_by(TraceRecord.created_at.desc(), TraceRecord.id.desc())
            .offset(max(offset, 0))
            .limit(max(limit, 0))
            .all()
        )
        return TracePage(items=items, total=total)

    def aggregate_by_node(
        self, *, farm_id: int, session_id: str
    ) -> list[dict[str, Any]]:
        rows = (
            self._db.query(TraceRecord)
            .filter(
                TraceRecord.farm_id == farm_id,
                TraceRecord.session_id == session_id,
            )
            .order_by(TraceRecord.id.desc())
            .all()
        )
        grouped: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
        for row in rows:
            key = (row.node_type, row.node_name)
            item = grouped.setdefault(
                key,
                {
                    "node_type": row.node_type,
                    "node_name": row.node_name,
                    "count": 0,
                    "duration_ms_total": 0,
                    "error_count": 0,
                },
            )
            item["count"] += 1
            item["duration_ms_total"] += row.duration_ms or 0
            if row.status != "success":
                item["error_count"] += 1
        return [
            {
                **item,
                "avg_duration_ms": (
                    item["duration_ms_total"] / item["count"] if item["count"] else 0
                ),
            }
            for item in grouped.values()
        ]


class TraceMongoRepository:
    """基于 motor collection 风格接口的 Trace Repository。"""

    def __init__(self, collection: Any, request_collection: Any | None = None) -> None:
        self._collection = collection
        self._request_collection = request_collection

    async def insert(self, record: TraceRecord) -> TraceRecord:
        ensure_row_mysql_id(record)
        doc = trace_record_to_mongo_doc(record)
        await self._collection.replace_one(
            {"mysqlId": doc["mysqlId"]},
            doc,
            upsert=True,
        )
        await self.refresh_request_summary(
            farm_id=record.farm_id,
            request_id=record.request_id,
            fallback_record=record,
        )
        return record

    async def refresh_request_summary(
        self,
        *,
        farm_id: int,
        request_id: str,
        fallback_record: TraceRecord | None = None,
    ) -> None:
        """刷新 request 级摘要，供 TraceMonitor 列表快速读取。"""
        if self._request_collection is None:
            return
        records = await self.get_by_request_id(farm_id=farm_id, request_id=request_id)
        if not records and fallback_record is not None:
            records = [fallback_record]
        summary = build_trace_request_summary(records)
        if summary is None:
            return
        doc = trace_request_summary_to_mongo_doc(summary)
        await self._request_collection.replace_one(
            {"farmId": farm_id, "requestId": request_id},
            doc,
            upsert=True,
        )

    async def get_by_request_id(
        self, *, farm_id: int, request_id: str
    ) -> list[TraceRecord]:
        filter_doc = _farm_filter(farm_id, requestId=request_id)
        cursor = self._collection.find(filter_doc).sort(
            [("roundIndex", 1), ("mysqlId", 1)]
        )
        docs = await cursor.to_list(None)
        return [trace_record_from_mongo_doc(doc) for doc in docs]

    async def list_by_session(
        self,
        *,
        farm_id: int,
        session_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> TracePage:
        filter_doc = _farm_filter(farm_id, sessionId=session_id)
        total = await self._collection.count_documents(filter_doc)
        cursor = (
            self._collection.find(filter_doc)
            .sort([("createdAt", -1), ("mysqlId", -1)])
            .skip(max(offset, 0))
            .limit(max(limit, 0))
        )
        docs = await cursor.to_list(None)
        return TracePage(
            items=[trace_record_from_mongo_doc(doc) for doc in docs],
            total=total,
        )

    async def aggregate_by_node(
        self, *, farm_id: int, session_id: str
    ) -> list[dict[str, Any]]:
        page = await self.list_by_session(
            farm_id=farm_id,
            session_id=session_id,
            limit=1000,
            offset=0,
        )
        grouped: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
        for row in page.items:
            key = (row.node_type, row.node_name)
            item = grouped.setdefault(
                key,
                {
                    "node_type": row.node_type,
                    "node_name": row.node_name,
                    "count": 0,
                    "duration_ms_total": 0,
                    "error_count": 0,
                },
            )
            item["count"] += 1
            item["duration_ms_total"] += row.duration_ms or 0
            if row.status != "success":
                item["error_count"] += 1
        return [
            {
                **item,
                "avg_duration_ms": (
                    item["duration_ms_total"] / item["count"] if item["count"] else 0
                ),
            }
            for item in grouped.values()
        ]


class TraceDualWriteRepository:
    """Trace 双写 Repository：MySQL 成功后再写 Mongo。"""

    def __init__(
        self,
        mysql_repo: TraceMySQLRepository,
        mongo_repo: TraceMongoRepository,
        on_secondary_failure: FailureHook | None = None,
    ) -> None:
        self._mysql = mysql_repo
        self._mongo = mongo_repo
        self._on_secondary_failure = on_secondary_failure

    async def insert(self, record: TraceRecord) -> TraceRecord:
        row = self._mysql.insert(record)
        try:
            await self._mongo.insert(row)
        except Exception as exc:
            _handle_secondary_failure(
                hook=self._on_secondary_failure,
                object_type="trace",
                farm_id=row.farm_id,
                business_id=row.request_id,
                mysql_id=row.id,
                operation="insert",
                exc=exc,
            )
        return row

    def get_by_request_id(self, *, farm_id: int, request_id: str) -> list[TraceRecord]:
        return self._mysql.get_by_request_id(farm_id=farm_id, request_id=request_id)

    def list_by_session(
        self,
        *,
        farm_id: int,
        session_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> TracePage:
        return self._mysql.list_by_session(
            farm_id=farm_id,
            session_id=session_id,
            limit=limit,
            offset=offset,
        )

    def aggregate_by_node(
        self, *, farm_id: int, session_id: str
    ) -> list[dict[str, Any]]:
        return self._mysql.aggregate_by_node(farm_id=farm_id, session_id=session_id)


class MongoReadTraceRepository(TraceDualWriteRepository):
    """Trace Mongo 读灰度 Repository，读失败或未命中回退 MySQL。"""

    async def get_by_request_id(
        self, *, farm_id: int, request_id: str
    ) -> list[TraceRecord]:
        try:
            rows = await self._mongo.get_by_request_id(
                farm_id=farm_id,
                request_id=request_id,
            )
            if rows:
                return rows
            _log_read_fallback("trace", farm_id, request_id, "mongo_miss")
        except Exception as exc:
            _log_read_fallback("trace", farm_id, request_id, _redact_error(exc))
        return self._mysql.get_by_request_id(farm_id=farm_id, request_id=request_id)

    async def list_by_session(
        self,
        *,
        farm_id: int,
        session_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> TracePage:
        try:
            page = await self._mongo.list_by_session(
                farm_id=farm_id,
                session_id=session_id,
                limit=limit,
                offset=offset,
            )
            if page.total:
                return page
            _log_read_fallback("trace", farm_id, session_id, "mongo_miss")
        except Exception as exc:
            _log_read_fallback("trace", farm_id, session_id, _redact_error(exc))
        return self._mysql.list_by_session(
            farm_id=farm_id,
            session_id=session_id,
            limit=limit,
            offset=offset,
        )

    async def aggregate_by_node(
        self, *, farm_id: int, session_id: str
    ) -> list[dict[str, Any]]:
        try:
            rows = await self._mongo.aggregate_by_node(
                farm_id=farm_id,
                session_id=session_id,
            )
            if rows:
                return rows
            _log_read_fallback("trace", farm_id, session_id, "mongo_miss")
        except Exception as exc:
            _log_read_fallback("trace", farm_id, session_id, _redact_error(exc))
        return self._mysql.aggregate_by_node(farm_id=farm_id, session_id=session_id)


def build_trace_repository(
    backend: str,
    db: Session,
    collection: Any | None = None,
    request_collection: Any | None = None,
    on_secondary_failure: FailureHook | None = None,
) -> Any:
    """按 storage backend 创建 Trace Repository。"""
    mysql_repo = TraceMySQLRepository(db)
    if backend == "mysql":
        return mysql_repo
    if collection is None:
        raise ValueError("MONGO_COLLECTION_REQUIRED")
    mongo_repo = TraceMongoRepository(collection, request_collection=request_collection)
    if backend == "dual":
        return TraceDualWriteRepository(mysql_repo, mongo_repo, on_secondary_failure)
    if backend == "mongo-read":
        return MongoReadTraceRepository(mysql_repo, mongo_repo, on_secondary_failure)
    if backend == "mongo":
        return mongo_repo
    raise ValueError({"code": "INVALID_STORAGE_BACKEND", "backend": backend})


def _farm_filter(farm_id: int, **conditions: Any) -> dict[str, Any]:
    if farm_id is None:
        raise ValueError("MONGO_FARM_ID_REQUIRED")
    return {"farmId": farm_id, **conditions}


def _handle_secondary_failure(
    *,
    hook: FailureHook | None,
    object_type: str,
    farm_id: int,
    business_id: str | None,
    mysql_id: int | None,
    operation: str,
    exc: Exception,
) -> None:
    payload = {
        "code": "mongo_secondary_write_failed",
        "object_type": object_type,
        "farm_id": farm_id,
        "business_id": business_id,
        "mysql_id": mysql_id,
        "operation": operation,
        "error": _redact_error(exc),
    }
    logger.warning(
        "Mongo 二级写失败 | code=%s object_type=%s farm_id=%s business_id=%s mysql_id=%s error=%s",
        payload["code"],
        object_type,
        farm_id,
        business_id,
        mysql_id,
        payload["error"],
    )
    if hook is not None:
        try:
            hook(payload)
        except Exception as hook_exc:
            logger.warning(
                "Mongo 补偿任务记录失败 | code=mongo_compensation_record_failed "
                "object_type=%s farm_id=%s business_id=%s mysql_id=%s error=%s",
                object_type,
                farm_id,
                business_id,
                mysql_id,
                _redact_error(hook_exc),
            )


def _log_read_fallback(
    object_type: str,
    farm_id: int,
    business_id: str,
    reason: str,
) -> None:
    logger.warning(
        "Mongo 读回退 MySQL | code=mongo_read_fallback_to_mysql object_type=%s farm_id=%s business_id=%s reason=%s",
        object_type,
        farm_id,
        business_id,
        reason,
    )


def _redact_error(exc: Exception) -> str:
    return re.sub(
        r"(mongodb(?:\+srv)?://[^:/\s@]+:)[^@\s]+@",
        r"\1***@",
        str(exc),
    )


__all__ = [
    "MongoReadTraceRepository",
    "TraceDualWriteRepository",
    "TraceMongoRepository",
    "TraceMySQLRepository",
    "TracePage",
    "TraceRepository",
    "build_trace_repository",
]
