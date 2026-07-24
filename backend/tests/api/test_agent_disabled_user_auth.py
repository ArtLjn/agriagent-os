"""Agent 入口禁用用户鉴权回归测试。"""

from collections.abc import AsyncGenerator
from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.agent.executor.models import PendingActionDecision
from app.domains.conversation.routes import router
from app.domains.farm.models import Farm
from app.domains.users.models import User
from app.domains.users.tokens import create_access_token
from app.infra.limiter import limiter
from app.shared.database import Base, get_db


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


_test_engine = create_engine(
    "sqlite:///tests/test_agent_disabled_user_auth.db",
    connect_args={"check_same_thread": False},
)
event.listen(_test_engine, "connect", _set_sqlite_pragma)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(autouse=True)
def clean_agent_disabled_auth_db():
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    db = _TestSession()
    _add_user_and_farm(
        db,
        user_id="disabled-user-001",
        farm_id=41,
        phone="00000000401",
        nickname="禁用用户",
        status="disabled",
    )
    _add_user_and_farm(
        db,
        user_id="admin-user-001",
        farm_id=42,
        phone="00000000402",
        nickname="管理员",
        role="admin",
    )
    _add_user_and_farm(
        db,
        user_id="active-target-001",
        farm_id=43,
        phone="00000000403",
        nickname="正常目标用户",
    )
    db.commit()
    db.close()
    yield


@pytest.fixture
def app_client():
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)

    def override_get_db():
        db = _TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_disabled_user_chat_token_fails_before_advisor(app_client):
    """禁用用户 token 调用 /agent/chat 不进入 advisor。"""
    advisor = AsyncMock(return_value="should-not-call")

    with patch("app.application.chat.use_case.invoke_advisor", advisor):
        response = app_client.post(
            "/agent/chat",
            headers=_headers_for("disabled-user-001"),
            json={"message": "帮我看看农场"},
        )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_USER_DISABLED"
    assert advisor.await_count == 0


def test_admin_stream_simulate_disabled_user_fails_before_stream_advisor(app_client):
    """管理员 body 模拟禁用用户调用流式入口时，不进入 stream_advisor。"""
    stream_advisor = _stream_advisor_mock()

    with _patch_stream_chain(stream_advisor):
        response = app_client.post(
            "/agent/chat/stream",
            headers=_headers_for("admin-user-001"),
            json={
                "message": "模拟禁用用户",
                "simulate_user_id": "disabled-user-001",
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "AUTH_SIMULATED_USER_DISABLED"
    assert stream_advisor.call_count == 0


def test_admin_stream_simulate_active_user_can_enter_stream_advisor(app_client):
    """管理员 body 模拟正常用户时，流式入口使用目标用户。"""
    stream_advisor = _stream_advisor_mock()

    with _patch_stream_chain(stream_advisor):
        with app_client.stream(
            "POST",
            "/agent/chat/stream",
            headers=_headers_for("admin-user-001"),
            json={
                "message": "模拟正常用户",
                "simulate_user_id": "active-target-001",
            },
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "stream-ok" in body
    assert stream_advisor.call_args.kwargs["user_id"] == "active-target-001"
    assert stream_advisor.call_args.kwargs["farm_id"] == 43


def _headers_for(user_id: str) -> dict[str, str]:
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


def _add_user_and_farm(
    db,
    *,
    user_id: str,
    farm_id: int,
    phone: str,
    nickname: str,
    role: str = "user",
    status: str = "active",
) -> None:
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
    db.add(Farm(id=farm_id, name=f"{nickname}农场", user_id=user_id))


def _stream_advisor_mock() -> Mock:
    async def _stream_advisor(*_args, **_kwargs) -> AsyncGenerator[str, None]:
        yield "stream-ok"

    return Mock(side_effect=_stream_advisor)


@contextmanager
def _patch_stream_chain(stream_advisor: Mock):
    """隔离和鉴权无关的流式 pending/query/metadata 链路。"""
    with (
        patch("app.application.chat.stream_chat.stream_advisor", stream_advisor),
        patch(
            "app.application.chat.stream_chat.handle_pending_action",
            AsyncMock(return_value=PendingActionDecision.unhandled()),
        ),
        patch(
            "app.application.chat.stream_chat.resolve_query_menu_or_message",
            AsyncMock(return_value=("有效消息", None)),
        ),
        patch(
            "app.application.chat.stream_chat.build_pending_action_response",
            return_value=None,
        ),
        patch(
            "app.application.chat.stream_chat.build_pending_plan_response",
            return_value=None,
        ),
        patch(
            "app.application.chat.stream_chat._get_skill_names",
            AsyncMock(return_value=[]),
        ),
    ):
        yield
