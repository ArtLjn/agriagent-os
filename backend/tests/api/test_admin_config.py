"""Tests for Admin Config API。"""

from fastapi.testclient import TestClient

from app.main import app
from tests.api.auth_helpers import admin_headers, auth_override_scope, ensure_admin_user


class TestListSkills:
    def test_returns_skill_list(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/skills", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


class TestListPrompts:
    def test_returns_prompt_list(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/prompts", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


class TestGetConfig:
    def test_config_masks_api_key(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/config", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        key = data["ai"]["api_key"]
        assert "***" in key

    def test_config_returns_monthly_and_weekly_quota(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/config", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["token_quota"]["monthly_limit"] == 3000000
        assert data["token_quota"]["weekly_limit"] == 750000
        assert data["token_quota"]["over_quota_action"] == "reject"
        assert "daily_limit" not in data["token_quota"]


class TestClearCache:
    def test_clear_cache(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).post("/admin/cache/clear", headers=admin_headers())

        assert resp.status_code == 200
        assert "cleared" in resp.json()


class TestReloadPrompts:
    def test_reload(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).post(
                "/admin/prompts/reload",
                headers=admin_headers(),
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
