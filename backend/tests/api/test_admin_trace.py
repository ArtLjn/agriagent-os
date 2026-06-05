"""Tests for Admin Trace API。"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app
from app.models.trace import TraceRecord
from app.models.user import User
from tests.api.auth_helpers import admin_headers, auth_override_scope, ensure_admin_user


def _mock_db(admin_user: User | None = None):
    """创建同时支持鉴权查询和 trace 查询的 mock 数据库会话。"""
    mock_db = MagicMock()
    user_query = MagicMock()
    trace_query = MagicMock()

    user_query.filter.return_value.first.return_value = admin_user
    trace_query.filter.return_value = trace_query
    trace_query.order_by.return_value = trace_query
    trace_query.offset.return_value = trace_query
    trace_query.limit.return_value = trace_query
    trace_query.all.return_value = []
    trace_query.count.return_value = 0
    trace_query.delete.return_value = 0

    def _query(model):
        if model is User:
            return user_query
        if model is TraceRecord:
            return trace_query
        return MagicMock()

    mock_db.query.side_effect = _query
    mock_db.trace_query = trace_query
    return mock_db


@contextmanager
def _db_override(mock_db) -> Iterator[None]:
    """临时替换数据库依赖，并在退出时恢复原有 overrides。"""
    original_overrides = dict(app.dependency_overrides)

    def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


class TestGetTraces:
    def test_list_traces(self, db_session) -> None:
        admin_user = ensure_admin_user(db_session)
        mock_db = _mock_db(admin_user)

        with auth_override_scope(app), _db_override(mock_db):
            resp = TestClient(app).get(
                "/admin/traces?limit=10", headers=admin_headers()
            )

            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert "total" in data


class TestGetTimeline:
    def test_timeline_returns_rounds(self, db_session) -> None:
        admin_user = ensure_admin_user(db_session)
        mock_record = MagicMock()
        mock_record.request_id = "abc12345"
        mock_record.round_index = 0
        mock_record.node_type = "llm_call"
        mock_record.node_name = "qwen"
        mock_record.duration_ms = 100
        mock_record.status = "success"
        mock_record.token_usage = '{"total_tokens": 150}'
        mock_record.start_time = "2026-05-26T10:00:00"
        mock_record.end_time = "2026-05-26T10:00:00"
        mock_record.error_message = None
        mock_record.input_data = None
        mock_record.output_data = None

        # 配置 mock_db 的查询链
        mock_db = _mock_db(admin_user)
        mock_db.trace_query.all.return_value = [mock_record]

        with auth_override_scope(app), _db_override(mock_db):
            resp = TestClient(app).get(
                "/admin/traces/abc12345/timeline",
                headers=admin_headers(),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "request_id" in data
            assert "rounds" in data

    def test_timeline_serializes_trace_json_and_datetime(self, db_session) -> None:
        admin_user = ensure_admin_user(db_session)
        mock_record = MagicMock()
        mock_record.request_id = "abc12345"
        mock_record.round_index = 0
        mock_record.node_type = "prompt_render"
        mock_record.node_name = "context_builder"
        mock_record.duration_ms = 42
        mock_record.status = "success"
        mock_record.token_usage = {"total_tokens": 150}
        mock_record.start_time = datetime(2026, 6, 4, 14, 3, 22)
        mock_record.end_time = datetime(2026, 6, 4, 14, 3, 23)
        mock_record.error_message = None
        mock_record.input_data = {"block_count": 6}
        mock_record.output_data = {"blocks": [{"key": "farm"}]}

        mock_db = _mock_db(admin_user)
        mock_db.trace_query.all.return_value = [mock_record]

        with auth_override_scope(app), _db_override(mock_db):
            resp = TestClient(app).get(
                "/admin/traces/abc12345/timeline",
                headers=admin_headers(),
            )
            assert resp.status_code == 200
            node = resp.json()["rounds"][0]["nodes"][0]
            assert node["start_time"] == "2026-06-04T14:03:22"
            assert node["input_data"] == {"block_count": 6}
            assert node["output_data"] == {"blocks": [{"key": "farm"}]}


class TestDeleteTraces:
    def test_delete_before_date(self, db_session) -> None:
        admin_user = ensure_admin_user(db_session)
        mock_db = _mock_db(admin_user)

        with auth_override_scope(app), _db_override(mock_db):
            resp = TestClient(app).delete(
                "/admin/traces?before=2026-05-20",
                headers=admin_headers(),
            )

            assert resp.status_code == 200
            data = resp.json()
            assert "deleted" in data
