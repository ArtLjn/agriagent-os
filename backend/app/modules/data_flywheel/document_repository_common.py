"""Data Flywheel 文档 Repository 公共类型与工具。"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, Protocol, TypeVar

from sqlalchemy.orm import Session

from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelPrelabel,
    AgentRepairPack,
    AgentReviewIssueChain,
)

logger = logging.getLogger(__name__)
ModelT = TypeVar("ModelT")


@dataclass(frozen=True)
class RepositoryPage(Generic[ModelT]):
    """Repository 分页结果。"""

    items: list[ModelT]
    total: int
    page: int = 1
    page_size: int = 20


class PrelabelRepository(Protocol):
    """预标注 Repository 接口。"""

    def create(self, row: AgentDataFlywheelPrelabel) -> AgentDataFlywheelPrelabel: ...

    def get_by_id_and_sample(
        self, *, farm_id: int, prelabel_id: int, sample_id: str
    ) -> AgentDataFlywheelPrelabel | None: ...

    def list_by_samples(
        self, *, farm_id: int, sample_ids: list[str]
    ) -> list[AgentDataFlywheelPrelabel]: ...

    def update_review_fields(
        self,
        *,
        farm_id: int,
        prelabel_id: int,
        sample_id: str,
        status: str,
        reviewed_by: str | None = None,
        reviewed_at: datetime | None = None,
        accepted_label_ids: list[int] | None = None,
    ) -> AgentDataFlywheelPrelabel | None: ...


class CaseDraftRepository(Protocol):
    """用例草稿 Repository 接口。"""

    def create(self, row: AgentCaseDraft) -> AgentCaseDraft: ...

    def get_by_draft_id(
        self, *, farm_id: int, draft_id: str
    ) -> AgentCaseDraft | None: ...

    def list_by_source_sample(
        self, *, farm_id: int, source_sample_id: str, limit: int = 20, offset: int = 0
    ) -> RepositoryPage[AgentCaseDraft]: ...


class RepairPackRepository(Protocol):
    """修复包 Repository 接口。"""

    def create(self, row: AgentRepairPack) -> AgentRepairPack: ...

    def get_by_pack_id(
        self, *, farm_id: int, pack_id: str
    ) -> AgentRepairPack | None: ...

    def list(
        self,
        *,
        farm_id: int,
        status: str | None = None,
        fix_target: str | None = None,
        include_discarded: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> RepositoryPage[AgentRepairPack]: ...

    def find_active_by_dedup_key(
        self, *, farm_id: int, dedup_key: str
    ) -> AgentRepairPack | None: ...

    def update_fields(
        self, *, farm_id: int, pack_id: str, **fields: Any
    ) -> AgentRepairPack | None: ...


class ReviewIssueChainRepository(Protocol):
    """问题链 Repository 接口。"""

    def get_by_chain_id(
        self, *, farm_id: int, chain_id: str
    ) -> AgentReviewIssueChain | None: ...

    def save(self, row: AgentReviewIssueChain) -> AgentReviewIssueChain: ...

    def list_by_session(
        self,
        *,
        farm_id: int,
        session_id: str,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> RepositoryPage[AgentReviewIssueChain]: ...

    def list(
        self,
        *,
        farm_id: int,
        session_id: str | None = None,
        severity: str = "all",
        limit: int = 1000,
        offset: int = 0,
    ) -> RepositoryPage[AgentReviewIssueChain]: ...

    def update_review_fields(
        self, *, farm_id: int, chain_id: str, **fields: Any
    ) -> AgentReviewIssueChain | None: ...

    def update_ai_judge_fields(
        self, *, farm_id: int, chain_id: str, ai_judge: dict[str, Any]
    ) -> AgentReviewIssueChain | None: ...


def insert_row(db: Session, row: ModelT) -> ModelT:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def apply_fields(row: Any, fields: dict[str, Any]) -> None:
    for key, value in fields.items():
        if hasattr(row, key):
            setattr(row, key, value)


def farm_filter(farm_id: int, **conditions: Any) -> dict[str, Any]:
    if farm_id is None:
        raise ValueError("MONGO_FARM_ID_REQUIRED")
    return {"farmId": farm_id, **conditions}


def mongo_update(fields: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "reviewed_by": "reviewedBy",
        "reviewed_at": "reviewedAt",
        "accepted_label_ids": "acceptedLabelIds",
        "repair_note": "repairNote",
        "verification_summary": "verificationSummary",
        "resolved_by": "resolvedBy",
        "resolved_at": "resolvedAt",
        "export_path": "exportPath",
        "export_error": "exportError",
        "manifest_json": "manifestJson",
        "source_label_ids": "sourceLabelIds",
        "reviewer_comment": "reviewerComment",
        "false_positive_reason": "falsePositiveReason",
        "missing_evidence": "missingEvidence",
        "reviewer_id": "reviewerId",
        "ai_judge": "aiJudge",
        "dominant_signal": "dominantSignal",
        "final_labels": "finalLabels",
        "root_cause": "rootCause",
        "expected_behavior": "expectedBehavior",
        "fix_target": "fixTarget",
    }
    return {mapping.get(key, key): value for key, value in fields.items()}


def business_id(row: Any) -> str | None:
    for attr in ("pack_id", "draft_id", "chain_id", "sample_id"):
        value = getattr(row, attr, None)
        if value:
            return str(value)
    row_id = getattr(row, "id", None)
    return str(row_id) if row_id is not None else None


def handle_secondary_failure(
    *,
    hook,
    object_type: str,
    farm_id: int,
    business_id_value: str | None,
    mysql_id: int | None,
    operation: str,
    exc: Exception,
) -> None:
    payload = {
        "code": "mongo_secondary_write_failed",
        "object_type": object_type,
        "farm_id": farm_id,
        "business_id": business_id_value,
        "mysql_id": mysql_id,
        "operation": operation,
        "error": redact_error(exc),
    }
    logger.warning(
        "Mongo 二级写失败 | code=%s object_type=%s farm_id=%s business_id=%s mysql_id=%s error=%s",
        payload["code"],
        object_type,
        farm_id,
        business_id_value,
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
                business_id_value,
                mysql_id,
                redact_error(hook_exc),
            )


def redact_error(exc: Exception) -> str:
    return re.sub(
        r"(mongodb(?:\+srv)?://[^:/\s@]+:)[^@\s]+@",
        r"\1***@",
        str(exc),
    )


def log_read_fallback(
    object_type: str,
    farm_id: int,
    business_id_value: str,
    reason: str,
) -> None:
    logger.warning(
        "Mongo 读回退 MySQL | code=mongo_read_fallback_to_mysql object_type=%s farm_id=%s business_id=%s reason=%s",
        object_type,
        farm_id,
        business_id_value,
        reason,
    )
