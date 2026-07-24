"""Agent AI 入口禁用用户鉴权回归测试。"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.domains.farm.models import Farm
from app.domains.users.models import User
from tests.api.auth_helpers import (
    admin_headers,
    auth_override_scope,
    ensure_admin_user,
    ensure_regular_user,
    regular_headers,
)


def test_disabled_user_token_cannot_call_agent_chat(db_session) -> None:
    """禁用用户自己的旧 token 不能继续调用非流式 AI 对话。"""
    user = ensure_regular_user(db_session)
    user.status = "disabled"
    db_session.commit()
    advisor = AsyncMock(return_value="不应调用")

    with auth_override_scope(app), patch(
        "app.application.chat.use_case.invoke_advisor", advisor
    ):
        resp = TestClient(app).post(
            "/agent/chat",
            json={"message": "帮我看看农场状态"},
            headers=regular_headers(),
        )

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_USER_DISABLED"
    advisor.assert_not_awaited()


def test_admin_cannot_stream_chat_as_disabled_simulated_user(db_session) -> None:
    """管理员也不能通过模拟身份让禁用用户继续调用流式 AI 对话。"""
    ensure_admin_user(db_session)
    disabled_user = User(
        id="disabled-sim-user-001",
        phone="18800000003",
        password_hash="h",
        nickname="禁用用户",
        role="user",
        status="disabled",
    )
    db_session.add(disabled_user)
    db_session.flush()
    db_session.add(Farm(name="禁用用户农场", user_id=disabled_user.id))
    db_session.commit()
    stream_advisor = AsyncMock()

    with auth_override_scope(app), patch(
        "app.application.chat.stream_chat.stream_advisor", stream_advisor
    ):
        resp = TestClient(app).post(
            "/agent/chat/stream",
            json={
                "message": "帮我看看农场状态",
                "simulate_user_id": disabled_user.id,
            },
            headers=admin_headers(),
        )

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_USER_DISABLED"
    stream_advisor.assert_not_awaited()
