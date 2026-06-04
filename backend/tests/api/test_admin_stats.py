"""Tests for Admin Token Stats API。"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.main import app
from app.models.farm import Farm
from app.models.trace import TraceRecord
from app.models.user import User


def _mock_db():
    """创建 mock 数据库会话。"""
    return MagicMock()


@pytest.fixture
def admin_user():
    return User(
        id="admin-001",
        phone="99999999999",
        password_hash="h",
        nickname="管理员",
        role="admin",
        status="active",
    )


@pytest.fixture
def client(admin_user):
    mock_db = _mock_db()

    def _override_get_db():
        yield mock_db

    def _override_current_user():
        return admin_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_current_user
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
            resp = client.get("/admin/stats/tokens?days=7")
            assert resp.status_code == 200
            data = resp.json()
            assert data["days"] == 7
            assert data["total_tokens"] == 7000
            assert data["total_requests"] == 10
            assert "qwen3.6-flash:chat" in data["by_model"]
        finally:
            app.dependency_overrides.clear()

    def test_filters_by_user_id(self, client) -> None:
        mock_db = _mock_db()
        query = mock_db.query.return_value
        query.filter.return_value = query
        query.group_by.return_value.all.return_value = []

        def _override():
            yield mock_db

        app.dependency_overrides[get_db] = _override
        try:
            resp = client.get("/admin/stats/tokens?user_id=user-001&days=7")
            assert resp.status_code == 200
            filter_args = query.filter.call_args.args
            assert any("user_id" in str(arg) for arg in filter_args)
            assert not any("farm_id" in str(arg) for arg in filter_args)
        finally:
            app.dependency_overrides.clear()

    def test_requires_admin(self, client) -> None:
        def _override_current_user():
            return User(
                id="user-001",
                phone="11111111111",
                password_hash="h",
                nickname="普通用户",
                role="user",
                status="active",
            )

        app.dependency_overrides[get_current_user] = _override_current_user
        try:
            resp = client.get("/admin/stats/tokens?days=7")
            assert resp.status_code == 403
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
        query = mock_db.query.return_value
        query.filter.return_value = query
        query.all.return_value = [mock_row]

        def _override():
            yield mock_db

        app.dependency_overrides[get_db] = _override
        try:
            resp = client.get("/admin/stats/tokens/daily?date=2026-05-26")
            assert resp.status_code == 200
            data = resp.json()
            assert data["date"] == "2026-05-26"
            assert len(data["items"]) == 1
            assert data["items"][0]["model"] == "qwen3.6-flash"
        finally:
            app.dependency_overrides.clear()


class TestTokenHourly:
    def test_returns_hourly_usage_grouped_by_user_model_and_hour(
        self, client, db_session, admin_user
    ) -> None:
        farm = db_session.query(Farm).filter(Farm.id == 1).first()
        farm.user_id = "hourly-user-001"
        db_session.add(
            User(
                id="hourly-user-001",
                phone="18800000000",
                password_hash="h",
                nickname="小时用户",
                role="user",
                status="active",
            )
        )
        db_session.add_all(
            [
                TraceRecord(
                    request_id="hour001",
                    farm_id=1,
                    node_type="llm_call",
                    node_name="gemma4:31b",
                    start_time=datetime(2026, 6, 4, 9, 5),
                    token_usage={
                        "prompt_tokens": 100,
                        "completion_tokens": 40,
                        "usage_source": "provider",
                    },
                    status="success",
                ),
                TraceRecord(
                    request_id="hour002",
                    farm_id=1,
                    node_type="llm_call",
                    node_name="gemma4:31b",
                    start_time=datetime(2026, 6, 4, 9, 40),
                    token_usage={
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "usage_source": "provider",
                    },
                    status="success",
                ),
                TraceRecord(
                    request_id="hour003",
                    farm_id=1,
                    node_type="llm_call",
                    node_name="llama",
                    start_time=datetime(2026, 6, 4, 10, 0),
                    token_usage={
                        "prompt_tokens": 20,
                        "completion_tokens": 30,
                        "usage_source": "usage_metadata",
                    },
                    status="success",
                ),
                TraceRecord(
                    request_id="hour004",
                    farm_id=1,
                    node_type="skill_call",
                    node_name="ignored",
                    start_time=datetime(2026, 6, 4, 9, 10),
                    token_usage={"prompt_tokens": 999, "completion_tokens": 999},
                    status="success",
                ),
            ]
        )
        db_session.commit()

        def _override_get_db():
            yield db_session

        def _override_current_user():
            return admin_user

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user] = _override_current_user
        try:
            resp = client.get(
                "/admin/stats/tokens/hourly?start_date=2026-06-04&end_date=2026-06-04"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["start_date"] == "2026-06-04"
            assert data["end_date"] == "2026-06-04"
            assert data["total_tokens"] == 205
            assert data["total_requests"] == 3
            assert data["hours"] == ["09", "10"]

            first = data["items"][0]
            assert first["hour"] == "09"
            assert first["user_id"] == "hourly-user-001"
            assert first["model"] == "gemma4:31b"
            assert first["prompt_tokens"] == 110
            assert first["completion_tokens"] == 45
            assert first["total_tokens"] == 155
            assert first["request_count"] == 2
        finally:
            app.dependency_overrides.clear()
