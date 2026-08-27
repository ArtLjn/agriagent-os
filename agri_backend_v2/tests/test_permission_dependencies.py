"""共享权限策略、REST 依赖和 MCP 工具授权测试。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from agent import deps as agent_deps
from business.api import api_router
from business.api import deps as business_deps
from business.api import users as users_api
from business.mcp_auth import McpAuthFailure
from business import mcp_auth
from business.tools import cost, farm, planting_plan, planting_units, user_settings
from business.tools import _headers as mcp_headers
from business.services.tokens import TokenExpiredError, TokenInvalidError
from shared.api_response import install_api_exception_handlers
from shared.roles import Permission, UserRole, has_permission, scope_for_role


def test_role_and_scope_permissions_use_intersection() -> None:
    user_scope = scope_for_role(UserRole.USER)
    assert has_permission(UserRole.USER, user_scope, Permission.FARM_WRITE)
    assert not has_permission(UserRole.USER, "farm:read", Permission.FARM_WRITE)
    assert not has_permission(UserRole.USER, None, Permission.FARM_READ)
    assert not has_permission("unknown", user_scope, Permission.FARM_READ)
    assert not has_permission(UserRole.DEV, user_scope, Permission.ADMIN_DEBUG)
    assert has_permission(
        UserRole.ADMIN, "admin:* farm:read", Permission.ADMIN_USER_READ
    )


def test_business_permission_dependency_returns_principal_or_403() -> None:
    dependency = business_deps.require_permission(Permission.FARM_WRITE)
    principal = {
        "role": UserRole.USER.value,
        "scope": scope_for_role(UserRole.USER),
        "user_id": "user-1",
    }
    assert dependency(principal) is principal

    with pytest.raises(HTTPException) as raised:
        dependency({**principal, "scope": "farm:read"})
    assert raised.value.status_code == 403
    assert raised.value.detail["code"] == "permission_denied"
    assert raised.value.detail["meta"]["permission"] == Permission.FARM_WRITE.value


def test_agent_permission_dependency_has_same_contract() -> None:
    dependency = agent_deps.require_permission(Permission.TRACE_READ)
    principal = {
        "role": UserRole.USER.value,
        "scope": "trace:read",
    }
    assert dependency(principal) is principal


def test_mcp_operation_permission_rejects_write_without_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_write(permission=None):
        assert permission is Permission.FARM_WRITE
        raise mcp_headers.McpToolAuthorizationError(permission)

    monkeypatch.setattr(mcp_headers, "get_principal", reject_write)

    with pytest.raises(mcp_headers.McpToolAuthorizationError) as raised:
        mcp_headers.require_farm_operation_permission(
            "create", read_operations={"query"}, write_operations={"create"}
        )
    assert raised.value.code == "permission_denied"
    assert raised.value.permission is Permission.FARM_WRITE


def test_mcp_operation_permission_accepts_read_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = {
        "role": UserRole.USER.value,
        "scope": f"{Permission.MCP_INVOKE.value} {Permission.FARM_READ.value}",
        "farm_id": 7,
    }

    def allow_read(permission=None):
        assert permission is Permission.FARM_READ
        return principal

    monkeypatch.setattr(mcp_headers, "get_principal", allow_read)
    result = mcp_headers.require_farm_operation_permission(
        "query", read_operations={"query"}, write_operations={"create"}
    )
    assert result is principal


def test_mcp_tool_registry_maps_read_and_write_operations() -> None:
    assert (
        mcp_headers.permission_for_tool("manage_cost", "query") is Permission.FARM_READ
    )
    assert (
        mcp_headers.permission_for_tool("manage_cost", "create")
        is Permission.FARM_WRITE
    )
    assert mcp_headers.permission_for_tool("manage_cost", "unknown") is None


def _business_test_client(principal: dict | None = None) -> TestClient:
    app = FastAPI()
    install_api_exception_handlers(app)
    app.include_router(api_router)
    if principal is not None:
        app.dependency_overrides[business_deps.get_current_user] = lambda: principal
    return TestClient(app)


def test_business_routes_return_401_without_token() -> None:
    with _business_test_client() as client:
        response = client.get("/api/v2/farms/my")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "missing_authorization"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (TokenInvalidError("bad"), "invalid_token"),
        (TokenExpiredError("old"), "token_expired"),
    ],
)
def test_business_routes_reject_invalid_or_expired_token(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str
) -> None:
    monkeypatch.setattr(
        business_deps,
        "decode_access_token",
        lambda _token: (_ for _ in ()).throw(error),
    )
    with _business_test_client() as client:
        response = client.get(
            "/api/v2/farms/my", headers={"Authorization": "Bearer test"}
        )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == code


def test_business_route_returns_403_for_missing_permission() -> None:
    principal = {
        "user_id": "user-1",
        "farm_id": 1,
        "farm_uid": "farm-1",
        "role": UserRole.USER.value,
        "scope": Permission.PROFILE_READ.value,
    }
    with _business_test_client(principal) as client:
        response = client.get("/api/v2/farms/my")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def test_dev_role_cannot_read_admin_users_and_admin_can(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev = {
        "user_id": "dev-1",
        "farm_id": 1,
        "farm_uid": "farm-1",
        "role": "dev",
        "scope": scope_for_role("dev"),
    }
    with _business_test_client(dev) as client:
        denied = client.get("/api/v2/admin/users/user-1")
    assert denied.status_code == 403

    admin = {
        "user_id": "admin-1",
        "farm_id": 1,
        "farm_uid": "farm-1",
        "role": "admin",
        "scope": scope_for_role("admin"),
    }
    monkeypatch.setattr(
        users_api.user_service,
        "get_admin_user_detail",
        lambda _user_id: {"id": "user-1"},
    )
    with _business_test_client(admin) as client:
        allowed = client.get("/api/v2/admin/users/user-1")
    assert allowed.status_code == 200
    assert allowed.json() == {"id": "user-1"}


def test_business_resource_scope_is_still_checked_after_permission() -> None:
    principal = {
        "user_id": "user-1",
        "farm_id": 1,
        "farm_uid": "farm-1",
        "role": "user",
        "scope": scope_for_role("user"),
    }
    with _business_test_client(principal) as client:
        response = client.get("/api/v2/farms/2")
    assert response.status_code == 403


def test_mcp_query_tool_succeeds_with_read_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(farm, "get_farm_id_from_headers", lambda _permission: 7)
    monkeypatch.setattr(
        farm.farm_service, "build_summary", lambda farm_id: {"farm_id": farm_id}
    )
    assert farm.get_farm_status() == {"farm_id": 7}


def test_mcp_write_tool_rejects_scope_before_database_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject(permission=None):
        assert permission is Permission.FARM_WRITE
        raise mcp_headers.McpToolAuthorizationError(Permission.FARM_WRITE)

    monkeypatch.setattr(mcp_headers, "get_principal", reject)
    with pytest.raises(mcp_headers.McpToolAuthorizationError):
        cost.manage_cost(
            operation="create",
            record_type="cost",
            category="肥料",
            amount=10,
            record_date="2026-08-25",
        )


def test_mcp_write_tool_succeeds_after_registry_permission_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = {"user_id": "user-1", "farm_id": 7}
    captured: dict[str, object] = {}

    class FakeDb:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(
        mcp_headers,
        "get_principal",
        lambda permission=None: (
            captured.setdefault("permission", permission),
            principal,
        )[1],
    )
    monkeypatch.setattr(planting_units, "session_scope", lambda: FakeDb())
    monkeypatch.setattr(
        planting_units.work_order_service,
        "create_unit",
        lambda _db, **kwargs: {"id": 8, **kwargs},
    )

    result = planting_units.manage_planting_units(
        operation="create", cycle_id=3, name="东棚 A 区", area_mu=1.5
    )
    assert captured["permission"] is Permission.FARM_WRITE
    assert result["id"] == 8
    assert result["farm_id"] == 7


def test_mcp_planting_plan_commit_preserves_idempotency_and_farm_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = {"user_id": "user-1", "farm_id": 7}
    captured: dict[str, object] = {}

    class FakeDb:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(
        mcp_headers,
        "get_principal",
        lambda permission=None: (
            captured.setdefault("permission", permission),
            principal,
        )[1],
    )
    monkeypatch.setattr(planting_plan, "session_scope", lambda: FakeDb())
    monkeypatch.setattr(
        planting_plan.planting_plan_service,
        "commit_planting_plan",
        lambda _db, **kwargs: captured.update(kwargs) or {"status": "committed"},
    )

    result = planting_plan.commit_planting_plan(
        client_request_id="request-1",
        approval_fingerprint="approval-1",
        plan={"crop_name": "番茄"},
    )

    assert result == {"status": "committed"}
    assert captured["permission"] is Permission.FARM_WRITE
    assert captured["farm_id"] == 7
    assert captured["client_request_id"] == "request-1"
    assert captured["approval_fingerprint"] == "approval-1"


def test_mcp_profile_tool_returns_data_with_profile_read_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = {"user_id": "user-1", "farm_id": 1}
    monkeypatch.setattr(user_settings, "get_principal", lambda _permission: principal)
    monkeypatch.setattr(
        user_settings.user_service,
        "get_user_settings",
        lambda _user_id: {"default_city": "苏州"},
    )
    assert user_settings.manage_user_settings("query") == {
        "user_id": "user-1",
        "configured": True,
        "settings": {"default_city": "苏州"},
    }


def test_mcp_delegation_db_farm_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class FakeDb:
        def __init__(self):
            self.values = iter(
                [
                    type(
                        "User", (), {"id": "user-1", "status": "active", "role": "user"}
                    )(),
                    type(
                        "Farm", (), {"id": 2, "uid": "farm-2", "user_id": "other-user"}
                    )(),
                ]
            )

        def execute(self, _query):
            return Result(next(self.values))

        def close(self):
            pass

    monkeypatch.setattr(mcp_auth, "SessionLocal", FakeDb)
    with pytest.raises(McpAuthFailure) as raised:
        mcp_auth._resolve_principal({"sub": "user-1", "farm_uid": "farm-2"}, {})
    assert raised.value.status_code == 403


def test_mcp_authenticated_user_without_mcp_scope_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    request = SimpleNamespace(
        state=SimpleNamespace(
            principal={
                "user_id": "user-1",
                "role": "user",
                "scope": Permission.FARM_READ.value,
            }
        )
    )
    monkeypatch.setattr("fastmcp.server.dependencies.get_http_request", lambda: request)
    with pytest.raises(mcp_headers.McpToolAuthorizationError) as raised:
        mcp_headers.get_principal(Permission.FARM_READ)
    assert raised.value.permission is Permission.MCP_INVOKE
