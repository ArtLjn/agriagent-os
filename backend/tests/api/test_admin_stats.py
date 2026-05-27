"""Tests for Admin Token Stats API。"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app


def _mock_db():
    """创建 mock 数据库会话。"""
    return MagicMock()


@pytest.fixture
def client():
    mock_db = _mock_db()

    def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestTokenSummary:
    def test_returns_summary(self, client) -> None:
        mock_db = _mock_db()
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [
            ("qwen3.6-flash", "chat", 5000, 2000, 7000, 10),
        ]

        def _override():
            yield mock_db

        app.dependency_overrides[get_db] = _override
        try:
            resp = client.get("/admin/stats/tokens?farm_id=1&days=7")
            assert resp.status_code == 200
            data = resp.json()
            assert data["days"] == 7
            assert data["total_tokens"] == 7000
            assert data["total_requests"] == 10
            assert "qwen3.6-flash:chat" in data["by_model"]
        finally:
            app.dependency_overrides.clear()


class TestTokenDaily:
    def test_returns_daily_detail(self, client) -> None:
        mock_row = MagicMock()
        mock_row.model = "qwen3.6-flash"
        mock_row.call_type = "chat"
        mock_row.prompt_tokens = 100
        mock_row.completion_tokens = 50
        mock_row.total_tokens = 150
        mock_row.request_count = 2
        mock_row.estimated_cost_cny = 0.0035

        mock_db = _mock_db()
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_row]

        def _override():
            yield mock_db

        app.dependency_overrides[get_db] = _override
        try:
            resp = client.get("/admin/stats/tokens/daily?farm_id=1&date=2026-05-26")
            assert resp.status_code == 200
            data = resp.json()
            assert data["date"] == "2026-05-26"
            assert len(data["items"]) == 1
            assert data["items"][0]["model"] == "qwen3.6-flash"
        finally:
            app.dependency_overrides.clear()
