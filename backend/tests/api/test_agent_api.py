"""会话管理 API 端点测试。"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.agent import router
from app.shared.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.farm.dependencies import get_current_farm
from app.shared.database import Base
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

    def override_get_current_user() -> User:
        return User(
            id="test-user-001",
            phone="00000000000",
            password_hash="h",
            nickname="测试用户",
            status="active",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_farm] = override_get_current_farm
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client():
    """创建管理员测试客户端，用于模拟用户查询。"""
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

    def override_get_current_user() -> User:
        return User(
            id="admin-user-001",
            phone="00000000999",
            password_hash="h",
            nickname="管理员",
            role="admin",
            status="active",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_farm] = override_get_current_farm
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_chat_passes_current_user_to_advisor(client):
    """POST /agent/chat 将当前用户透传给 advisor。"""
    advisor = AsyncMock(return_value="ok")

    with patch("app.application.chat.use_case.invoke_advisor", advisor):
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

    def test_admin_simulated_user_lists_target_user_conversations(
        self, admin_client, clean_db
    ):
        """管理员切换模拟用户后，返回目标用户 farm 的会话列表。"""
        from app.services.conversation_service import (
            get_or_create_conversation,
            save_message,
        )

        db = _TestSession()
        db.add(
            User(
                id="sim-user-001",
                phone="00000000003",
                password_hash="h",
                nickname="爸爸",
                status="active",
            )
        )
        db.add(Farm(id=3, name="爸爸农场", user_id="sim-user-001"))
        db.commit()
        own_conv = get_or_create_conversation(db, farm_id=1, session_id="admin-sess")
        save_message(db, own_conv.id, "user", "管理员自己的会话")
        sim_conv = get_or_create_conversation(db, farm_id=3, session_id="sim-sess")
        save_message(db, sim_conv.id, "user", "模拟用户的会话")
        db.close()

        response = admin_client.get(
            "/agent/conversations?simulate_user_id=sim-user-001"
        )

        assert response.status_code == 200
        data = response.json()
        assert [item["session_id"] for item in data] == ["sim-sess"]

    def test_admin_simulated_user_reads_target_user_messages(
        self, admin_client, clean_db
    ):
        """管理员切换模拟用户后，消息接口读取目标用户 farm。"""
        from app.services.conversation_service import (
            get_or_create_conversation,
            save_message,
        )

        db = _TestSession()
        db.add(
            User(
                id="sim-user-002",
                phone="00000000004",
                password_hash="h",
                nickname="妈妈",
                status="active",
            )
        )
        db.add(Farm(id=4, name="妈妈农场", user_id="sim-user-002"))
        db.commit()
        conv = get_or_create_conversation(db, farm_id=4, session_id="sim-msg-sess")
        save_message(db, conv.id, "user", "模拟用户消息")
        db.close()

        response = admin_client.get(
            "/agent/conversations/sim-msg-sess/messages?simulate_user_id=sim-user-002"
        )

        assert response.status_code == 200
        assert response.json()[0]["content"] == "模拟用户消息"

    def test_get_messages_rejects_other_farm_session(self, client, clean_db):
        """不能读取其他 farm 的会话消息。"""
        from app.services.conversation_service import (
            get_or_create_conversation,
            save_message,
        )

        db = _TestSession()
        db.add(
            User(
                id="test-user-002",
                phone="00000000002",
                password_hash="h",
                nickname="其他用户",
                status="active",
            )
        )
        db.add(Farm(id=2, name="其他农场", user_id="test-user-002"))
        db.commit()
        conv = get_or_create_conversation(db, farm_id=2, session_id="sess-other-farm")
        save_message(db, conv.id, "user", "其他农场的私密消息")
        db.close()

        response = client.get("/agent/conversations/sess-other-farm/messages")

        assert response.status_code == 404
        assert "其他农场的私密消息" not in response.text

    def test_get_messages_not_found(self, client, clean_db):
        """不存在的 session_id 返回 404。"""
        response = client.get("/agent/conversations/nonexistent/messages")

        assert response.status_code == 404
