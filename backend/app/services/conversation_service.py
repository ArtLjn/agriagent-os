"""会话服务 -- 管理 Conversation 生命周期和历史消息。"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.infra.repository_runtime import (
    get_conversation_message_repository,
    run_maybe_awaitable,
)
from app.models.conversation import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
)

logger = logging.getLogger(__name__)

_EXPIRE_HOURS = 24
_MAX_INJECT_MESSAGES = 20  # 10 轮 = 20 条消息


class ConversationAccessError(ValueError):
    """会话不属于当前 farm。"""


def get_or_create_conversation(
    db: Session, farm_id: int, session_id: str, user_id: str | None = None
) -> Conversation:
    """获取或创建会话。每个 farm 同时只有一个活跃会话。"""
    existing = (
        db.query(Conversation).filter(Conversation.session_id == session_id).first()
    )
    if existing:
        if existing.farm_id != farm_id:
            raise ConversationAccessError("会话不存在")
        return existing

    # 关闭同一 farm 的其他活跃会话
    _close_other_active(db, farm_id)

    conv = Conversation(
        farm_id=farm_id,
        user_id=user_id,
        session_id=session_id,
        status=ConversationStatus.ACTIVE,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    logger.info("创建新会话 | farm=%s session=%s", farm_id, session_id)
    return conv


def _close_other_active(db: Session, farm_id: int) -> int:
    """关闭指定 farm 的所有活跃会话。"""
    count = (
        db.query(Conversation)
        .filter(
            Conversation.farm_id == farm_id,
            Conversation.status == ConversationStatus.ACTIVE.value,
        )
        .update({"status": ConversationStatus.CLOSED.value})
    )
    db.commit()
    if count > 0:
        logger.info("关闭旧会话 | farm=%s count=%d", farm_id, count)
    return count


def close_expired_conversations(db: Session, farm_id: int) -> int:
    """关闭超过 24h 无活动的活跃会话。"""
    cutoff = datetime.now() - timedelta(hours=_EXPIRE_HOURS)
    count = (
        db.query(Conversation)
        .filter(
            Conversation.farm_id == farm_id,
            Conversation.status == ConversationStatus.ACTIVE.value,
            Conversation.last_active_at < cutoff,
        )
        .update({"status": ConversationStatus.CLOSED.value})
    )
    db.commit()
    if count > 0:
        logger.info("过期会话清理 | farm=%s count=%d", farm_id, count)
    return count


def save_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    meta: str | None = None,
) -> ConversationMessage:
    """持久化单条消息并更新会话最后活跃时间。"""
    conversation = db.get(Conversation, conversation_id)
    msg = ConversationMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        meta=meta,
    )
    if conversation is not None:
        msg.conversation = conversation
    repo = get_conversation_message_repository(db)
    msg = run_maybe_awaitable(repo.save_one(msg))

    # 更新会话最后活跃时间
    db.query(Conversation).filter(Conversation.id == conversation_id).update(
        {"last_active_at": datetime.now()}
    )
    db.commit()
    return msg


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def save_messages_batch(
    db: Session,
    conversation_id: int,
    messages: list[dict[str, Any]],
) -> list[ConversationMessage]:
    """在一次事务中保存多条消息并更新会话活跃时间。"""
    conversation = db.get(Conversation, conversation_id)
    rows: list[ConversationMessage] = []
    for item in messages:
        meta_json = item.get("meta_json")
        meta_text = item.get("meta")
        if meta_text is None and meta_json is not None:
            meta_text = json.dumps(meta_json, ensure_ascii=False)
        row = ConversationMessage(
            conversation_id=conversation_id,
            role=item["role"],
            content=item["content"],
            meta=meta_text,
            turn_id=item.get("turn_id"),
            content_hash=_content_hash(item["content"]),
            meta_json=meta_json,
        )
        if conversation is not None:
            row.conversation = conversation
        rows.append(row)
    repo = get_conversation_message_repository(db)
    rows = run_maybe_awaitable(repo.save_batch(rows))
    db.query(Conversation).filter(Conversation.id == conversation_id).update(
        {"last_active_at": datetime.now()}
    )
    db.commit()
    return rows


def get_recent_messages(
    db: Session, conversation_id: int, limit: int = _MAX_INJECT_MESSAGES
) -> list[ConversationMessage]:
    """获取最近 N 条消息，按创建时间正序排列。"""
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        return []
    repo = get_conversation_message_repository(db)
    return run_maybe_awaitable(
        repo.get_recent(
            farm_id=conversation.farm_id,
            conversation_id=conversation_id,
            limit=limit,
        )
    )


def list_conversations(
    db: Session, farm_id: int, limit: int = 20
) -> list[Conversation]:
    """返回 farm 的会话列表，按最后活跃时间倒序。"""
    return (
        db.query(Conversation)
        .filter(Conversation.farm_id == farm_id)
        .order_by(Conversation.last_active_at.desc())
        .limit(limit)
        .all()
    )


def get_conversation_by_session(
    db: Session, session_id: str, farm_id: int | None = None
) -> Conversation | None:
    """按 session_id 获取会话，可限定 farm。"""
    query = db.query(Conversation).filter(Conversation.session_id == session_id)
    if farm_id is not None:
        query = query.filter(Conversation.farm_id == farm_id)
    return query.first()


def get_conversation_messages(
    db: Session, session_id: str, farm_id: int | None = None
) -> list[ConversationMessage]:
    """通过 session_id 返回完整消息列表，按创建时间正序。"""
    conv = get_conversation_by_session(db, session_id, farm_id=farm_id)
    if not conv:
        return []
    repo = get_conversation_message_repository(db)
    return run_maybe_awaitable(
        repo.list_by_session(farm_id=conv.farm_id, session_id=session_id)
    )


__all__ = [
    "ConversationAccessError",
    "get_or_create_conversation",
    "close_expired_conversations",
    "save_message",
    "save_messages_batch",
    "get_recent_messages",
    "list_conversations",
    "get_conversation_by_session",
    "get_conversation_messages",
]
