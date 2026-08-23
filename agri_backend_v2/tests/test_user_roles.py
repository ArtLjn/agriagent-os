"""用户角色统一定义、注册授权和 SSE 视图规则测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from agent.api import health
from agent.domains.harness.runtime.projection import (
    ProjectionPermissionError,
    resolve_presentation_profile,
)
from business.api import auth
from business.api.users import AdminCreateUserRequest
from business.config import settings as business_settings
from business.services.tokens import create_access_token, decode_access_token
from shared.roles import UserRole, scope_for_role


def test_dev_role_uses_normal_user_scope() -> None:
    assert scope_for_role(UserRole.DEV) == scope_for_role(UserRole.USER)
    assert "admin:*" not in scope_for_role(UserRole.DEV)


def test_register_rejects_privileged_role_without_admin_identity() -> None:
    request = auth.RegisterRequest(
        phone="13800138000",
        password="password123",
        nickname="调试用户",
        role=UserRole.DEV,
    )

    with pytest.raises(HTTPException) as raised:
        auth.register_endpoint(request, current_user=None)

    assert raised.value.status_code == 403
    assert raised.value.detail["code"] == "role_assignment_forbidden"


def test_admin_can_select_dev_role_through_register(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_register(phone: str, password: str, nickname: str, *, role):
        calls.update(phone=phone, password=password, nickname=nickname, role=role)
        return SimpleNamespace(role=role.value), "dev-token"

    monkeypatch.setattr(auth, "register", fake_register)
    monkeypatch.setattr(
        auth,
        "_auth_response",
        lambda user, token: {"role": user.role, "token": token},
    )

    result = auth.register_endpoint(
        auth.RegisterRequest(
            phone="13800138000",
            password="password123",
            nickname="调试用户",
            role=UserRole.DEV,
        ),
        current_user={"role": UserRole.ADMIN.value},
    )

    assert result == {"role": UserRole.DEV.value, "token": "dev-token"}
    assert calls["role"] is UserRole.DEV


def test_register_phone_requires_eleven_digit_mobile_number() -> None:
    with pytest.raises(ValidationError):
        auth.RegisterRequest(phone="1380013800", password="password123")

    with pytest.raises(ValidationError):
        AdminCreateUserRequest(
            phone="+8613800138000",
            password="password123",
        )


def test_dev_token_contains_normal_user_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(business_settings.auth, "jwt_secret", "role-test-secret")
    token = create_access_token(
        user_id="dev-1",
        phone="13800138000",
        role=UserRole.DEV,
        farm_uid="farm-1",
        farm_id=1,
    )

    payload = decode_access_token(token)
    assert payload["role"] == UserRole.DEV.value
    assert payload["scope"] == "farm:read farm:write"


def test_dev_viewer_cannot_request_admin_debug_projection() -> None:
    assert (
        resolve_presentation_profile(
            execution_identity={"user_id": "dev-1", "role": UserRole.DEV.value},
            viewer_identity={"user_id": "dev-1", "role": UserRole.DEV.value},
            requested=None,
        )
        == "user"
    )
    with pytest.raises(ProjectionPermissionError):
        resolve_presentation_profile(
            execution_identity={"user_id": "dev-1", "role": UserRole.DEV.value},
            viewer_identity={"user_id": "dev-1", "role": UserRole.DEV.value},
            requested="admin_debug",
        )


class _FakeQuery:
    def __init__(self) -> None:
        self.filter_conditions = ()

    def outerjoin(self, *_args):
        return self

    def filter(self, *conditions):
        self.filter_conditions = conditions
        return self

    def order_by(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def all(self):
        return []


class _FakeDb:
    def __init__(self) -> None:
        self.query_instance = _FakeQuery()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def query(self, *_args):
        return self.query_instance


def test_dev_users_query_filters_dev_role(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_db = _FakeDb()
    previous = health.settings.environment
    previous_secret = health.settings.auth.jwt_secret
    health.settings.environment = "development"
    health.settings.auth.jwt_secret = "role-test-secret"
    monkeypatch.setattr("business.db.session_scope", lambda: fake_db)
    try:
        assert health.dev_users() == {"users": [], "total": 0}
        conditions = [
            str(condition) for condition in fake_db.query_instance.filter_conditions
        ]
        assert any("users.role" in condition for condition in conditions)
    finally:
        health.settings.environment = previous
        health.settings.auth.jwt_secret = previous_secret
