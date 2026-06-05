"""会话服务 -- 管理 Conversation 生命周期和历史消息。"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.conversation import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
)

logger = logging.getLogger(__name__)

_EXPIRE_HOURS = 24
_MAX_INJECT_MESSAGES = 20  # 10 轮 = 20 条消息


def get_or_create_conversation(
    db: Session, farm_id: int, session_id: str, user_id: str | None = None
) -> Conversation:
    """获取或创建会话。每个 farm 同时只有一个活跃会话。"""
    existing = (
        db.query(Conversation).filter(Conversation.session_id == session_id).first()
    )
    if existing:
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
    msg = ConversationMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        meta=meta,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # 更新会话最后活跃时间
    db.query(Conversation).filter(Conversation.id == conversation_id).update(
        {"last_active_at": datetime.now()}
    )
    db.commit()
    return msg


def get_recent_messages(
    db: Session, conversation_id: int, limit: int = _MAX_INJECT_MESSAGES
) -> list[ConversationMessage]:
    """获取最近 N 条消息，按创建时间正序排列。"""
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
        .limit(limit)
        .all()
    )[::-1]


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
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conv.id)
        .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        .all()
    )


__all__ = [
    "get_or_create_conversation",
    "close_expired_conversations",
    "save_message",
    "get_recent_messages",
    "list_conversations",
    "get_conversation_by_session",
    "get_conversation_messages",
]
