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
        assert data["items"]
        metadata = data["items"][0]["metadata"]
        assert "permission_level" in metadata
        assert "risk_level" in metadata
        assert "metadata_incomplete" in metadata
        assert "context_dependencies" in metadata
        assert "cache_invalidation" in metadata
        assert "enabled" in metadata
        assert "disabled_reason" in metadata

    def test_returns_skill_status_summary(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/skills", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total"] == data["total"]
        assert data["summary"]["enabled"] > 0
        assert data["summary"]["disabled"] >= 1
        assert data["summary"]["admin_only"] >= 0
        disabled = [item for item in data["items"] if item["status"] == "disabled"]
        assert disabled
        assert disabled[0]["metadata"]["enabled"] is False

    def test_update_skill_enabled_state(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            disabled_resp = TestClient(app).put(
                "/admin/skills/get_cost_summary/enabled",
                headers=admin_headers(),
                json={"enabled": False, "disabled_reason": "测试禁用"},
            )
            list_resp = TestClient(app).get("/admin/skills", headers=admin_headers())
            enabled_resp = TestClient(app).put(
                "/admin/skills/get_cost_summary/enabled",
                headers=admin_headers(),
                json={"enabled": True},
            )

        assert disabled_resp.status_code == 200
        assert disabled_resp.json()["metadata"]["enabled"] is False
        assert disabled_resp.json()["metadata"]["disabled_reason"] == "测试禁用"
        items = {item["name"]: item for item in list_resp.json()["items"]}
        assert items["get_cost_summary"]["status"] == "disabled"
        assert items["get_cost_summary"]["metadata"]["disabled_reason"] == "测试禁用"
        assert enabled_resp.status_code == 200
        assert enabled_resp.json()["metadata"]["enabled"] is True
        assert enabled_resp.json()["metadata"]["disabled_reason"] is None


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
        assert data["token_quota"]["monthly_limit"] == 200000
        assert data["token_quota"]["weekly_limit"] == 50000
        assert data["token_quota"]["over_quota_action"] == "reject"
        assert "daily_limit" not in data["token_quota"]

    def test_config_returns_session_summary_flag(self, db_session) -> None:
        ensure_admin_user(db_session)
        with auth_override_scope(app):
            resp = TestClient(app).get("/admin/config", headers=admin_headers())

        assert resp.status_code == 200
        data = resp.json()
        assert data["ai"]["enable_session_summary"] is True


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
