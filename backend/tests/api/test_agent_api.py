"""会话管理 API 端点测试。"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.agent import router
from app.api.deps import get_current_farm, get_db
from app.core.database import Base
from app.infra.limiter import limiter
from app.models.farm import Farm
from app.models.user import User


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


_test_engine = create_engine(
    "sqlite:///tests/test_agent_api.db",
    connect_args={"check_same_thread": False},
)
event.listen(_test_engine, "connect", _set_sqlite_pragma)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(autouse=True)
def clean_agent_api_db():
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    db = _TestSession()
    db.add(
        User(
            id="test-user-001",
            phone="00000000000",
            password_hash="h",
            nickname="测试用户",
            status="active",
        )
    )
    db.add(Farm(id=1, name="默认农场", user_id="test-user-001"))
    db.commit()
    db.close()
    yield


@pytest.fixture
def client():
    """创建测试客户端，注入真实 DB 会话和默认农场。"""
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)

    def override_get_db():
        try:
            db = _TestSession()
            yield db
        finally:
            db.close()

    def override_get_current_farm(
        db=Depends(get_db),
    ) -> Farm:
        return db.query(Farm).filter(Farm.id == 1).first()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_farm] = override_get_current_farm

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_chat_passes_current_user_to_advisor(client):
    """POST /agent/chat 将当前用户透传给 advisor。"""
    advisor = AsyncMock(return_value="ok")

    with patch("app.services.agent_service.invoke_advisor", advisor):
        response = client.post(
            "/agent/chat",
            json={"message": "帮我看看农场状态", "session_id": "sess-user-1"},
        )

    assert response.status_code == 200
    assert response.json()["reply"] == "ok"
    assert advisor.await_args.kwargs["user_id"] == "test-user-001"


class TestConversationApi:
    """测试会话管理 API 端点。"""

    def test_list_conversations(self, client, clean_db):
        """GET /agent/conversations 返回会话列表。"""
        from app.services.conversation_service import (
            get_or_create_conversation,
            save_message,
        )

        db = _TestSession()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-api-1")
        save_message(db, conv.id, "user", "今天适不适合打药？")
        save_message(db, conv.id, "assistant", "今天风小，可以安排傍晚打药。")
        db.close()

        response = client.get("/agent/conversations")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["session_id"] == "sess-api-1"
        assert data[0]["title"] == "今天适不适合打药？"
        assert data[0]["preview"] == "今天风小，可以安排傍晚打药。"
        assert data[0]["category"] == "天气"

    def test_get_conversation_messages(self, client, clean_db):
        """GET /agent/conversations/{session_id}/messages 返回消息列表。"""
        from app.services.conversation_service import (
            get_or_create_conversation,
            save_message,
        )

        db = _TestSession()
        conv = get_or_create_conversation(db, farm_id=1, session_id="sess-api-2")
        save_message(db, conv.id, "user", "hello")
        save_message(db, conv.id, "assistant", "hi")
        db.close()

        response = client.get("/agent/conversations/sess-api-2/messages")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["role"] == "user"
        assert data[1]["role"] == "assistant"

    def test_get_messages_not_found(self, client, clean_db):
        """不存在的 session_id 返回空列表。"""
        response = client.get("/agent/conversations/nonexistent/messages")

        assert response.status_code == 200
        assert response.json() == []
