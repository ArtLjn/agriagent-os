"""Data Flywheel 文档 Repository backend selector。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.platforms.data_flywheel.document_repository_mongo import (
    MongoCaseDraftRepository,
    MongoPrelabelRepository,
    MongoRepairPackRepository,
    MongoReviewIssueChainRepository,
)
from app.platforms.data_flywheel.document_repository_mysql import (
    MySQLCaseDraftRepository,
    MySQLPrelabelRepository,
    MySQLRepairPackRepository,
    MySQLReviewIssueChainRepository,
)


def build_data_flywheel_repository(
    object_name: str,
    backend: str,
    db: Session,
    collection: Any | None = None,
    on_secondary_failure=None,
) -> Any:
    """按对象名和可验证 backend 创建 Data Flywheel Repository。"""
    _ = on_secondary_failure
    registry = {
        "prelabels": (MySQLPrelabelRepository, MongoPrelabelRepository),
        "case_drafts": (MySQLCaseDraftRepository, MongoCaseDraftRepository),
        "repair_packs": (MySQLRepairPackRepository, MongoRepairPackRepository),
        "review_issue_chains": (
            MySQLReviewIssueChainRepository,
            MongoReviewIssueChainRepository,
        ),
    }
    if object_name not in registry:
        raise ValueError(
            {"code": "UNKNOWN_DATA_FLYWHEEL_OBJECT", "object": object_name}
        )
    mysql_cls, mongo_cls = registry[object_name]
    if backend == "mysql":
        return mysql_cls(db)
    if backend != "mongo":
        raise ValueError({"code": "INVALID_STORAGE_BACKEND", "backend": backend})
    if collection is None:
        raise ValueError("MONGO_COLLECTION_REQUIRED")
    return mongo_cls(collection)
