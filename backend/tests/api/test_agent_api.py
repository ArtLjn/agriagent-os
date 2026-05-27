"""会话管理 API 端点测试。"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.agent import router
from app.api.deps import get_current_farm, get_db
from app.core.database import SessionLocal
from app.infra.limiter import limiter
from app.models.farm import Farm


@pytest.fixture
def client():
    """创建测试客户端，注入真实 DB 会话和默认农场。"""
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)

    def override_get_db():
        try:
            db = SessionLocal()
            yield db
        finally:
            db.close()

    def override_get_current_farm(
        db: SessionLocal = Depends(get_db),
    ) -> Farm:
        return db.query(Farm).filter(Farm.id == 1).first()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_farm] = override_get_current_farm

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestConversationApi:
    """测试会话管理 API 端点。"""

    def test_list_conversations(self, client, clean_db):
        """GET /agent/conversations 返回会话列表。"""
        from app.services.conversation_service import get_or_create_conversation

        db = SessionLocal()
        get_or_create_conversation(db, farm_id=1, session_id="sess-api-1")
        db.close()

        response = client.get("/agent/conversations")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["session_id"] == "sess-api-1"

    def test_get_conversation_messages(self, client, clean_db):
        """GET /agent/conversations/{session_id}/messages 返回消息列表。"""
        from app.services.conversation_service import (
            get_or_create_conversation,
            save_message,
        )

        db = SessionLocal()
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
