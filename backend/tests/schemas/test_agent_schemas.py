"""Agent schemas 测试 — ChatRequest session_id 扩展 + 新增响应 Schema。"""

from datetime import datetime

from app.schemas.agent import (
    ChatRequest,
    ConversationListItem,
    ConversationMessageItem,
)


class TestChatRequestSessionId:
    """ChatRequest.session_id 字段验证。"""

    def test_chat_request_accepts_session_id(self):
        req = ChatRequest(message="test", session_id="test-sess-123")
        assert req.session_id == "test-sess-123"

    def test_chat_request_session_id_optional(self):
        req = ChatRequest(message="test")
        assert req.session_id is None


class TestConversationListItem:
    """ConversationListItem schema 验证。"""

    def test_valid_conversation_list_item(self):
        now = datetime(2026, 5, 27, 12, 0, 0)
        item = ConversationListItem(
            id=1,
            session_id="sess-abc",
            status="active",
            created_at=now,
            last_active_at=now,
        )
        assert item.id == 1
        assert item.session_id == "sess-abc"
        assert item.status == "active"

    def test_from_attributes(self):
        """验证 ConfigDict(from_attributes=True) 能从对象属性读取。"""

        class FakeRow:
            id = 2
            session_id = "sess-xyz"
            status = "closed"
            created_at = datetime(2026, 1, 1)
            last_active_at = datetime(2026, 1, 2)

        item = ConversationListItem.model_validate(FakeRow())
        assert item.session_id == "sess-xyz"


class TestConversationMessageItem:
    """ConversationMessageItem schema 验证。"""

    def test_valid_message_item(self):
        now = datetime(2026, 5, 27, 12, 0, 0)
        item = ConversationMessageItem(
            id=10,
            role="user",
            content="你好",
            created_at=now,
        )
        assert item.role == "user"
        assert item.content == "你好"

    def test_from_attributes(self):

        class FakeRow:
            id = 11
            role = "assistant"
            content = "你好，有什么可以帮助你的？"
            created_at = datetime(2026, 5, 27, 12, 1, 0)

        item = ConversationMessageItem.model_validate(FakeRow())
        assert item.role == "assistant"
