"""Conversation 模型测试。"""

from app.models.conversation import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
)


class TestConversationModel:
    def test_create_conversation(self, db_session):
        conv = Conversation(
            farm_id=1,
            session_id="test-session-001",
            status=ConversationStatus.ACTIVE,
        )
        db_session.add(conv)
        db_session.commit()
        db_session.refresh(conv)

        assert conv.id is not None
        assert conv.farm_id == 1
        assert conv.session_id == "test-session-001"
        assert conv.status == ConversationStatus.ACTIVE
        assert conv.created_at is not None
        assert conv.last_active_at is not None

    def test_create_conversation_message(self, db_session):
        conv = Conversation(farm_id=1, session_id="test-session-002")
        db_session.add(conv)
        db_session.commit()

        msg = ConversationMessage(
            conversation_id=conv.id,
            role="user",
            content="明天天气怎么样",
        )
        db_session.add(msg)
        db_session.commit()
        db_session.refresh(msg)

        assert msg.id is not None
        assert msg.conversation_id == conv.id
        assert msg.role == "user"
        assert msg.content == "明天天气怎么样"
        assert msg.created_at is not None

    def test_conversation_cascade_delete_messages(self, db_session):
        conv = Conversation(farm_id=1, session_id="test-session-003")
        db_session.add(conv)
        db_session.commit()

        msg = ConversationMessage(conversation_id=conv.id, role="user", content="test")
        db_session.add(msg)
        db_session.commit()

        db_session.delete(conv)
        db_session.commit()

        remaining = (
            db_session.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conv.id)
            .all()
        )
        assert len(remaining) == 0

    def test_conversation_status_enum(self, db_session):
        conv = Conversation(
            farm_id=1, session_id="test-session-004", status=ConversationStatus.CLOSED
        )
        db_session.add(conv)
        db_session.commit()

        fetched = (
            db_session.query(Conversation)
            .filter(Conversation.session_id == "test-session-004")
            .first()
        )
        assert fetched.status == "closed"
