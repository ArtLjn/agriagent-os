"""反馈功能测试。"""

from app.core.database import SessionLocal
from app.models.conversation import Conversation, ConversationMessage
from app.services.feedback_service import get_feedback_stats, submit_feedback


def _seed_message(db) -> int:
    """创建一条测试消息并返回 ID。"""
    conv = Conversation(farm_id=1, session_id="test-session")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    msg = ConversationMessage(
        conversation_id=conv.id, role="assistant", content="测试回复"
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg.id


def test_submit_good_feedback():
    """提交正面评价。"""
    db = SessionLocal()
    try:
        msg_id = _seed_message(db)
        record = submit_feedback(
            db, user_id="test-user", message_id=msg_id, rating="good"
        )

        assert record.rating == "good"
        assert record.id is not None
    finally:
        db.close()


def test_submit_bad_feedback_with_correction():
    """提交负面评价 + 修正。"""
    db = SessionLocal()
    try:
        msg_id = _seed_message(db)
        record = submit_feedback(
            db,
            user_id="test-user",
            message_id=msg_id,
            rating="bad",
            correction="应该说...",
        )

        assert record.rating == "bad"
        assert record.correction == "应该说..."
    finally:
        db.close()


def test_feedback_stats():
    """统计反馈数据。"""
    db = SessionLocal()
    try:
        msg_id = _seed_message(db)
        submit_feedback(db, "u1", msg_id, "good")
        submit_feedback(db, "u2", msg_id, "bad")
        stats = get_feedback_stats(db)

        assert stats["total"] >= 2
        assert stats["good"] >= 1
        assert stats["bad"] >= 1
    finally:
        db.close()
