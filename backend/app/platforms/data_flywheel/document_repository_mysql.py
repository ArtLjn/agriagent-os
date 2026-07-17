"""Data Flywheel 文档对象 MySQL Repository。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.data_flywheel import (
    AgentCaseDraft,
    AgentDataFlywheelPrelabel,
    AgentRepairPack,
    AgentReviewIssueChain,
)
from app.platforms.data_flywheel.document_repository_common import (
    RepositoryPage,
    apply_fields,
    insert_row,
)


class MySQLPrelabelRepository:
    """MySQL 预标注 Repository。"""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, row: AgentDataFlywheelPrelabel) -> AgentDataFlywheelPrelabel:
        return insert_row(self._db, row)

    def get_by_id_and_sample(
        self, *, farm_id: int, prelabel_id: int, sample_id: str
    ) -> AgentDataFlywheelPrelabel | None:
        return (
            self._db.query(AgentDataFlywheelPrelabel)
            .filter(
                AgentDataFlywheelPrelabel.id == prelabel_id,
                AgentDataFlywheelPrelabel.farm_id == farm_id,
                AgentDataFlywheelPrelabel.sample_id == sample_id,
            )
            .first()
        )

    def list_by_samples(
        self, *, farm_id: int, sample_ids: list[str]
    ) -> list[AgentDataFlywheelPrelabel]:
        if not sample_ids:
            return []
        return (
            self._db.query(AgentDataFlywheelPrelabel)
            .filter(
                AgentDataFlywheelPrelabel.farm_id == farm_id,
                AgentDataFlywheelPrelabel.sample_id.in_(sample_ids),
            )
            .order_by(
                AgentDataFlywheelPrelabel.created_at.desc(),
                AgentDataFlywheelPrelabel.id.desc(),
            )
            .all()
        )

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
    ) -> AgentDataFlywheelPrelabel | None:
        row = self.get_by_id_and_sample(
            farm_id=farm_id,
            prelabel_id=prelabel_id,
            sample_id=sample_id,
        )
        if row is None:
            return None
        row.status = status
        row.reviewed_by = reviewed_by
        row.reviewed_at = reviewed_at
        row.accepted_label_ids = accepted_label_ids
        self._db.commit()
        self._db.refresh(row)
        return row


class MySQLCaseDraftRepository:
    """MySQL 用例草稿 Repository。"""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, row: AgentCaseDraft) -> AgentCaseDraft:
        return insert_row(self._db, row)

    def get_by_draft_id(self, *, farm_id: int, draft_id: str) -> AgentCaseDraft | None:
        return (
            self._db.query(AgentCaseDraft)
            .filter(
                AgentCaseDraft.farm_id == farm_id,
                AgentCaseDraft.draft_id == draft_id,
            )
            .first()
        )

    def list_by_source_sample(
        self, *, farm_id: int, source_sample_id: str, limit: int = 20, offset: int = 0
    ) -> RepositoryPage[AgentCaseDraft]:
        query = self._db.query(AgentCaseDraft).filter(
            AgentCaseDraft.farm_id == farm_id,
            AgentCaseDraft.source_sample_id == source_sample_id,
        )
        total = query.count()
        items = (
            query.order_by(desc(AgentCaseDraft.created_at), desc(AgentCaseDraft.id))
            .offset(max(offset, 0))
            .limit(max(limit, 0))
            .all()
        )
        return RepositoryPage(items=items, total=total, page_size=limit)


class MySQLRepairPackRepository:
    """MySQL 修复包 Repository。"""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, row: AgentRepairPack) -> AgentRepairPack:
        return insert_row(self._db, row)

    def get_by_pack_id(self, *, farm_id: int, pack_id: str) -> AgentRepairPack | None:
        return (
            self._db.query(AgentRepairPack)
            .filter(
                AgentRepairPack.farm_id == farm_id,
                AgentRepairPack.pack_id == pack_id,
            )
            .first()
        )

    def list(
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
        query = self._db.query(AgentRepairPack).filter(
            AgentRepairPack.farm_id == farm_id
        )
        if status:
            query = query.filter(AgentRepairPack.status == status)
        elif not include_discarded:
            query = query.filter(AgentRepairPack.status != "discarded")
        if fix_target:
            query = query.filter(AgentRepairPack.fix_target == fix_target)
        total = query.count()
        items = (
            query.order_by(desc(AgentRepairPack.created_at), desc(AgentRepairPack.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return RepositoryPage(items=items, total=total, page=page, page_size=page_size)

    def find_active_by_dedup_key(
        self, *, farm_id: int, dedup_key: str
    ) -> AgentRepairPack | None:
        return (
            self._db.query(AgentRepairPack)
            .filter(
                AgentRepairPack.farm_id == farm_id,
                AgentRepairPack.dedup_key == dedup_key,
                AgentRepairPack.status != "discarded",
            )
            .order_by(desc(AgentRepairPack.created_at), desc(AgentRepairPack.id))
            .first()
        )

    def update_fields(
        self, *, farm_id: int, pack_id: str, **fields: Any
    ) -> AgentRepairPack | None:
        row = self.get_by_pack_id(farm_id=farm_id, pack_id=pack_id)
        if row is None:
            return None
        apply_fields(row, fields)
        self._db.commit()
        self._db.refresh(row)
        return row


class MySQLReviewIssueChainRepository:
    """MySQL 问题链 Repository。"""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_chain_id(
        self, *, farm_id: int, chain_id: str
    ) -> AgentReviewIssueChain | None:
        return (
            self._db.query(AgentReviewIssueChain)
            .filter(
                AgentReviewIssueChain.farm_id == farm_id,
                AgentReviewIssueChain.chain_id == chain_id,
            )
            .first()
        )

    def save(self, row: AgentReviewIssueChain) -> AgentReviewIssueChain:
        existing = (
            self.get_by_chain_id(farm_id=row.farm_id, chain_id=row.chain_id)
            if row.chain_id
            else None
        )
        if existing is None:
            return insert_row(self._db, row)
        values = {
            column.name: getattr(row, column.name)
            for column in AgentReviewIssueChain.__table__.columns
            if column.name != "id"
        }
        apply_fields(existing, values)
        self._db.commit()
        self._db.refresh(existing)
        return existing

    def list_by_session(
        self,
        *,
        farm_id: int,
        session_id: str,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> RepositoryPage[AgentReviewIssueChain]:
        query = self._db.query(AgentReviewIssueChain).filter(
            AgentReviewIssueChain.farm_id == farm_id,
            AgentReviewIssueChain.session_id == session_id,
        )
        if status:
            query = query.filter(AgentReviewIssueChain.status == status)
        total = query.count()
        items = (
            query.order_by(
                AgentReviewIssueChain.severity.asc(),
                desc(AgentReviewIssueChain.updated_at),
                desc(AgentReviewIssueChain.id),
            )
            .offset(max(offset, 0))
            .limit(max(limit, 0))
            .all()
        )
        return RepositoryPage(items=items, total=total, page_size=limit)

    def list(
        self,
        *,
        farm_id: int,
        session_id: str | None = None,
        severity: str = "all",
        limit: int = 1000,
        offset: int = 0,
    ) -> RepositoryPage[AgentReviewIssueChain]:
        query = self._db.query(AgentReviewIssueChain).filter(
            AgentReviewIssueChain.farm_id == farm_id,
        )
        if session_id:
            query = query.filter(AgentReviewIssueChain.session_id == session_id)
        if severity != "all":
            query = query.filter(AgentReviewIssueChain.severity == severity)
        total = query.count()
        items = (
            query.order_by(
                AgentReviewIssueChain.severity.asc(),
                desc(AgentReviewIssueChain.updated_at),
                desc(AgentReviewIssueChain.id),
            )
            .offset(max(offset, 0))
            .limit(max(limit, 0))
            .all()
        )
        return RepositoryPage(items=items, total=total, page_size=limit)

    def update_review_fields(
        self, *, farm_id: int, chain_id: str, **fields: Any
    ) -> AgentReviewIssueChain | None:
        return self._update_fields(farm_id=farm_id, chain_id=chain_id, fields=fields)

    def update_ai_judge_fields(
        self, *, farm_id: int, chain_id: str, ai_judge: dict[str, Any]
    ) -> AgentReviewIssueChain | None:
        return self._update_fields(
            farm_id=farm_id,
            chain_id=chain_id,
            fields={"ai_judge": ai_judge, "dominant_signal": "judge"},
        )

    def _update_fields(
        self, *, farm_id: int, chain_id: str, fields: dict[str, Any]
    ) -> AgentReviewIssueChain | None:
        row = self.get_by_chain_id(farm_id=farm_id, chain_id=chain_id)
        if row is None:
            return None
        apply_fields(row, fields)
        self._db.commit()
        self._db.refresh(row)
        return row
