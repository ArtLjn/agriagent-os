"""Tests for Admin Trace API。"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app


def _mock_db():
    """创建 mock 数据库会话。"""
    mock_db = MagicMock()
    return mock_db


@pytest.fixture
def client():
    mock_db = _mock_db()

    def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestGetTraces:
    def test_list_traces(self, client) -> None:
        resp = client.get("/admin/traces?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data


class TestGetTimeline:
    def test_timeline_returns_rounds(self, client) -> None:
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
        mock_db = _mock_db()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_record
        ]

        def _override():
            yield mock_db

        app.dependency_overrides[get_db] = _override
        try:
            resp = client.get("/admin/traces/abc12345/timeline")
            assert resp.status_code == 200
            data = resp.json()
            assert "request_id" in data
            assert "rounds" in data
        finally:
            app.dependency_overrides.clear()

    def test_timeline_serializes_trace_json_and_datetime(self, client) -> None:
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

        mock_db = _mock_db()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_record
        ]

        def _override():
            yield mock_db

        app.dependency_overrides[get_db] = _override
        try:
            resp = client.get("/admin/traces/abc12345/timeline")
            assert resp.status_code == 200
            node = resp.json()["rounds"][0]["nodes"][0]
            assert node["start_time"] == "2026-06-04T14:03:22"
            assert node["input_data"] == {"block_count": 6}
            assert node["output_data"] == {"blocks": [{"key": "farm"}]}
        finally:
            app.dependency_overrides.clear()


class TestDeleteTraces:
    def test_delete_before_date(self, client) -> None:
        resp = client.delete("/admin/traces?before=2026-05-20")
        assert resp.status_code == 200
        data = resp.json()
        assert "deleted" in data
