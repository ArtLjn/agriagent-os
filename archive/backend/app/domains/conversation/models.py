"""会话模型 -- 持久化用户与 Agent 的多轮对话历史。"""

import enum

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.shared.database import Base


class ConversationStatus(str, enum.Enum):
    """会话状态枚举。"""

    ACTIVE = "active"
    CLOSED = "closed"


class Conversation(Base):
    """会话模型 -- 每个 farm 同时只有一个活跃会话。"""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    user_id = Column(String(36), nullable=True)
    session_id = Column(String(64), nullable=False, index=True, unique=True)
    status = Column(String(20), nullable=False, default=ConversationStatus.ACTIVE.value)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    summary = Column(Text, nullable=True)
    summary_updated_at = Column(DateTime(timezone=True), nullable=True)
    last_turn_id = Column(Integer, nullable=True)
    last_event_seq = Column(Integer, nullable=True)
    meta_json = Column(JSON, nullable=True)

    messages = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class ConversationMessage(Base):
    """会话消息模型 -- 存储单条对话记录。"""

    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    meta = Column(Text, nullable=True)
    turn_id = Column(Integer, nullable=True, index=True)
    content_hash = Column(String(64), nullable=True)
    meta_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")
