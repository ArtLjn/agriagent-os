"""Data Flywheel 文档对象双写与 Mongo 读灰度 Repository。"""

from __future__ import annotations

from typing import Generic, TypeVar

from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelPrelabel,
    AgentRepairPack,
    AgentReviewIssueChain,
)
from app.modules.data_flywheel.document_repository_common import (
    business_id,
    handle_secondary_failure,
    log_read_fallback,
    redact_error,
)

ModelT = TypeVar("ModelT")


class _DualWriteBase(Generic[ModelT]):
    object_type = "document"

    def __init__(self, mysql_repo, mongo_repo, on_secondary_failure=None) -> None:
        self._mysql = mysql_repo
        self._mongo = mongo_repo
        self._on_secondary_failure = on_secondary_failure

    async def _dual_create(self, row: ModelT) -> ModelT:
        saved = self._mysql.create(row)
        await self._write_secondary("create", saved)
        return saved

    async def _write_secondary(self, operation: str, row: ModelT) -> None:
        try:
            method = getattr(self._mongo, operation)
            await method(row)
        except Exception as exc:
            handle_secondary_failure(
                hook=self._on_secondary_failure,
                object_type=self.object_type,
                farm_id=getattr(row, "farm_id"),
                business_id_value=business_id(row),
                mysql_id=getattr(row, "id", None),
                operation=operation,
                exc=exc,
            )


class DualWritePrelabelRepository(_DualWriteBase[AgentDataFlywheelPrelabel]):
    object_type = "prelabel"

    async def create(self, row: AgentDataFlywheelPrelabel) -> AgentDataFlywheelPrelabel:
        return await self._dual_create(row)

    def get_by_id_and_sample(self, **kwargs):
        return self._mysql.get_by_id_and_sample(**kwargs)

    def list_by_samples(self, **kwargs):
        return self._mysql.list_by_samples(**kwargs)

    async def update_review_fields(self, **kwargs):
        row = self._mysql.update_review_fields(**kwargs)
        if row is not None:
            await self._write_secondary("create", row)
        return row


class DualWriteCaseDraftRepository(_DualWriteBase[AgentCaseDraft]):
    object_type = "case_draft"

    async def create(self, row: AgentCaseDraft) -> AgentCaseDraft:
        return await self._dual_create(row)

    def get_by_draft_id(self, **kwargs):
        return self._mysql.get_by_draft_id(**kwargs)

    def list_by_source_sample(self, **kwargs):
        return self._mysql.list_by_source_sample(**kwargs)


class DualWriteRepairPackRepository(_DualWriteBase[AgentRepairPack]):
    object_type = "repair_pack"

    async def create(self, row: AgentRepairPack) -> AgentRepairPack:
        return await self._dual_create(row)

    def get_by_pack_id(self, **kwargs):
        return self._mysql.get_by_pack_id(**kwargs)

    def list(self, **kwargs):
        return self._mysql.list(**kwargs)

    def find_active_by_dedup_key(self, **kwargs):
        return self._mysql.find_active_by_dedup_key(**kwargs)

    async def update_fields(self, **kwargs):
        row = self._mysql.update_fields(**kwargs)
        if row is not None:
            await self._write_secondary("create", row)
        return row


class DualWriteReviewIssueChainRepository(_DualWriteBase[AgentReviewIssueChain]):
    object_type = "review_issue_chain"

    async def save(self, row: AgentReviewIssueChain) -> AgentReviewIssueChain:
        saved = self._mysql.save(row)
        await self._write_secondary("save", saved)
        return saved

    def get_by_chain_id(self, **kwargs):
        return self._mysql.get_by_chain_id(**kwargs)

    def list_by_session(self, **kwargs):
        return self._mysql.list_by_session(**kwargs)

    async def update_review_fields(self, **kwargs):
        row = self._mysql.update_review_fields(**kwargs)
        if row is not None:
            await self._write_secondary("save", row)
        return row

    async def update_ai_judge_fields(self, **kwargs):
        row = self._mysql.update_ai_judge_fields(**kwargs)
        if row is not None:
            await self._write_secondary("save", row)
        return row


