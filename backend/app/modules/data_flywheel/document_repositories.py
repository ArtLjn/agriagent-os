"""Data Flywheel 文档对象 Repository 对外导出门面。"""

from __future__ import annotations

from app.modules.data_flywheel.document_repository_common import (
    CaseDraftRepository,
    PrelabelRepository,
    RepairPackRepository,
    RepositoryPage,
    ReviewIssueChainRepository,
)
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
from app.platforms.shared.repository_selector import (
    build_data_flywheel_repository,
)

__all__ = [
    "CaseDraftRepository",
    "DualWriteCaseDraftRepository",
    "DualWritePrelabelRepository",
    "DualWriteRepairPackRepository",
    "DualWriteReviewIssueChainRepository",
    "MongoCaseDraftRepository",
    "MongoPrelabelRepository",
    "MongoReadCaseDraftRepository",
    "MongoReadPrelabelRepository",
    "MongoReadRepairPackRepository",
    "MongoReadReviewIssueChainRepository",
    "MongoRepairPackRepository",
    "MongoReviewIssueChainRepository",
    "MySQLCaseDraftRepository",
    "MySQLPrelabelRepository",
    "MySQLRepairPackRepository",
    "MySQLReviewIssueChainRepository",
    "PrelabelRepository",
    "RepairPackRepository",
    "RepositoryPage",
    "ReviewIssueChainRepository",
    "build_data_flywheel_repository",
]
