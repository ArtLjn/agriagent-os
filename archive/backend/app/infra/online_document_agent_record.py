"""`agent_records` 在线文档 Repository。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infra.mongo_mappers import (
    agent_record_from_mongo_doc,
    agent_record_to_mongo_doc,
)
from app.infra.mongo_identity import ensure_row_mysql_id
from app.infra.online_document_common import (
    DualWriteBase,
    RepositoryPage,
    log_secondary_failure,
    mongo_read_many,
    mongo_read_one,
    mongo_read_page,
    replace_doc,
    report_filter,
)
from app.agent.models import AgentRecord


class MySQLAgentRecordRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, row: AgentRecord) -> AgentRecord:
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def delete_daily_cache(
        self,
        *,
        farm_id: int,
        cycle_id: int | None = None,
        since: datetime | None = None,
    ) -> int:
        query = self._db.query(AgentRecord).filter(
            AgentRecord.farm_id == farm_id,
            AgentRecord.record_type == "daily",
        )
        if cycle_id is not None:
            query = query.filter(AgentRecord.cycle_id == cycle_id)
        if since is not None:
            query = query.filter(AgentRecord.created_at >= since)
        deleted = query.delete(synchronize_session=False)
        self._db.commit()
        return int(deleted or 0)

    def list_advice_history(
        self, *, farm_id: int, cycle_id: int | None = None, limit: int = 20
    ) -> list[AgentRecord]:
        query = self._db.query(AgentRecord).filter(
            AgentRecord.farm_id == farm_id,
            AgentRecord.record_type.in_(["chat", "daily"]),
        )
        if cycle_id is not None:
            query = query.filter(AgentRecord.cycle_id == cycle_id)
        return query.order_by(AgentRecord.created_at.desc()).limit(limit).all()

    def list_report_history(
        self, *, farm_id: int, cycle_id: int | None = None, limit: int = 20
    ) -> list[AgentRecord]:
        query = self._report_query(farm_id)
        if cycle_id is not None:
            query = query.filter(AgentRecord.cycle_id == cycle_id)
        return query.order_by(AgentRecord.created_at.desc()).limit(limit).all()

    def list_report_page(self, *, farm_id: int, page: int, size: int) -> RepositoryPage:
        query = self._report_query(farm_id)
        total = query.with_entities(func.count(AgentRecord.id)).scalar() or 0
        items = (
            query.order_by(AgentRecord.created_at.desc())
            .offset((max(page, 1) - 1) * size)
            .limit(size)
            .all()
        )
        return RepositoryPage(items=items, total=total)

    def get_report_by_id(self, *, farm_id: int, report_id: int) -> AgentRecord | None:
        return self._report_query(farm_id).filter(AgentRecord.id == report_id).first()

    def delete_report(self, *, farm_id: int, report_id: int) -> bool:
        row = self.get_report_by_id(farm_id=farm_id, report_id=report_id)
        if row is None:
            return False
        self._db.delete(row)
        self._db.commit()
        return True

    def find_daily_cache(self, *, farm_id: int, since: datetime) -> AgentRecord | None:
        return (
            self._db.query(AgentRecord)
            .filter(
                AgentRecord.farm_id == farm_id,
                AgentRecord.record_type == "daily",
                AgentRecord.created_at >= since,
            )
            .order_by(AgentRecord.created_at.desc())
            .first()
        )

    def clear_cycle_reference(self, *, cycle_id: int) -> int:
        updated = (
            self._db.query(AgentRecord)
            .filter(AgentRecord.cycle_id == cycle_id)
            .update({"cycle_id": None}, synchronize_session=False)
        )
        self._db.flush()
        return int(updated or 0)

    def _report_query(self, farm_id: int):
        return self._db.query(AgentRecord).filter(
            AgentRecord.farm_id == farm_id,
            AgentRecord.record_type.in_(["report", "weekly", "monthly"]),
        )


class MongoAgentRecordRepository:
    def __init__(self, collection: Any) -> None:
        self._collection = collection

    async def create(self, row: AgentRecord) -> AgentRecord:
        ensure_row_mysql_id(row)
        await replace_doc(self._collection, agent_record_to_mongo_doc(row))
        return row

    async def delete_daily_cache(
        self,
        *,
        farm_id: int,
        cycle_id: int | None = None,
        since: datetime | None = None,
    ) -> int:
        filter_doc: dict[str, Any] = {"farmId": farm_id, "recordType": "daily"}
        if cycle_id is not None:
            filter_doc["cycleId"] = cycle_id
        if since is not None:
            filter_doc["createdAt"] = {"$gte": since}
        result = await self._collection.delete_many(filter_doc)
        return int(getattr(result, "deleted_count", 0) or 0)

    async def list_advice_history(
        self, *, farm_id: int, cycle_id: int | None = None, limit: int = 20
    ) -> list[AgentRecord]:
        filter_doc: dict[str, Any] = {
            "farmId": farm_id,
            "recordType": {"$in": ["chat", "daily"]},
        }
        if cycle_id is not None:
            filter_doc["cycleId"] = cycle_id
        return await self._find_many(filter_doc, limit=limit)

    async def list_report_history(
        self, *, farm_id: int, cycle_id: int | None = None, limit: int = 20
    ) -> list[AgentRecord]:
        filter_doc = report_filter(farm_id)
        if cycle_id is not None:
            filter_doc["cycleId"] = cycle_id
        return await self._find_many(filter_doc, limit=limit)

    async def list_report_page(
        self, *, farm_id: int, page: int, size: int
    ) -> RepositoryPage:
        filter_doc = report_filter(farm_id)
        total = await self._collection.count_documents(filter_doc)
        items = await self._find_many(
            filter_doc,
            limit=size,
            offset=(max(page, 1) - 1) * size,
        )
        return RepositoryPage(items=items, total=total)

    async def get_report_by_id(
        self, *, farm_id: int, report_id: int
    ) -> AgentRecord | None:
        doc = await self._collection.find_one(
            {**report_filter(farm_id), "mysqlId": report_id}
        )
        return agent_record_from_mongo_doc(doc) if doc is not None else None

    async def delete_report(self, *, farm_id: int, report_id: int) -> bool:
        result = await self._collection.delete_one(
            {**report_filter(farm_id), "mysqlId": report_id}
        )
        return bool(getattr(result, "deleted_count", 0))

    async def find_daily_cache(
        self, *, farm_id: int, since: datetime
    ) -> AgentRecord | None:
        rows = await self._find_many(
            {
                "farmId": farm_id,
                "recordType": "daily",
                "createdAt": {"$gte": since},
            },
            limit=1,
        )
        return rows[0] if rows else None

    async def clear_cycle_reference(self, *, cycle_id: int) -> int:
        result = await self._collection.update_many(
            {"cycleId": cycle_id},
            {"$set": {"cycleId": None}},
        )
        return int(getattr(result, "modified_count", 0) or 0)

    async def _find_many(
        self, filter_doc: dict[str, Any], *, limit: int, offset: int = 0
    ) -> list[AgentRecord]:
        cursor = (
            self._collection.find(filter_doc)
            .sort([("createdAt", -1), ("mysqlId", -1)])
            .skip(max(offset, 0))
            .limit(max(limit, 0))
        )
        docs = await cursor.to_list(None)
        return [agent_record_from_mongo_doc(doc) for doc in docs]


class DualWriteAgentRecordRepository(DualWriteBase):
    object_type = "agent_record"

    async def create(self, row: AgentRecord) -> AgentRecord:
        saved = self._mysql.create(row)
        await self._write_secondary("create", saved)
        return saved

    async def delete_daily_cache(self, **kwargs):
        deleted = self._mysql.delete_daily_cache(**kwargs)
        try:
            await self._mongo.delete_daily_cache(**kwargs)
        except Exception as exc:
            log_secondary_failure(
                self.object_type,
                kwargs.get("farm_id", 0),
                "delete_daily_cache",
                exc,
            )
        return deleted

    def list_advice_history(self, **kwargs):
        return self._mysql.list_advice_history(**kwargs)

    def list_report_history(self, **kwargs):
        return self._mysql.list_report_history(**kwargs)

    def list_report_page(self, **kwargs):
        return self._mysql.list_report_page(**kwargs)

    def get_report_by_id(self, **kwargs):
        return self._mysql.get_report_by_id(**kwargs)

    async def delete_report(self, **kwargs):
        deleted = self._mysql.delete_report(**kwargs)
        try:
            await self._mongo.delete_report(**kwargs)
        except Exception as exc:
            log_secondary_failure(
                self.object_type,
                kwargs.get("farm_id", 0),
                "delete_report",
                exc,
            )
        return deleted

    def find_daily_cache(self, **kwargs):
        return self._mysql.find_daily_cache(**kwargs)

    async def clear_cycle_reference(self, **kwargs):
        updated = self._mysql.clear_cycle_reference(**kwargs)
        try:
            await self._mongo.clear_cycle_reference(**kwargs)
        except Exception as exc:
            log_secondary_failure(self.object_type, 0, "clear_cycle_reference", exc)
        return updated


class MongoReadAgentRecordRepository(DualWriteAgentRecordRepository):
    async def list_advice_history(self, **kwargs):
        return await mongo_read_many(
            self._mongo.list_advice_history,
            self._mysql.list_advice_history,
            self.object_type,
            kwargs,
        )

    async def list_report_history(self, **kwargs):
        return await mongo_read_many(
            self._mongo.list_report_history,
            self._mysql.list_report_history,
            self.object_type,
            kwargs,
        )

    async def list_report_page(self, **kwargs):
        return await mongo_read_page(
            self._mongo.list_report_page,
            self._mysql.list_report_page,
            self.object_type,
            kwargs,
        )

    async def get_report_by_id(self, **kwargs):
        return await mongo_read_one(
            self._mongo.get_report_by_id,
            self._mysql.get_report_by_id,
            self.object_type,
            kwargs,
        )

    async def find_daily_cache(self, **kwargs):
        return await mongo_read_one(
            self._mongo.find_daily_cache,
            self._mysql.find_daily_cache,
            self.object_type,
            kwargs,
        )


def build_agent_record_repository(
    backend: str, db: Session, collection: Any | None = None, hook: Any = None
) -> Any:
    mysql = MySQLAgentRecordRepository(db)
    if backend == "mysql":
        return mysql
    if collection is None:
        raise ValueError("MONGO_COLLECTION_REQUIRED")
    mongo = MongoAgentRecordRepository(collection)
    if backend == "dual":
        return DualWriteAgentRecordRepository(mysql, mongo, hook)
    if backend == "mongo-read":
        return MongoReadAgentRecordRepository(mysql, mongo, hook)
    if backend == "mongo":
        return mongo
    raise ValueError({"code": "INVALID_STORAGE_BACKEND", "backend": backend})
