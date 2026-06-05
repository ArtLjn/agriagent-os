"""Admin API 鉴权分类行为测试。"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.api.auth_helpers import (
    admin_headers,
    auth_override_scope,
    ensure_admin_user,
    ensure_regular_user,
    regular_headers,
)

AdminRequest = tuple[str, str, Callable[[str], dict]]

ADMIN_CONFIG_REQUESTS: list[AdminRequest] = [
    ("GET", "/admin/skills", lambda _method: {}),
    ("GET", "/admin/prompts", lambda _method: {}),
    ("GET", "/admin/config", lambda _method: {}),
    ("POST", "/admin/cache/clear", lambda _method: {}),
    ("POST", "/admin/prompts/reload", lambda _method: {}),
]

ADMIN_TRACE_REQUESTS: list[AdminRequest] = [
    ("GET", "/admin/traces?limit=10", lambda _method: {}),
    ("GET", "/admin/traces/missing-request/timeline", lambda _method: {}),
    ("GET", "/admin/traces/missing-request/nodes/1", lambda _method: {}),
    ("DELETE", "/admin/traces?before=2026-05-20", lambda _method: {}),
]

ADMIN_GUARDRAILS_REQUESTS: list[AdminRequest] = [
    ("GET", "/admin/guardrails-logs", lambda _method: {}),
]


@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_CONFIG_REQUESTS)
def test_admin_config_endpoints_reject_anonymous(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """匿名访问 admin config 相关接口返回 401。"""
    with auth_override_scope(app):
        resp = TestClient(app).request(method, path, **kwargs_factory(method))

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"


@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_CONFIG_REQUESTS)
def test_admin_config_endpoints_reject_regular_user(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """普通用户访问 admin config 相关接口返回 403。"""
    ensure_regular_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).request(
            method,
            path,
            headers=regular_headers(),
            **kwargs_factory(method),
        )

    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "AUTH_ADMIN_REQUIRED"


@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_CONFIG_REQUESTS)
def test_admin_config_endpoints_allow_admin(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """管理员访问 admin config 相关接口返回业务结果。"""
    ensure_admin_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).request(
            method,
            path,
            headers=admin_headers(),
            **kwargs_factory(method),
        )

    assert resp.status_code == 200


@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_TRACE_REQUESTS)
def test_admin_trace_endpoints_reject_anonymous(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """匿名访问 admin trace 相关接口返回 401。"""
    with auth_override_scope(app):
        resp = TestClient(app).request(method, path, **kwargs_factory(method))

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"


@pytest.mark.parametrize(("method", "path", "kwargs_factory"), ADMIN_TRACE_REQUESTS)
def test_admin_trace_endpoints_reject_regular_user(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """普通用户访问 admin trace 相关接口返回 403。"""
    ensure_regular_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).request(
            method,
            path,
            headers=regular_headers(),
            **kwargs_factory(method),
        )

    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "AUTH_ADMIN_REQUIRED"


@pytest.mark.parametrize(
    ("method", "path", "kwargs_factory"), ADMIN_GUARDRAILS_REQUESTS
)
def test_admin_guardrails_endpoints_reject_anonymous(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """匿名访问 admin guardrails 相关接口返回 401。"""
    with auth_override_scope(app):
        resp = TestClient(app).request(method, path, **kwargs_factory(method))

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"


@pytest.mark.parametrize(
    ("method", "path", "kwargs_factory"), ADMIN_GUARDRAILS_REQUESTS
)
def test_admin_guardrails_endpoints_reject_regular_user(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """普通用户访问 admin guardrails 相关接口返回 403。"""
    ensure_regular_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).request(
            method,
            path,
            headers=regular_headers(),
            **kwargs_factory(method),
        )

    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "AUTH_ADMIN_REQUIRED"


@pytest.mark.parametrize(
    ("method", "path", "kwargs_factory"), ADMIN_GUARDRAILS_REQUESTS
)
def test_admin_guardrails_endpoints_allow_admin(
    db_session,
    method: str,
    path: str,
    kwargs_factory: Callable[[str], dict],
):
    """管理员访问 admin guardrails 相关接口返回业务结果。"""
    ensure_admin_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).request(
            method,
            path,
            headers=admin_headers(),
            **kwargs_factory(method),
        )

    assert resp.status_code == 200
