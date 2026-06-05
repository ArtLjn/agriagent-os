"""反馈功能测试。"""

from app.models.conversation import Conversation, ConversationMessage
from app.models.user import User
from app.services.feedback_service import get_feedback_stats, submit_feedback


def _ensure_user(db, user_id: str) -> None:
    """确保反馈测试使用的用户存在。"""
    if db.get(User, user_id):
        return
    db.add(
        User(
            id=user_id,
            phone=f"{abs(hash(user_id)) % 10_000_000_000:010d}",
            password_hash="h",
            nickname=user_id,
            status="active",
        )
    )
    db.commit()


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


def test_submit_good_feedback(db_session):
    """提交正面评价。"""
    msg_id = _seed_message(db_session)
    _ensure_user(db_session, "test-user")
    record = submit_feedback(
        db_session, user_id="test-user", message_id=msg_id, rating="good"
    )

    assert record.rating == "good"
    assert record.id is not None


def test_submit_bad_feedback_with_correction(db_session):
    """提交负面评价 + 修正。"""
    msg_id = _seed_message(db_session)
    _ensure_user(db_session, "test-user")
    record = submit_feedback(
        db_session,
        user_id="test-user",
        message_id=msg_id,
        rating="bad",
        correction="应该说...",
    )

    assert record.rating == "bad"
    assert record.correction == "应该说..."


def test_feedback_stats(db_session):
    """统计反馈数据。"""
    msg_id = _seed_message(db_session)
    _ensure_user(db_session, "u1")
    _ensure_user(db_session, "u2")
    submit_feedback(db_session, "u1", msg_id, "good")
    submit_feedback(db_session, "u2", msg_id, "bad")
    stats = get_feedback_stats(db_session)

    assert stats["total"] >= 2
    assert stats["good"] >= 1
    assert stats["bad"] >= 1
