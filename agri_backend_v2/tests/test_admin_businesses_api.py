"""管理员业务目录接口契约测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shared.api_response import install_api_exception_handlers

from agent.api import admin_businesses, admin_prompts, api_router
from agent.plugins import PluginError, PluginScan


def _client() -> TestClient:
    app = FastAPI()
    install_api_exception_handlers(app)
    app.include_router(api_router)
    return TestClient(app)


def _admin(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in (admin_businesses, admin_prompts):
        monkeypatch.setattr(
            module,
            "parse_identity",
            lambda _authorization: {"role": "admin", "scope": "admin:*"},
        )


def _manifest(name: str, *, skills: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        display_name="农场助理",
        description="农场经营管理助手",
        skill_paths=[Path(f"skill-{index}") for index in range(skills)],
    )


def test_business_list_requires_authentication() -> None:
    with _client() as client:
        response = client.get("/api/v2/admin/businesses")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "missing_authorization"


def test_regular_user_cannot_list_businesses(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_businesses,
        "parse_identity",
        lambda _authorization: {"role": "user", "scope": "farm:read"},
    )

    with _client() as client:
        response = client.get(
            "/api/v2/admin/businesses",
            headers={"Authorization": "Bearer user-token"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def test_admin_business_list_reports_active_and_invalid_entries(monkeypatch) -> None:
    _admin(monkeypatch)
    monkeypatch.setattr(
        admin_businesses.settings.plugins,
        "manifest",
        SimpleNamespace(name="farm"),
    )
    monkeypatch.setattr(
        admin_businesses,
        "list_plugins",
        lambda _root: [
            PluginScan(name="farm", manifest=_manifest("farm")),
            PluginScan(
                name="broken",
                manifest=None,
                error_code="plugin_manifest_unknown_fields",
            ),
        ],
    )

    with _client() as client:
        response = client.get(
            "/api/v2/admin/businesses",
            headers={"Authorization": "Bearer admin-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "active": "farm",
        "total": 2,
        "items": [
            {
                "name": "farm",
                "display_name": "农场助理",
                "description": "农场经营管理助手",
                "skill_count": 2,
                "error_code": None,
            },
            {
                "name": "broken",
                "display_name": None,
                "description": None,
                "skill_count": 0,
                "error_code": "plugin_manifest_unknown_fields",
            },
        ],
    }


def test_switch_business_requires_admin(monkeypatch) -> None:
    with _client() as client:
        unauth = client.put(
            "/api/v2/admin/businesses/active",
            json={"name": "companion"},
        )
    assert unauth.status_code == 401

    monkeypatch.setattr(
        admin_businesses,
        "parse_identity",
        lambda _authorization: {"role": "user", "scope": "farm:read"},
    )
    with _client() as client:
        denied = client.put(
            "/api/v2/admin/businesses/active",
            json={"name": "companion"},
            headers={"Authorization": "Bearer user-token"},
        )
    assert denied.status_code == 403


def test_admin_can_switch_active_business(monkeypatch) -> None:
    _admin(monkeypatch)
    original_manifest = admin_businesses.settings.plugins.manifest
    monkeypatch.setattr(
        admin_businesses.settings.plugins,
        "manifest",
        original_manifest,
    )

    with _client() as client:
        response = client.put(
            "/api/v2/admin/businesses/active",
            json={"name": "companion"},
            headers={"Authorization": "Bearer admin-token"},
        )
        listing = client.get(
            "/api/v2/admin/businesses",
            headers={"Authorization": "Bearer admin-token"},
        )
        prompt_data = client.get(
            "/api/v2/admin/prompts",
            headers={"Authorization": "Bearer admin-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "active": "companion",
        "display_name": "陪伴助手",
        "skill_count": 2,
    }
    assert admin_businesses.settings.plugins.active == "companion"
    assert listing.json()["active"] == "companion"
    system = next(
        item
        for item in prompt_data.json()["items"]
        if item["name"] == "system"
    )
    assert system["business"] == "companion"
    assert system["content"] == (
        admin_businesses.settings.plugins.manifest.system_prompt_path.read_text(
            encoding="utf-8"
        )
    )


def test_switch_unknown_business_returns_404(monkeypatch) -> None:
    _admin(monkeypatch)

    with _client() as client:
        response = client.put(
            "/api/v2/admin/businesses/active",
            json={"name": "missing"},
            headers={"Authorization": "Bearer admin-token"},
        )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "business_not_found"


def test_business_catalog_failure_returns_503(monkeypatch) -> None:
    _admin(monkeypatch)

    def unavailable(_root):
        raise PluginError("plugin_root_missing", "/secret/path")

    monkeypatch.setattr(admin_businesses, "list_plugins", unavailable)

    with _client() as client:
        response = client.get(
            "/api/v2/admin/businesses",
            headers={"Authorization": "Bearer admin-token"},
        )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "business_catalog_unavailable"
    assert detail["message"] == "业务目录不可用"
    assert "secret" not in response.text
