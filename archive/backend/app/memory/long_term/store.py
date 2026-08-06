"""长期记忆 SQL store。"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.memory.long_term.models import MemoryRecord
from app.memory.models import (
    FarmProfileMemory,
    KeyFactMemory,
    LedgerSummaryMemory,
    LongTermMemoryContext,
    UserPreferenceMemory,
)
from app.shared.compatibility import StrEnum
from app.shared.database import SessionLocal

logger = logging.getLogger(__name__)


class MemoryRecordStatus(StrEnum):
    """长期记忆生命周期状态。"""

    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class MemoryRecordType(StrEnum):
    """第一版支持的长期记忆类型。"""

    PREFERENCE = "preference"
    ALIAS = "alias"
    FACT = "fact"
    FARM_PROFILE = "farm_profile"
    LEDGER_SUMMARY = "ledger_summary"


class MemoryRecordSource(StrEnum):
    """长期记忆来源。"""

    USER_EXPLICIT = "user_explicit"


SessionFactory = Callable[[], Session]


class MemoryRecordStore:
    """面向 Memory 边界的长期记忆读写接口。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_confirmed(
        self,
        *,
        farm_id: int,
        user_id: str,
        memory_type: MemoryRecordType | str,
        content: str,
        importance: float = 0.8,
        confidence: float = 1.0,
        source: MemoryRecordSource | str = MemoryRecordSource.USER_EXPLICIT,
    ) -> MemoryRecord:
        """创建 confirmed 记忆；同 farm/user/type/content 已存在时复用。"""
        normalized_type = _normalize_enum(memory_type, MemoryRecordType)
        normalized_source = _normalize_enum(source, MemoryRecordSource)
        normalized_content = _compact_text(content)
        existing = self._find_live_record(
            farm_id=farm_id,
            user_id=user_id,
            memory_type=normalized_type,
            content=normalized_content,
        )
        if existing is not None:
            return existing

        record = MemoryRecord(
            memory_id=uuid.uuid4().hex,
            farm_id=farm_id,
            user_id=user_id,
            type=normalized_type,
            content=normalized_content,
            status=MemoryRecordStatus.CONFIRMED.value,
            source=normalized_source,
            importance=importance,
            confidence=confidence,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def build_context(
        self,
        *,
        farm_id: int,
        user_id: str,
        limit: int = 5,
    ) -> LongTermMemoryContext:
        """读取同 farm/user 下可注入的 confirmed 记忆。"""
        records = (
            self.db.query(MemoryRecord)
            .filter(
                MemoryRecord.farm_id == farm_id,
                MemoryRecord.user_id == user_id,
                MemoryRecord.status == MemoryRecordStatus.CONFIRMED.value,
            )
            .order_by(
                MemoryRecord.importance.desc(),
                MemoryRecord.updated_at.desc(),
                MemoryRecord.id.desc(),
            )
            .limit(limit)
            .all()
        )
        return _records_to_context(records)

    def archive(
        self,
        *,
        farm_id: int,
        user_id: str,
        memory_id: str,
    ) -> MemoryRecord | None:
        """归档一条用户显式记忆。"""
        record = (
            self.db.query(MemoryRecord)
            .filter(
                MemoryRecord.farm_id == farm_id,
                MemoryRecord.user_id == user_id,
                MemoryRecord.memory_id == memory_id,
                MemoryRecord.status != MemoryRecordStatus.ARCHIVED.value,
            )
            .first()
        )
        if record is None:
            return None
        record.status = MemoryRecordStatus.ARCHIVED.value
        record.archived_at = datetime.now()
        record.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(record)
        return record

    def _find_live_record(
        self,
        *,
        farm_id: int,
        user_id: str,
        memory_type: str,
        content: str,
    ) -> MemoryRecord | None:
        return (
            self.db.query(MemoryRecord)
            .filter(
                MemoryRecord.farm_id == farm_id,
                MemoryRecord.user_id == user_id,
                MemoryRecord.type == memory_type,
                MemoryRecord.content == content,
                MemoryRecord.status != MemoryRecordStatus.ARCHIVED.value,
            )
            .first()
        )


class SQLLongTermMemoryStore:
    """供全局 MemoryService 使用的只读长期记忆 store。"""

    def __init__(self, session_factory: SessionFactory = SessionLocal) -> None:
        self.session_factory = session_factory

    async def build_context(
        self,
        user_id: str,
        farm_id: int,
    ) -> LongTermMemoryContext:
        """使用独立 session 读取长期记忆，失败时降级为空上下文。"""
        if not user_id:
            return LongTermMemoryContext()
        db = self.session_factory()
        try:
            return MemoryRecordStore(db).build_context(
                farm_id=farm_id,
                user_id=user_id,
            )
        except Exception:
            logger.exception(
                "长期记忆上下文读取失败",
                extra={
                    "code": "LONG_TERM_MEMORY_CONTEXT_FAILED",
                    "farm_id": farm_id,
                    "user_id": user_id,
                },
            )
            return LongTermMemoryContext()
        finally:
            db.close()


def _records_to_context(records: list[MemoryRecord]) -> LongTermMemoryContext:
    preferences: list[UserPreferenceMemory] = []
    farm_profiles: list[FarmProfileMemory] = []
    key_facts: list[KeyFactMemory] = []
    ledger_summaries: list[LedgerSummaryMemory] = []

    for record in records:
        metadata = {"memory_id": record.memory_id, "source": record.source}
        if record.type == MemoryRecordType.PREFERENCE.value:
            preferences.append(
                UserPreferenceMemory(
                    key=record.type,
                    value=record.content,
                    confidence=record.confidence,
                    metadata=metadata,
                )
            )
        elif record.type == MemoryRecordType.FARM_PROFILE.value:
            farm_profiles.append(
                FarmProfileMemory(
                    farm_id=record.farm_id,
                    summary=record.content,
                    metadata=metadata,
                )
            )
        elif record.type == MemoryRecordType.LEDGER_SUMMARY.value:
            ledger_summaries.append(
                LedgerSummaryMemory(
                    period="long_term",
                    summary=record.content,
                    metadata=metadata,
                )
            )
        else:
            key_facts.append(
                KeyFactMemory(
                    fact=record.content,
                    source=record.source,
                    confidence=record.confidence,
                    metadata=metadata,
                )
            )

    return LongTermMemoryContext(
        user_preferences=preferences,
        farm_profiles=farm_profiles,
        key_facts=key_facts,
        ledger_summaries=ledger_summaries,
    )


def _normalize_enum(value, enum_cls: type[StrEnum]) -> str:
    normalized = value.value if isinstance(value, enum_cls) else str(value)
    allowed = {item.value for item in enum_cls}
    if normalized not in allowed:
        raise ValueError(f"不支持的长期记忆字段: {normalized}")
    return normalized


def _compact_text(text: str) -> str:
    return " ".join(str(text or "").strip().split())


__all__ = [
    "MemoryRecordSource",
    "MemoryRecordStatus",
    "MemoryRecordStore",
    "MemoryRecordType",
    "SQLLongTermMemoryStore",
]
