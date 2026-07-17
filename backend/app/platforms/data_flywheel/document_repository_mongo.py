"""Data Flywheel 文档对象 Mongo Repository。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from app.infra.mongo_mappers import (
    case_draft_from_mongo_doc,
    case_draft_to_mongo_doc,
    prelabel_from_mongo_doc,
    prelabel_to_mongo_doc,
    repair_pack_from_mongo_doc,
    repair_pack_to_mongo_doc,
    review_issue_chain_from_mongo_doc,
    review_issue_chain_to_mongo_doc,
)
from app.infra.mongo_identity import ensure_row_mysql_id
from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelPrelabel,
    AgentRepairPack,
    AgentReviewIssueChain,
)
from app.platforms.data_flywheel.document_repository_common import (
    RepositoryPage,
    farm_filter,
    mongo_update,
)

ModelT = TypeVar("ModelT")


class _MongoBaseRepository(Generic[ModelT]):
    object_type = "document"

    def __init__(self, collection: Any, *, to_doc, from_doc) -> None:
        self._collection = collection
        self._to_doc = to_doc
        self._from_doc = from_doc

    async def _upsert_row(self, row: ModelT) -> ModelT:
        ensure_row_mysql_id(row)
        doc = self._to_doc(row)
        await self._collection.replace_one(
            {"mysqlId": doc["mysqlId"]},
            doc,
            upsert=True,
        )
        return row

    async def _find_one(self, farm_id: int, **conditions: Any) -> ModelT | None:
        doc = await self._collection.find_one(farm_filter(farm_id, **conditions))
        return self._from_doc(doc) if doc is not None else None

    async def _find_many(
        self,
        farm_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
        sort: list[tuple[str, int]] | None = None,
        **conditions: Any,
    ) -> list[ModelT]:
        cursor = self._collection.find(farm_filter(farm_id, **conditions))
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(max(offset, 0)).limit(max(limit, 0))
        docs = await cursor.to_list(None)
        return [self._from_doc(doc) for doc in docs]

    async def _count(self, farm_id: int, **conditions: Any) -> int:
        return await self._collection.count_documents(
            farm_filter(farm_id, **conditions)
        )

    async def _update_one(
        self, farm_id: int, filter_conditions: dict[str, Any], fields: dict[str, Any]
    ) -> ModelT | None:
        filter_doc = farm_filter(farm_id, **filter_conditions)
        await self._collection.update_one(filter_doc, {"$set": mongo_update(fields)})
        doc = await self._collection.find_one(filter_doc)
        return self._from_doc(doc) if doc is not None else None


class MongoPrelabelRepository(_MongoBaseRepository[AgentDataFlywheelPrelabel]):
    object_type = "prelabel"

    def __init__(self, collection: Any) -> None:
        super().__init__(
            collection,
            to_doc=prelabel_to_mongo_doc,
            from_doc=prelabel_from_mongo_doc,
        )

    async def create(self, row: AgentDataFlywheelPrelabel) -> AgentDataFlywheelPrelabel:
        return await self._upsert_row(row)

    async def get_by_id_and_sample(
        self, *, farm_id: int, prelabel_id: int, sample_id: str
    ) -> AgentDataFlywheelPrelabel | None:
        return await self._find_one(farm_id, mysqlId=prelabel_id, sampleId=sample_id)

    async def list_by_samples(
        self, *, farm_id: int, sample_ids: list[str]
    ) -> list[AgentDataFlywheelPrelabel]:
        if not sample_ids:
            return []
        return await self._find_many(
            farm_id,
            limit=1000,
            sort=[("createdAt", -1), ("mysqlId", -1)],
            sampleId={"$in": sample_ids},
        )

    async def update_review_fields(
        self,
        *,
        farm_id: int,
        prelabel_id: int,
        sample_id: str,
        status: str,
        reviewed_by: str | None = None,
        reviewed_at: datetime | None = None,
        accepted_label_ids: list[int] | None = None,
    ) -> AgentDataFlywheelPrelabel | None:
        return await self._update_one(
            farm_id,
            {"mysqlId": prelabel_id, "sampleId": sample_id},
            {
                "status": status,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
                "accepted_label_ids": accepted_label_ids,
            },
        )


class MongoCaseDraftRepository(_MongoBaseRepository[AgentCaseDraft]):
    object_type = "case_draft"

    def __init__(self, collection: Any) -> None:
        super().__init__(
            collection,
            to_doc=case_draft_to_mongo_doc,
            from_doc=case_draft_from_mongo_doc,
        )

    async def create(self, row: AgentCaseDraft) -> AgentCaseDraft:
        return await self._upsert_row(row)

    async def get_by_draft_id(
        self, *, farm_id: int, draft_id: str
    ) -> AgentCaseDraft | None:
        return await self._find_one(farm_id, draftId=draft_id)

    async def list_by_source_sample(
        self, *, farm_id: int, source_sample_id: str, limit: int = 20, offset: int = 0
    ) -> RepositoryPage[AgentCaseDraft]:
        conditions = {"sourceSampleId": source_sample_id}
        total = await self._count(farm_id, **conditions)
        items = await self._find_many(
            farm_id,
            limit=limit,
            offset=offset,
            sort=[("createdAt", -1), ("mysqlId", -1)],
            **conditions,
        )
        return RepositoryPage(items=items, total=total, page_size=limit)


class MongoRepairPackRepository(_MongoBaseRepository[AgentRepairPack]):
    object_type = "repair_pack"

    def __init__(self, collection: Any) -> None:
        super().__init__(
            collection,
            to_doc=repair_pack_to_mongo_doc,
            from_doc=repair_pack_from_mongo_doc,
        )

    async def create(self, row: AgentRepairPack) -> AgentRepairPack:
        return await self._upsert_row(row)

    async def get_by_pack_id(
        self, *, farm_id: int, pack_id: str
    ) -> AgentRepairPack | None:
        return await self._find_one(farm_id, packId=pack_id)

    async def list(
        self,
        *,
        farm_id: int,
        status: str | None = None,
        fix_target: str | None = None,
        include_discarded: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> RepositoryPage[AgentRepairPack]:
        page = max(page, 1)
        page_size = max(page_size, 1)
        conditions: dict[str, Any] = {}
        if status:
            conditions["status"] = status
        elif not include_discarded:
            conditions["status"] = {"$ne": "discarded"}
        if fix_target:
            conditions["fixTarget"] = fix_target
        total = await self._count(farm_id, **conditions)
        items = await self._find_many(
            farm_id,
            limit=page_size,
            offset=(page - 1) * page_size,
            sort=[("createdAt", -1), ("mysqlId", -1)],
            **conditions,
        )
        return RepositoryPage(items=items, total=total, page=page, page_size=page_size)

    async def find_active_by_dedup_key(
        self, *, farm_id: int, dedup_key: str
    ) -> AgentRepairPack | None:
        rows = await self._find_many(
            farm_id,
            limit=1,
            sort=[("createdAt", -1), ("mysqlId", -1)],
            dedupKey=dedup_key,
            status={"$ne": "discarded"},
        )
        return rows[0] if rows else None

    async def update_fields(
        self, *, farm_id: int, pack_id: str, **fields: Any
    ) -> AgentRepairPack | None:
        return await self._update_one(farm_id, {"packId": pack_id}, fields)


class MongoReviewIssueChainRepository(_MongoBaseRepository[AgentReviewIssueChain]):
    object_type = "review_issue_chain"

    def __init__(self, collection: Any) -> None:
        super().__init__(
            collection,
            to_doc=review_issue_chain_to_mongo_doc,
            from_doc=review_issue_chain_from_mongo_doc,
        )

    async def get_by_chain_id(
        self, *, farm_id: int, chain_id: str
    ) -> AgentReviewIssueChain | None:
        return await self._find_one(farm_id, chainId=chain_id)

    async def save(self, row: AgentReviewIssueChain) -> AgentReviewIssueChain:
        return await self._upsert_row(row)

    async def list_by_session(
        self,
        *,
        farm_id: int,
        session_id: str,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> RepositoryPage[AgentReviewIssueChain]:
        conditions = {"sessionId": session_id}
        if status:
            conditions["status"] = status
        total = await self._count(farm_id, **conditions)
        items = await self._find_many(
            farm_id,
            limit=limit,
            offset=offset,
            sort=[("severity", 1), ("updatedAt", -1), ("mysqlId", -1)],
            **conditions,
        )
        return RepositoryPage(items=items, total=total, page_size=limit)

    async def list(
        self,
        *,
        farm_id: int,
        session_id: str | None = None,
        severity: str = "all",
        limit: int = 1000,
        offset: int = 0,
    ) -> RepositoryPage[AgentReviewIssueChain]:
        conditions: dict[str, Any] = {}
        if session_id:
            conditions["sessionId"] = session_id
        if severity != "all":
            conditions["severity"] = severity
        total = await self._count(farm_id, **conditions)
        items = await self._find_many(
            farm_id,
            limit=limit,
            offset=offset,
            sort=[("severity", 1), ("updatedAt", -1), ("mysqlId", -1)],
            **conditions,
        )
        return RepositoryPage(items=items, total=total, page_size=limit)

    async def update_review_fields(
        self, *, farm_id: int, chain_id: str, **fields: Any
    ) -> AgentReviewIssueChain | None:
        return await self._update_one(farm_id, {"chainId": chain_id}, fields)

    async def update_ai_judge_fields(
        self, *, farm_id: int, chain_id: str, ai_judge: dict[str, Any]
    ) -> AgentReviewIssueChain | None:
        return await self._update_one(
            farm_id,
            {"chainId": chain_id},
            {"ai_judge": ai_judge, "dominant_signal": "judge"},
        )
