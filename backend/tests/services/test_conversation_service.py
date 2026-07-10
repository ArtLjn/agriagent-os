"""ConversationService 测试。"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.conversation import ConversationStatus
from app.models.conversation import ConversationMessage
from app.models.farm import Farm
from app.services.conversation_service import (
    ConversationAccessError,
    async_get_recent_messages,
    close_expired_conversations,
    get_conversation_messages,
    get_or_create_conversation,
    get_recent_messages,
    list_conversations,
    save_message,
    save_messages_batch,
)


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


_test_engine = create_engine(
    "sqlite:///tests/test_conversation_service.db",
    connect_args={"check_same_thread": False},
)
event.listen(_test_engine, "connect", _set_sqlite_pragma)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(autouse=True)
def clean_conversation_db():
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    db = _TestSession()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()
    yield


class TestGetOrCreateConversation:
    """get_or_create_conversation 测试。"""

    def test_create_new_conversation(self):
        """新 session_id 创建新会话。"""
        db = _TestSession()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-new")

        assert conv.farm_id == 1
        assert conv.session_id == "sess-new"
        assert conv.status == ConversationStatus.ACTIVE
        db.close()

    def test_reuse_active_conversation(self):
        """同一 session_id 复用已有会话。"""
        db = _TestSession()
        conv1 = get_or_create_conversation(db, farm_id=1, session_id="sess-reuse")
        conv2 = get_or_create_conversation(db, farm_id=1, session_id="sess-reuse")

        assert conv1.id == conv2.id
        db.close()

    def test_reject_reusing_other_farm_session_id(self):
        """不能复用其他 farm 已存在的 session_id。"""
        db = _TestSession()
        db.add(Farm(id=2, name="其他农场"))
        db.commit()
        existing = get_or_create_conversation(
            db, farm_id=1, session_id="sess-cross-farm"
        )

        with pytest.raises(ConversationAccessError):
            get_or_create_conversation(db, farm_id=2, session_id="sess-cross-farm")

        db.refresh(existing)
        assert existing.farm_id == 1
        db.close()

    def test_close_old_active_when_new_session(self):
        """新 session_id 时关闭同一 farm 的旧活跃会话。"""
        db = _TestSession()
        old = get_or_create_conversation(db, farm_id=1, session_id="sess-old")
        assert old.status == ConversationStatus.ACTIVE

        new = get_or_create_conversation(db, farm_id=1, session_id="sess-new2")
        db.refresh(old)

        assert old.status == ConversationStatus.CLOSED
        assert new.status == ConversationStatus.ACTIVE
        assert new.session_id == "sess-new2"
        db.close()


class TestSaveAndGetMessages:
    """save_message / get_recent_messages 测试。"""

    def test_save_user_message(self):
        """保存用户消息。"""
        db = _TestSession()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-msg")
        msg = save_message(db, conv.id, "user", "明天天气如何")

        assert msg.role == "user"
        assert msg.content == "明天天气如何"
        db.close()

    def test_save_assistant_message(self):
        """保存助手消息。"""
        db = _TestSession()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-msg2")
        msg = save_message(db, conv.id, "assistant", "明天晴，适合浇水")

        assert msg.role == "assistant"
        assert msg.content == "明天晴，适合浇水"
        db.close()

    def test_get_recent_messages_limit(self):
        """获取最近 N 条消息，按时间正序返回。"""
        db = _TestSession()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-recent")
        for i in range(5):
            save_message(db, conv.id, "user", f"msg-{i}")
            save_message(db, conv.id, "assistant", f"reply-{i}")

        recent = get_recent_messages(db, conv.id, limit=6)
        assert len(recent) == 6
        # 从第 3 轮开始的最后 6 条
        assert recent[0].content == "msg-2"
        db.close()

    async def test_async_get_recent_messages_awaits_async_repository(self, monkeypatch):
        """async 链路获取历史消息时直接 await 文档仓储。"""
        db = _TestSession()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-async-recent")

        class AsyncRepo:
            async def get_recent(self, **kwargs):
                assert kwargs == {"farm_id": 1, "conversation_id": conv.id, "limit": 3}
                return [ConversationMessage(role="user", content="历史")]

        monkeypatch.setattr(
            "app.services.conversation_service.get_conversation_message_repository",
            lambda _db: AsyncRepo(),
        )

        recent = await async_get_recent_messages(db, conv.id, limit=3)

        assert [item.content for item in recent] == ["历史"]
        db.close()


class TestBatchMessageSave:
    """批量保存消息测试。"""

    def test_save_messages_batch_uses_one_transaction_and_sets_light_metadata(self):
        db = _TestSession()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-batch")

        messages = save_messages_batch(
            db,
            conv.id,
            [
                {
                    "role": "user",
                    "content": "查一下作物",
                    "turn_id": 1,
                    "meta_json": {"trace_request_id": "abcd1234"},
                },
                {
                    "role": "assistant",
                    "content": "当前有水稻",
                    "turn_id": 1,
                    "meta_json": {"skills": ["get_farm_status"]},
                },
            ],
        )

        assert [m.role for m in messages] == ["user", "assistant"]
        assert messages[0].turn_id == 1
        assert messages[1].meta_json == {"skills": ["get_farm_status"]}
        db.refresh(conv)
        assert conv.last_active_at is not None
        db.close()


class TestCloseExpiredConversations:
    """close_expired_conversations 测试。"""

    def test_close_conversations_older_than_24h(self):
        """超过 24h 无活动的活跃会话被关闭。"""
        db = _TestSession()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-expired")
        # 手动设置 last_active_at 为 25 小时前
        conv.last_active_at = datetime.now() - timedelta(hours=25)
        db.commit()

        closed_count = close_expired_conversations(db, farm_id=1)
        assert closed_count == 1

        db.refresh(conv)
        assert conv.status == ConversationStatus.CLOSED
        db.close()

    def test_keep_recent_conversations(self):
        """近期活跃的会话不会被关闭。"""
        db = _TestSession()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-recent2")

        closed_count = close_expired_conversations(db, farm_id=1)
        assert closed_count == 0

        db.refresh(conv)
        assert conv.status == ConversationStatus.ACTIVE
        db.close()


class TestListConversations:
    """list_conversations 测试。"""

    def test_list_ordered_by_last_active(self):
        """会话列表按最后活跃时间倒序。"""
        db = _TestSession()
        conv1 = get_or_create_conversation(db, farm_id=1, session_id="sess-list1")
        _conv2 = get_or_create_conversation(db, farm_id=1, session_id="sess-list2")
        # conv2 创建后 conv1 被 close，但 save_message 更新 conv1.last_active_at
        save_message(db, conv1.id, "user", "hi")
        db.commit()

        result = list_conversations(db, farm_id=1, limit=10)
        assert len(result) == 2
        assert result[0].session_id == "sess-list1"
        db.close()


class TestGetConversationMessages:
    """get_conversation_messages 测试。"""

    def test_get_full_message_list(self):
        """通过 session_id 获取完整消息列表。"""
        db = _TestSession()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-full")
        save_message(db, conv.id, "user", "Q1")
        save_message(db, conv.id, "assistant", "A1")

        msgs = get_conversation_messages(db, conv.session_id)
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"
        db.close()

    def test_get_messages_nonexistent_session(self):
        """不存在的 session_id 返回空列表。"""
        db = _TestSession()
        msgs = get_conversation_messages(db, "nonexistent-session")
        assert msgs == []
        db.close()
