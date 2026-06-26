"""Data Flywheel 文档 Repository backend selector。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.modules.data_flywheel.document_repository_dual import (
    DualWriteCaseDraftRepository,
    DualWritePrelabelRepository,
    DualWriteRepairPackRepository,
    DualWriteReviewIssueChainRepository,
    MongoReadCaseDraftRepository,
    MongoReadPrelabelRepository,
    MongoReadRepairPackRepository,
    MongoReadReviewIssueChainRepository,
)
from app.modules.data_flywheel.document_repository_mongo import (
    MongoCaseDraftRepository,
    MongoPrelabelRepository,
    MongoRepairPackRepository,
    MongoReviewIssueChainRepository,
)
from app.modules.data_flywheel.document_repository_mysql import (
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
    """按对象名和 storage backend 创建 Data Flywheel Repository。"""
    registry = {
        "prelabels": (
            MySQLPrelabelRepository,
            MongoPrelabelRepository,
            DualWritePrelabelRepository,
            MongoReadPrelabelRepository,
        ),
        "case_drafts": (
            MySQLCaseDraftRepository,
            MongoCaseDraftRepository,
            DualWriteCaseDraftRepository,
            MongoReadCaseDraftRepository,
        ),
        "repair_packs": (
            MySQLRepairPackRepository,
            MongoRepairPackRepository,
            DualWriteRepairPackRepository,
            MongoReadRepairPackRepository,
        ),
        "review_issue_chains": (
            MySQLReviewIssueChainRepository,
            MongoReviewIssueChainRepository,
            DualWriteReviewIssueChainRepository,
            MongoReadReviewIssueChainRepository,
        ),
    }
    if object_name not in registry:
        raise ValueError(
            {"code": "UNKNOWN_DATA_FLYWHEEL_OBJECT", "object": object_name}
        )
    mysql_cls, mongo_cls, dual_cls, mongo_read_cls = registry[object_name]
    mysql_repo = mysql_cls(db)
    if backend == "mysql":
        return mysql_repo
    if collection is None:
        raise ValueError("MONGO_COLLECTION_REQUIRED")
    mongo_repo = mongo_cls(collection)
    if backend == "dual":
        return dual_cls(mysql_repo, mongo_repo, on_secondary_failure)
    if backend == "mongo-read":
        return mongo_read_cls(mysql_repo, mongo_repo, on_secondary_failure)
    if backend == "mongo":
        return mongo_repo
    raise ValueError({"code": "INVALID_STORAGE_BACKEND", "backend": backend})
