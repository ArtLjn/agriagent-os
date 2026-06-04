"""Tests for Admin Config API。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestListSkills:
    def test_returns_skill_list(self, client) -> None:
        resp = client.get("/admin/skills")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


class TestListPrompts:
    def test_returns_prompt_list(self, client) -> None:
        resp = client.get("/admin/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


class TestGetConfig:
    def test_config_masks_api_key(self, client) -> None:
        resp = client.get("/admin/config")
        assert resp.status_code == 200
        data = resp.json()
        key = data["ai"]["api_key"]
        assert "***" in key

    def test_config_returns_monthly_and_weekly_quota(self, client) -> None:
        resp = client.get("/admin/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["token_quota"]["monthly_limit"] == 3000000
        assert data["token_quota"]["weekly_limit"] == 750000
        assert data["token_quota"]["over_quota_action"] == "reject"
        assert "daily_limit" not in data["token_quota"]


class TestClearCache:
    def test_clear_cache(self, client) -> None:
        resp = client.post("/admin/cache/clear")
        assert resp.status_code == 200
        assert "cleared" in resp.json()


class TestReloadPrompts:
    def test_reload(self, client) -> None:
        resp = client.post("/admin/prompts/reload")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
