"""反馈服务 — 提交评价、统计查询。"""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.feedback import FeedbackRecord
from app.models.conversation import ConversationMessage

logger = logging.getLogger(__name__)


def submit_feedback(
    db: Session,
    user_id: str,
    message_id: int,
    rating: str,
    correction: str | None = None,
) -> FeedbackRecord:
    """提交一条反馈。如果 message_id 对应的消息不存在则置空。"""
    actual_message_id = message_id
    if message_id is not None:
        exists = db.query(ConversationMessage).filter(ConversationMessage.id == message_id).first()
        if not exists:
            actual_message_id = None

    record = FeedbackRecord(
        user_id=user_id,
        conversation_message_id=actual_message_id,
        rating=rating,
        correction=correction,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("反馈已提交 | user=%s msg=%s rating=%s", user_id, message_id, rating)
    return record


def get_feedback_stats(db: Session) -> dict:
    """获取反馈统计。"""
    total = db.query(func.count(FeedbackRecord.id)).scalar() or 0
    good = (
        db.query(func.count(FeedbackRecord.id))
        .filter(FeedbackRecord.rating == "good")
        .scalar()
        or 0
    )
    bad = (
        db.query(func.count(FeedbackRecord.id))
        .filter(FeedbackRecord.rating == "bad")
        .scalar()
        or 0
    )
    return {"total": total, "good": good, "bad": bad}
