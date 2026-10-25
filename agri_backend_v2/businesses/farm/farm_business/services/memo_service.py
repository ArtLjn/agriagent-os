"""备忘录业务边界：内容校验、用户隔离、幂等创建与归档。"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from farm_business.models import Memo

logger = logging.getLogger(__name__)
MYSQL_TABLE_MISSING = 1146

MAX_RESULTS = 100
DEFAULT_RESULTS = 20
MAX_CONTENT_LENGTH = 10000


class MemoError(ValueError):
    """为 REST 和 MCP 提供相同的错误码与上下文。"""

    def __init__(self, code: str, message: str, **meta):
        super().__init__(message)
        self.code, self.meta = code, meta


def storage_error(exc: SQLAlchemyError, *, operation: str) -> MemoError:
    """协议边界只返回可行动的错误，避免 SQL 参数中的用户内容外泄。"""
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    missing = bool(args) and (
        args[0] == MYSQL_TABLE_MISSING or str(args[0]) == "no such table: memos"
    )
    code = "memo_schema_not_ready" if missing else "memo_storage_unavailable"
    logger.error(
        "memo_storage_failed",
        extra={"code": code, "operation": operation, "error_type": type(exc).__name__},
    )
    message = (
        "备忘录数据表尚未初始化，请联系管理员完成数据库迁移后重试"
        if missing
        else "备忘录暂时无法保存或读取，请稍后重试"
    )
    return MemoError(code, message, operation=operation)


class MemoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)
    pinned: bool = False
    client_request_id: str = Field(min_length=1, max_length=100)


class MemoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(
        default=None, min_length=1, max_length=MAX_CONTENT_LENGTH
    )
    pinned: bool | None = None
    archived: bool | None = None


def serialize(item: Memo) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "content": item.content,
        "pinned": item.pinned,
        "archived": item.archived,
        "created_at": item.created_at.replace(tzinfo=UTC).isoformat(),
        "updated_at": item.updated_at.replace(tzinfo=UTC).isoformat(),
    }


def list_memos(
    db: Session,
    *,
    farm_id: int,
    user_id: str,
    keyword: str = "",
    archived: bool = False,
    limit: int = DEFAULT_RESULTS,
    skip: int = 0,
) -> dict:
    """仅搜索当前用户在当前农场的笔记，置顶优先；百分号按字面量搜索。"""
    if not 1 <= limit <= MAX_RESULTS or skip < 0 or len(keyword) > 200:
        raise MemoError(
            "validation_error", "搜索或分页参数超出范围", limit=limit, skip=skip
        )
    query = db.query(Memo).filter(
        Memo.farm_id == farm_id, Memo.user_id == user_id, Memo.archived == archived
    )
    if keyword.strip():
        query = query.filter(
            or_(
                Memo.title.contains(keyword.strip(), autoescape=True),
                Memo.content.contains(keyword.strip(), autoescape=True),
            )
        )
    total = query.count()
    rows = (
        query.order_by(Memo.pinned.desc(), Memo.updated_at.desc(), Memo.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {"items": [serialize(row) for row in rows], "total": total}


def create_memo(
    db: Session, *, farm_id: int, user_id: str, request: MemoCreate
) -> dict:
    """同一请求键只创建一次，不同内容复用请求键时拒绝覆盖。"""
    fingerprint = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
    query = db.query(Memo).filter(
        Memo.farm_id == farm_id,
        Memo.user_id == user_id,
        Memo.client_request_id == request.client_request_id,
    )
    existing = query.first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise MemoError("idempotency_conflict", "同一请求标识已用于不同备忘录")
        return serialize(existing)
    now = datetime.now(UTC).replace(tzinfo=None)
    item = Memo(
        farm_id=farm_id,
        user_id=user_id,
        **request.model_dump(),
        archived=False,
        request_fingerprint=fingerprint,
        created_at=now,
        updated_at=now,
    )
    try:
        # 数据库唯一约束兜底并发重试，保存点避免冲突破坏调用方事务。
        with db.begin_nested():
            db.add(item)
            db.flush()
    except IntegrityError:
        existing = query.populate_existing().with_for_update().first()
        if existing is None:
            raise
        if existing.request_fingerprint != fingerprint:
            raise MemoError(
                "idempotency_conflict", "同一请求标识已用于不同备忘录"
            ) from None
        return serialize(existing)
    return serialize(item)


def update_memo(
    db: Session, *, farm_id: int, user_id: str, memo_id: int, request: MemoUpdate
) -> dict:
    """对所属用户的笔记加锁编辑；归档可恢复，不删除用户原始记录。"""
    item = (
        db.query(Memo)
        .filter(Memo.id == memo_id, Memo.farm_id == farm_id, Memo.user_id == user_id)
        .with_for_update()
        .first()
    )
    if item is None:
        raise MemoError("not_found", "备忘录不存在", memo_id=memo_id)
    changes = request.model_dump(exclude_unset=True)
    if not changes or any(value is None for value in changes.values()):
        raise MemoError("validation_error", "请提供非空的更新字段", memo_id=memo_id)
    for key, value in changes.items():
        setattr(item, key, value)
    item.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.flush()
    return serialize(item)
