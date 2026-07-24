"""会话管理 API 端点测试。"""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.domains.conversation.routes import router
from app.shared.database import get_db
from app.shared.database import Base
from app.infra.limiter import limiter
from app.agent.executor.models import PendingActionDecision
from app.domains.farm.models import Farm
from app.domains.users.models import User
from app.domains.users.tokens import create_access_token


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
    """创建使用真实 JWT 的普通用户测试客户端。"""
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)

    def override_get_db():
        try:
            db = _TestSession()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    client.headers.update(_headers_for("test-user-001"))
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client():
    """创建使用真实 JWT 的管理员测试客户端，用于模拟用户查询。"""
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)

    def override_get_db():
        try:
            db = _TestSession()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    _create_user_and_farm(
        user_id="admin-user-001",
        farm_id=9,
        phone="00000000999",
        nickname="管理员",
        role="admin",
        farm_name="管理员农场",
    )
    client.headers.update(_headers_for("admin-user-001"))
    yield client
    app.dependency_overrides.clear()


def test_chat_passes_current_user_to_advisor(client):
    """POST /agent/chat 将当前用户透传给 advisor。"""
    advisor = AsyncMock(return_value="ok")

    with _patch_chat_chain(advisor):
        response = client.post(
            "/agent/chat",
            json={"message": "帮我看看农场状态", "session_id": "sess-user-1"},
        )

    assert response.status_code == 200
    assert response.json()["reply"] == "ok"
    assert advisor.await_args.kwargs["user_id"] == "test-user-001"


def test_admin_body_simulate_user_chat_uses_target_user(admin_client):
    """管理员在 POST /agent/chat body 模拟用户时，使用目标用户和目标 farm。"""
    _create_user_and_farm(
        user_id="sim-chat-user-001",
        farm_id=31,
        phone="00000000301",
        nickname="模拟聊天用户",
        farm_name="模拟聊天农场",
    )
    advisor = AsyncMock(return_value="ok")

    with _patch_chat_chain(advisor):
        response = admin_client.post(
            "/agent/chat",
            json={
                "message": "帮我看看目标农场",
                "session_id": "sess-sim-chat",
                "simulate_user_id": "sim-chat-user-001",
            },
        )

    assert response.status_code == 200
    assert response.json()["reply"] == "ok"
    assert advisor.await_args.kwargs["user_id"] == "sim-chat-user-001"
    assert advisor.await_args.kwargs["farm_id"] == 31


def test_regular_user_body_simulate_chat_returns_403(client):
    """普通用户不能在 POST /agent/chat body 模拟其他用户。"""
    _create_user_and_farm(
        user_id="sim-chat-user-002",
        farm_id=32,
        phone="00000000302",
        nickname="被模拟用户",
        farm_name="被模拟农场",
    )
    advisor = AsyncMock(return_value="should-not-call")

    with _patch_chat_chain(advisor):
        response = client.post(
            "/agent/chat",
            json={
                "message": "尝试模拟",
                "simulate_user_id": "sim-chat-user-002",
            },
        )

    assert response.status_code == 403
    assert advisor.await_count == 0


class TestConversationApi:
    """测试会话管理 API 端点。"""

    def test_list_conversations(self, client, clean_db):
        """GET /agent/conversations 返回会话列表。"""
        from app.domains.conversation.service import (
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
        from app.domains.conversation.service import (
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
        from app.domains.conversation.service import (
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
        from app.domains.conversation.service import (
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
        from app.domains.conversation.service import (
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


def _headers_for(user_id: str) -> dict[str, str]:
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


def _create_user_and_farm(
    *,
    user_id: str,
    farm_id: int,
    phone: str,
    nickname: str,
    farm_name: str,
    role: str = "user",
    status: str = "active",
) -> None:
    db = _TestSession()
    try:
        db.add(
            User(
                id=user_id,
                phone=phone,
                password_hash="h",
                nickname=nickname,
                role=role,
                status=status,
            )
        )
        db.add(Farm(id=farm_id, name=farm_name, user_id=user_id))
        db.commit()
    finally:
        db.close()


@contextmanager
def _patch_chat_chain(advisor: AsyncMock) -> Iterator[None]:
    """隔离和本轮鉴权无关的 Agent 后置链路。"""
    with (
        patch("app.application.chat.use_case.invoke_advisor", advisor),
        patch(
            "app.application.chat.use_case.handle_pending_action",
            AsyncMock(return_value=PendingActionDecision.unhandled()),
        ),
        patch(
            "app.application.chat.use_case.resolve_query_menu_or_message",
            AsyncMock(return_value=("有效消息", None)),
        ),
        patch(
            "app.application.chat.use_case.build_pending_action_response",
            return_value=None,
        ),
        patch(
            "app.application.chat.use_case.build_pending_plan_response",
            return_value=None,
        ),
        patch(
            "app.application.chat.use_case._update_task_state_after_chat_turn",
            AsyncMock(),
        ),
        patch(
            "app.application.chat.use_case._record_explicit_memory_after_chat_turn",
            AsyncMock(),
        ),
        patch(
            "app.application.chat.use_case._observe_chat_completion",
            AsyncMock(),
        ),
    ):
        yield
