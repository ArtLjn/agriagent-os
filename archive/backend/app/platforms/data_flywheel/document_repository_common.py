"""Data Flywheel Mongo 文档 Repository 公共工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


@dataclass(frozen=True)
class RepositoryPage(Generic[ModelT]):
    """Repository 分页结果。"""

    items: list[ModelT]
    total: int
    page: int = 1
    page_size: int = 20


def farm_filter(farm_id: int, **conditions: Any) -> dict[str, Any]:
    if farm_id is None:
        raise ValueError("MONGO_FARM_ID_REQUIRED")
    return {"farmId": farm_id, **conditions}


def insert_row(db: Session, row: ModelT) -> ModelT:
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def apply_fields(row: Any, fields: dict[str, Any]) -> None:
    for key, value in fields.items():
        if hasattr(row, key):
            setattr(row, key, value)


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
