"""Tests for Admin Token Stats API。"""

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.shared.database import get_db
from app.infra.mongo import set_mongo_client
from app.domains.users.dependencies import get_current_user
from app.main import app
from app.domains.farm.models import Farm
from app.platforms.evaluation.token_stats_models import TokenDailyStats
from app.platforms.evaluation.trace_models import TraceRecord
from app.domains.users.models import User


def _mock_db():
    """创建 mock 数据库会话。"""
    return MagicMock()


class FakeMongoCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_args):
        return self

    async def to_list(self, _length=None):
        return list(self._docs)


class FakeMongoCollection:
    def __init__(self, docs):
        self.docs = docs
        self.filters = []

    def find(self, filter_doc):
        self.filters.append(dict(filter_doc))
        docs = []
        for doc in self.docs:
            if doc.get("nodeType") != filter_doc.get("nodeType"):
                continue
            start_range = filter_doc.get("startTime", {})
            start_time = doc.get("startTime")
            if "$gte" in start_range and start_time < start_range["$gte"]:
                continue
            if "$lt" in start_range and start_time >= start_range["$lt"]:
                continue
            if "farmId" in filter_doc and doc.get("farmId") != filter_doc["farmId"]:
                continue
            if (
                "nodeName" in filter_doc
                and doc.get("nodeName") != filter_doc["nodeName"]
            ):
                continue
            docs.append(doc)
        return FakeMongoCursor(docs)


class FakeMongoClient:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, _database_name):
        return {"traceRecords": self.collection}


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
    def test_falls_back_to_daily_stats_when_hourly_trace_empty(
        self, client, db_session, admin_user
    ) -> None:
        farm = db_session.query(Farm).filter(Farm.id == 1).first()
        farm.user_id = "hourly-fallback-user"
        db_session.add(
            User(
                id="hourly-fallback-user",
                phone="18800000005",
                password_hash="h",
                nickname="小时回填用户",
                role="user",
                status="active",
            )
        )
        db_session.commit()
        db_session.add(
            TokenDailyStats(
                user_id="hourly-fallback-user",
                farm_id=1,
                date=date(2026, 7, 10),
                model="qwen3.6-flash",
                call_type="chat",
                prompt_tokens=100_000,
                completion_tokens=15_000,
                total_tokens=115_000,
                request_count=42,
            )
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
                "/admin/stats/tokens/hourly?start_date=2026-07-10&end_date=2026-07-10"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_tokens"] == 115_000
            assert data["total_requests"] == 42
            assert data["hours"] == ["00"]
            assert data["items"][0]["date"] == "2026-07-10"
            assert data["items"][0]["hour"] == "00"
            assert data["items"][0]["model"] == "qwen3.6-flash"
        finally:
            app.dependency_overrides.clear()

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

    def test_returns_hourly_usage_from_mongo_when_trace_table_missing(
        self, client, db_session, admin_user
    ) -> None:
        import app.platforms.admin.stats_routes as admin_stats

        farm = db_session.query(Farm).filter(Farm.id == 1).first()
        farm.user_id = "hourly-mongo-user"
        db_session.add(
            User(
                id="hourly-mongo-user",
                phone="18800000003",
                password_hash="h",
                nickname="Mongo 小时用户",
                role="user",
                status="active",
            )
        )
        db_session.commit()
        collection = FakeMongoCollection(
            [
                {
                    "farmId": 1,
                    "nodeType": "llm_call",
                    "nodeName": "qwen3.6-flash",
                    "startTime": datetime(2026, 6, 30, 9, 15),
                    "tokenUsage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "usage_source": "provider",
                    },
                },
                {
                    "farmId": 1,
                    "nodeType": "skill_call",
                    "nodeName": "ignored",
                    "startTime": datetime(2026, 6, 30, 9, 30),
                    "tokenUsage": {
                        "prompt_tokens": 1000,
                        "completion_tokens": 1000,
                        "usage_source": "provider",
                    },
                },
            ]
        )

        def _override_get_db():
            yield db_session

        def _override_current_user():
            return admin_user

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user] = _override_current_user
        set_mongo_client(FakeMongoClient(collection), "farm_manager")
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(admin_stats, "_trace_table_exists", lambda _db: False)
        try:
            resp = client.get(
                "/admin/stats/tokens/hourly?start_date=2026-06-30&end_date=2026-06-30"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_tokens"] == 150
            assert data["total_requests"] == 1
            assert data["hours"] == ["09"]
            assert data["items"][0]["user_id"] == "hourly-mongo-user"
            assert collection.filters[0]["nodeType"] == "llm_call"
        finally:
            app.dependency_overrides.clear()
            set_mongo_client(None)
            monkeypatch.undo()
