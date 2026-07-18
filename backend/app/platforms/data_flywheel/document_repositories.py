"""Data Flywheel 文档对象 Repository 对外导出门面。"""

from __future__ import annotations

from app.platforms.data_flywheel.document_repository_common import RepositoryPage
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
from app.platforms.shared.repository_selector import (
    build_data_flywheel_repository,
)

__all__ = [
    "MongoCaseDraftRepository",
    "MongoPrelabelRepository",
    "MongoRepairPackRepository",
    "MongoReviewIssueChainRepository",
    "MySQLCaseDraftRepository",
    "MySQLPrelabelRepository",
    "MySQLRepairPackRepository",
    "MySQLReviewIssueChainRepository",
    "RepositoryPage",
    "build_data_flywheel_repository",
]
