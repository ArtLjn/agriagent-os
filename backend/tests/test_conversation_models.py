"""Conversation 模型测试。"""

from app.models.conversation import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
)
from app.core.database import SessionLocal


class TestConversationModel:
    def test_create_conversation(self, clean_db):
        db = SessionLocal()
        conv = Conversation(
            farm_id=1,
            session_id="test-session-001",
            status=ConversationStatus.ACTIVE,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

        assert conv.id is not None
        assert conv.farm_id == 1
        assert conv.session_id == "test-session-001"
        assert conv.status == ConversationStatus.ACTIVE
        assert conv.created_at is not None
        assert conv.last_active_at is not None
        db.close()

    def test_create_conversation_message(self, clean_db):
        db = SessionLocal()
        conv = Conversation(farm_id=1, session_id="test-session-002")
        db.add(conv)
        db.commit()

        msg = ConversationMessage(
            conversation_id=conv.id,
            role="user",
            content="明天天气怎么样",
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)

        assert msg.id is not None
        assert msg.conversation_id == conv.id
        assert msg.role == "user"
        assert msg.content == "明天天气怎么样"
        assert msg.created_at is not None
        db.close()

    def test_conversation_cascade_delete_messages(self, clean_db):
        db = SessionLocal()
        conv = Conversation(farm_id=1, session_id="test-session-003")
        db.add(conv)
        db.commit()

        msg = ConversationMessage(conversation_id=conv.id, role="user", content="test")
        db.add(msg)
        db.commit()

        db.delete(conv)
        db.commit()

        remaining = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conv.id)
            .all()
        )
        assert len(remaining) == 0
        db.close()

    def test_conversation_status_enum(self, clean_db):
        db = SessionLocal()
        conv = Conversation(
            farm_id=1, session_id="test-session-004", status=ConversationStatus.CLOSED
        )
        db.add(conv)
        db.commit()

        fetched = (
            db.query(Conversation)
            .filter(Conversation.session_id == "test-session-004")
            .first()
        )
        assert fetched.status == "closed"
        db.close()
