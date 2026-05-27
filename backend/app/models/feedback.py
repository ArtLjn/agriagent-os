"""用户反馈模型 — AI 回复评价收集。"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class FeedbackRecord(Base):
    """用户对 AI 回复的评价。"""

    __tablename__ = "feedback_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    conversation_message_id = Column(
        Integer, ForeignKey("conversation_messages.id"), nullable=True
    )
    rating = Column(String(10), nullable=False)  # good / bad
    correction = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
