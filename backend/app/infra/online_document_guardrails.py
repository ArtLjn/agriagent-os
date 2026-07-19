"""`guardrails_logs` 在线文档 Repository。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.infra.mongo_mappers import (
    guardrails_log_from_mongo_doc,
    guardrails_log_to_mongo_doc,
)
from app.infra.mongo_identity import ensure_row_mysql_id
from app.infra.online_document_common import (
    DualWriteBase,
    RepositoryPage,
    log_secondary_failure,
    mongo_read_page,
    replace_doc,
)
from app.agent.guardrails.models import GuardrailsLog


class MySQLGuardrailsLogRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, row: GuardrailsLog) -> GuardrailsLog:
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def list_admin_page(
        self,
        *,
        trigger_type: str | None,
        page: int,
        size: int,
        farm_id: int | None = None,
    ) -> RepositoryPage:
        query = self._db.query(GuardrailsLog)
        if farm_id is not None:
            query = query.filter(GuardrailsLog.farm_id == farm_id)
        if trigger_type:
            query = query.filter(GuardrailsLog.trigger_type == trigger_type)
        total = query.count()
        items = (
            query.order_by(GuardrailsLog.created_at.desc(), GuardrailsLog.id.desc())
            .offset((max(page, 1) - 1) * size)
            .limit(size)
            .all()
        )
        return RepositoryPage(items=items, total=total)

    def cleanup_before(self, *, cutoff: datetime) -> int:
        deleted = (
            self._db.query(GuardrailsLog)
            .filter(GuardrailsLog.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        self._db.commit()
        return int(deleted or 0)


class MongoGuardrailsLogRepository:
    def __init__(self, collection: Any) -> None:
        self._collection = collection

    async def create(self, row: GuardrailsLog) -> GuardrailsLog:
        ensure_row_mysql_id(row)
        await replace_doc(self._collection, guardrails_log_to_mongo_doc(row))
        return row

    async def list_admin_page(
        self,
        *,
        trigger_type: str | None,
        page: int,
        size: int,
        farm_id: int | None = None,
    ) -> RepositoryPage:
        filter_doc: dict[str, Any] = {}
        if farm_id is not None:
            filter_doc["farmId"] = farm_id
        if trigger_type:
            filter_doc["triggerType"] = trigger_type
        total = await self._collection.count_documents(filter_doc)
        cursor = (
            self._collection.find(filter_doc)
            .sort([("createdAt", -1), ("mysqlId", -1)])
            .skip((max(page, 1) - 1) * size)
            .limit(size)
        )
        docs = await cursor.to_list(None)
        return RepositoryPage(
            items=[guardrails_log_from_mongo_doc(doc) for doc in docs],
            total=total,
        )

    async def cleanup_before(self, *, cutoff: datetime) -> int:
        result = await self._collection.delete_many({"createdAt": {"$lt": cutoff}})
        return int(getattr(result, "deleted_count", 0) or 0)


class DualWriteGuardrailsLogRepository(DualWriteBase):
    object_type = "guardrails_log"

    async def create(self, row: GuardrailsLog) -> GuardrailsLog:
        saved = self._mysql.create(row)
        await self._write_secondary("create", saved)
        return saved

    def list_admin_page(self, **kwargs):
        return self._mysql.list_admin_page(**kwargs)

    async def cleanup_before(self, **kwargs):
        deleted = self._mysql.cleanup_before(**kwargs)
        try:
            await self._mongo.cleanup_before(**kwargs)
        except Exception as exc:
            log_secondary_failure(self.object_type, 0, "cleanup_before", exc)
        return deleted


class MongoReadGuardrailsLogRepository(DualWriteGuardrailsLogRepository):
    async def list_admin_page(self, **kwargs):
        return await mongo_read_page(
            self._mongo.list_admin_page,
            self._mysql.list_admin_page,
            self.object_type,
            kwargs,
        )


def build_guardrails_log_repository(
    backend: str, db: Session, collection: Any | None = None, hook: Any = None
) -> Any:
    mysql = MySQLGuardrailsLogRepository(db)
    if backend == "mysql":
        return mysql
    if collection is None:
        raise ValueError("MONGO_COLLECTION_REQUIRED")
    mongo = MongoGuardrailsLogRepository(collection)
    if backend == "dual":
        return DualWriteGuardrailsLogRepository(mysql, mongo, hook)
    if backend == "mongo-read":
        return MongoReadGuardrailsLogRepository(mysql, mongo, hook)
    if backend == "mongo":
        return mongo
    raise ValueError({"code": "INVALID_STORAGE_BACKEND", "backend": backend})