class MongoReadPrelabelRepository(DualWritePrelabelRepository):
    async def get_by_id_and_sample(self, **kwargs):
        return await _mongo_read_one(
            self._mongo.get_by_id_and_sample,
            self._mysql.get_by_id_and_sample,
            self.object_type,
            str(kwargs.get("prelabel_id")),
            kwargs,
        )

    async def list_by_samples(self, **kwargs):
        return await _mongo_read_many(
            self._mongo.list_by_samples,
            self._mysql.list_by_samples,
            self.object_type,
            str(kwargs.get("sample_ids")),
            kwargs,
        )


class MongoReadCaseDraftRepository(DualWriteCaseDraftRepository):
    async def get_by_draft_id(self, **kwargs):
        return await _mongo_read_one(
            self._mongo.get_by_draft_id,
            self._mysql.get_by_draft_id,
            self.object_type,
            str(kwargs.get("draft_id")),
            kwargs,
        )

    async def list_by_source_sample(self, **kwargs):
        return await _mongo_read_page(
            self._mongo.list_by_source_sample,
            self._mysql.list_by_source_sample,
            self.object_type,
            str(kwargs.get("source_sample_id")),
            kwargs,
        )


class MongoReadRepairPackRepository(DualWriteRepairPackRepository):
    async def get_by_pack_id(self, **kwargs):
        return await _mongo_read_one(
            self._mongo.get_by_pack_id,
            self._mysql.get_by_pack_id,
            self.object_type,
            str(kwargs.get("pack_id")),
            kwargs,
        )

    async def list(self, **kwargs):
        return await _mongo_read_page(
            self._mongo.list,
            self._mysql.list,
            self.object_type,
            "list",
            kwargs,
        )

    async def find_active_by_dedup_key(self, **kwargs):
        return await _mongo_read_one(
            self._mongo.find_active_by_dedup_key,
            self._mysql.find_active_by_dedup_key,
            self.object_type,
            str(kwargs.get("dedup_key")),
            kwargs,
        )


class MongoReadReviewIssueChainRepository(DualWriteReviewIssueChainRepository):
    async def get_by_chain_id(self, **kwargs):
        return await _mongo_read_one(
            self._mongo.get_by_chain_id,
            self._mysql.get_by_chain_id,
            self.object_type,
            str(kwargs.get("chain_id")),
            kwargs,
        )

    async def list_by_session(self, **kwargs):
        return await _mongo_read_page(
            self._mongo.list_by_session,
            self._mysql.list_by_session,
            self.object_type,
            str(kwargs.get("session_id")),
            kwargs,
        )


async def _mongo_read_one(mongo_method, mysql_method, object_type, business, kwargs):
    farm_id = kwargs.get("farm_id")
    try:
        row = await mongo_method(**kwargs)
        if row is not None:
            return row
        log_read_fallback(object_type, farm_id, business, "mongo_miss")
    except Exception as exc:
        log_read_fallback(object_type, farm_id, business, redact_error(exc))
    return mysql_method(**kwargs)


async def _mongo_read_many(mongo_method, mysql_method, object_type, business, kwargs):
    farm_id = kwargs.get("farm_id")
    try:
        rows = await mongo_method(**kwargs)
        if rows:
            return rows
        log_read_fallback(object_type, farm_id, business, "mongo_miss")
    except Exception as exc:
        log_read_fallback(object_type, farm_id, business, redact_error(exc))
    return mysql_method(**kwargs)


async def _mongo_read_page(mongo_method, mysql_method, object_type, business, kwargs):
    farm_id = kwargs.get("farm_id")
    try:
        page = await mongo_method(**kwargs)
        if page.total:
            return page
        log_read_fallback(object_type, farm_id, business, "mongo_miss")
    except Exception as exc:
        log_read_fallback(object_type, farm_id, business, redact_error(exc))
    return mysql_method(**kwargs)
