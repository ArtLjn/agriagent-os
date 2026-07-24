"""Tests for Admin Trace API。"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.shared.database import get_db
from app.main import app
from app.platforms.evaluation.trace_models import TraceRecord
from app.domains.users.models import User
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

    def test_list_traces_with_farm_id_uses_repository_fallback(
        self, db_session, monkeypatch
    ) -> None:
        import app.platforms.admin.trace_routes as admin_trace
        from app.shared.config import settings

        admin_user = ensure_admin_user(db_session)
        mock_record = MagicMock()
        mock_record.id = 7
        mock_record.request_id = "abc12345"
        mock_record.session_id = "sess-admin"
        mock_record.farm_id = 1
        mock_record.round_index = 0
        mock_record.node_type = "llm_call"
        mock_record.node_name = "planner"
        mock_record.duration_ms = 12
        mock_record.status = "success"
        mock_record.token_usage = {"total_tokens": 10}
        mock_record.error_message = None
        mock_record.created_at = datetime(2026, 6, 26, 12, 0, 0)

        class Repo:
            async def get_by_request_id(self, **kwargs):
                assert kwargs == {"farm_id": 1, "request_id": "abc12345"}
                return [mock_record]

        mock_db = _mock_db(admin_user)
        monkeypatch.setattr(settings.storage, "trace", "mysql")
        monkeypatch.setattr(admin_trace, "get_trace_repository", lambda db: Repo())

        with auth_override_scope(app), _db_override(mock_db):
            resp = TestClient(app).get(
                "/admin/traces?farm_id=1&request_id=abc12345",
                headers=admin_headers(),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["request_id"] == "abc12345"

    def test_list_traces_uses_mongo_when_storage_is_mongo_even_if_mysql_table_exists(
        self, db_session, monkeypatch
    ) -> None:
        import app.platforms.admin.trace_routes as admin_trace

        admin_user = ensure_admin_user(db_session)
        mock_db = _mock_db(admin_user)

        async def _mongo_page(**kwargs):
            assert kwargs["limit"] == 5
            return admin_trace.TracePage(items=[], total=3)

        from app.shared.config import settings

        monkeypatch.setattr(settings.storage, "trace", "mongo")
        monkeypatch.setattr(admin_trace, "_list_traces_from_mongo", _mongo_page)
        monkeypatch.setattr(admin_trace, "_trace_table_exists", lambda _db: True)

        with auth_override_scope(app), _db_override(mock_db):
            resp = TestClient(app).get(
                "/admin/traces?limit=5",
                headers=admin_headers(),
            )

        assert resp.status_code == 200
        assert resp.json()["total"] == 3
        mock_db.trace_query.count.assert_not_called()


class TestGetTraceRequests:
    def test_list_trace_requests_groups_nodes_by_request(self, db_session) -> None:
        from app.shared.config import settings
        from pytest import MonkeyPatch

        admin_user = ensure_admin_user(db_session)

        first_node = MagicMock()
        first_node.request_id = "req-new"
        first_node.session_id = "sess-1"
        first_node.farm_id = 2
        first_node.duration_ms = 10
        first_node.start_time = datetime(2026, 7, 10, 16, 0, 1)
        first_node.created_at = None
        first_node.end_time = None
        first_node.id = 1
        first_node.node_type = "routing"
        first_node.node_name = "skill_router"
        first_node.status = "success"
        first_node.error_message = None
        first_node.output_data = None
        first_node.token_usage = None

        second_node = MagicMock()
        second_node.request_id = "req-new"
        second_node.session_id = "sess-1"
        second_node.farm_id = 2
        second_node.duration_ms = 20
        second_node.start_time = datetime(2026, 7, 10, 16, 0, 2)
        second_node.created_at = None
        second_node.end_time = None
        second_node.id = 2
        second_node.node_type = "llm_call"
        second_node.node_name = "qwen"
        second_node.status = "success"
        second_node.error_message = None
        second_node.output_data = None
        second_node.token_usage = None

        old_node = MagicMock()
        old_node.request_id = "req-old"
        old_node.session_id = "sess-1"
        old_node.farm_id = 2
        old_node.duration_ms = 5
        old_node.start_time = datetime(2026, 7, 10, 15, 0, 0)
        old_node.created_at = None
        old_node.end_time = None
        old_node.id = 3
        old_node.node_type = "routing"
        old_node.node_name = "skill_router"
        old_node.status = "success"
        old_node.error_message = None
        old_node.output_data = None
        old_node.token_usage = None

        mock_db = _mock_db(admin_user)
        mock_db.trace_query.all.return_value = [first_node, second_node, old_node]
        monkeypatch = MonkeyPatch()
        monkeypatch.setattr(settings.storage, "trace", "mysql")

        try:
            with auth_override_scope(app), _db_override(mock_db):
                resp = TestClient(app).get(
                    "/admin/traces/requests?session_id=sess-1&limit=20",
                    headers=admin_headers(),
                )
        finally:
            monkeypatch.undo()

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["items"][0] == {
            "request_id": "req-new",
            "session_id": "sess-1",
            "farm_id": 2,
            "node_count": 2,
            "total_duration_ms": 30,
            "created_at": "2026-07-10T16:00:02",
            "status": "success",
            "status_reason": None,
            "error_count": 0,
            "root_error": None,
            "metrics": {
                "total_duration_ms": 30,
                "llm_duration_ms": 20,
                "tool_duration_ms": 0,
                "rag_duration_ms": 0,
                "memory_duration_ms": 0,
                "planner_duration_ms": 10,
                "reflection_duration_ms": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "llm_calls": 1,
                "tool_calls": 0,
                "skill_calls": 0,
            },
            "started_at": "2026-07-10T16:00:01",
            "ended_at": "2026-07-10T16:00:02",
        }

    def test_list_trace_requests_reads_mongo_request_summary(
        self, db_session, monkeypatch
    ) -> None:
        import app.platforms.admin.trace_requests as trace_requests

        class FakeCursor:
            async def to_list(self, _length):
                return [
                    {
                        "_id": "2:req-blocked",
                        "requestId": "req-blocked",
                        "sessionId": "sess-1",
                        "farmId": 2,
                        "nodeCount": 4,
                        "totalDurationMs": 1234,
                        "createdAt": datetime(2026, 7, 24, 15, 0, 0),
                        "status": "blocked",
                        "statusReason": "pending_plan_contract_blocked",
                        "errorCount": 1,
                        "rootError": {
                            "code": "pending_plan_contract_blocked",
                            "message": "缺少 name",
                        },
                        "metrics": {"tool_calls": 0},
                    }
                ]

        class FakeCollection:
            async def count_documents(self, filter_doc):
                assert filter_doc == {"requestId": "req-blocked"}
                return 1

            def find(self, filter_doc):
                assert filter_doc == {"requestId": "req-blocked"}
                return self

            def sort(self, keys):
                assert keys == [("createdAt", -1), ("requestId", -1)]
                return self

            def skip(self, offset):
                assert offset == 0
                return self

            def limit(self, limit):
                assert limit == 20
                return FakeCursor()

        class FakeDatabase:
            def __getitem__(self, name):
                assert name == "traceRequests"
                return FakeCollection()

        monkeypatch.setattr(
            trace_requests, "get_mongo_database", lambda: FakeDatabase()
        )

        page = trace_requests.list_trace_requests_from_mongo(
            request_id="req-blocked",
            session_id=None,
            farm_id=None,
            limit=20,
            offset=0,
        )

        import asyncio

        data = asyncio.run(page)
        assert data.total == 1
        assert data.items[0].status == "blocked"
        assert data.items[0].status_reason == "pending_plan_contract_blocked"
        assert data.items[0].root_error == {
            "code": "pending_plan_contract_blocked",
            "message": "缺少 name",
        }


class TestGetTimeline:
    def test_timeline_orders_rounds_by_first_node_time(self, db_session) -> None:
        from app.shared.config import settings
        from pytest import MonkeyPatch

        admin_user = ensure_admin_user(db_session)

        early_record = MagicMock()
        early_record.id = 2
        early_record.request_id = "abc12345"
        early_record.round_index = 1
        early_record.node_type = "routing"
        early_record.node_name = "skill_router"
        early_record.duration_ms = 0
        early_record.status = "success"
        early_record.token_usage = None
        early_record.start_time = datetime(2026, 7, 10, 16, 32, 46)
        early_record.end_time = None
        early_record.error_message = None
        early_record.input_data = None
        early_record.output_data = None

        late_record = MagicMock()
        late_record.id = 1
        late_record.request_id = "abc12345"
        late_record.round_index = 0
        late_record.node_type = "final_reply"
        late_record.node_name = "final_reply"
        late_record.duration_ms = 0
        late_record.status = "success"
        late_record.token_usage = None
        late_record.start_time = datetime(2026, 7, 10, 16, 32, 54)
        late_record.end_time = None
        late_record.error_message = None
        late_record.input_data = None
        late_record.output_data = None

        mock_db = _mock_db(admin_user)
        mock_db.trace_query.all.return_value = [late_record, early_record]
        monkeypatch = MonkeyPatch()
        monkeypatch.setattr(settings.storage, "trace", "mysql")

        try:
            with auth_override_scope(app), _db_override(mock_db):
                resp = TestClient(app).get(
                    "/admin/traces/abc12345/timeline",
                    headers=admin_headers(),
                )

            assert resp.status_code == 200
            rounds = resp.json()["rounds"]
            assert [round_item["round_index"] for round_item in rounds] == [1, 0]
        finally:
            monkeypatch.undo()

    def test_timeline_returns_rounds(self, db_session) -> None:
        from app.shared.config import settings

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
        from pytest import MonkeyPatch

        monkeypatch = MonkeyPatch()
        monkeypatch.setattr(settings.storage, "trace", "mysql")

        try:
            with auth_override_scope(app), _db_override(mock_db):
                resp = TestClient(app).get(
                    "/admin/traces/abc12345/timeline",
                    headers=admin_headers(),
                )
                assert resp.status_code == 200
                data = resp.json()
                assert "request_id" in data
                assert "rounds" in data
        finally:
            monkeypatch.undo()

    def test_timeline_serializes_trace_json_and_datetime(self, db_session) -> None:
        from app.shared.config import settings

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
        from pytest import MonkeyPatch

        monkeypatch = MonkeyPatch()
        monkeypatch.setattr(settings.storage, "trace", "mysql")

        try:
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
        finally:
            monkeypatch.undo()


class TestGetDiagnostics:
    def test_diagnostics_returns_structured_pending_and_context(
        self, db_session
    ) -> None:
        from app.shared.config import settings
        from pytest import MonkeyPatch

        admin_user = ensure_admin_user(db_session)
        context_record = MagicMock()
        context_record.id = 1
        context_record.round_index = 0
        context_record.node_type = "context_build"
        context_record.node_name = "context_bundle"
        context_record.input_data = {"block_count": 1}
        context_record.output_data = {
            "context_dependency_diagnostics": [
                {"block_key": "workers", "status": "selected"}
            ]
        }
        context_record.status = "success"
        context_record.error_message = None

        pending_record = MagicMock()
        pending_record.id = 2
        pending_record.round_index = 0
        pending_record.node_type = "pending_action"
        pending_record.node_name = "settle_labor_payment"
        pending_record.input_data = {}
        pending_record.output_data = {
            "status": "created",
            "confirmation_context": {"target_object": {"worker": "张三"}},
            "metadata": {"cache_groups_cleared": ["cost_summary"]},
        }
        pending_record.status = "success"
        pending_record.error_message = None

        reflection_record = MagicMock()
        reflection_record.id = 3
        reflection_record.round_index = 0
        reflection_record.node_type = "reflection_check"
        reflection_record.node_name = "pre_write_plan"
        reflection_record.input_data = {"skill_name": "create_cost_record"}
        reflection_record.output_data = {
            "trigger": "pre_write_plan",
            "decision": "block_write",
            "reason": "确认文案与待执行参数不一致。",
            "checks": ["write_plan_consistency"],
            "issues": [
                {
                    "code": "confirmation_param_mismatch",
                    "severity": "blocker",
                }
            ],
        }
        reflection_record.status = "success"
        reflection_record.error_message = None

        mock_db = _mock_db(admin_user)
        mock_db.trace_query.all.return_value = [
            context_record,
            pending_record,
            reflection_record,
        ]
        monkeypatch = MonkeyPatch()
        monkeypatch.setattr(settings.storage, "trace", "mysql")

        try:
            with auth_override_scope(app), _db_override(mock_db):
                resp = TestClient(app).get(
                    "/admin/traces/abc12345/diagnostics",
                    headers=admin_headers(),
                )
        finally:
            monkeypatch.undo()

        assert resp.status_code == 200
        data = resp.json()
        assert data["context_dependencies"][0]["block_key"] == "workers"
        assert data["context_dependency_diagnostic"][0]["diagnosis"] == (
            "selected_by_skill_metadata"
        )
        assert data["pending_lifecycle"][0]["structured_context"] == {
            "target_object": {"worker": "张三"}
        }
        assert data["pending_action_diagnostic"]["statuses"] == ["created"]
        assert data["pending_action_diagnostic"]["cache_invalidation"] == {
            "status": "recorded",
            "groups": ["cost_summary"],
        }
        assert data["tool_not_called_reason"] == (
            "request_bypassed_agent_or_tool_selection_missing"
        )
        assert data["reflection_checks"] == [
            {
                "trigger": "pre_write_plan",
                "decision": "block_write",
                "reason": "确认文案与待执行参数不一致。",
                "checks": ["write_plan_consistency"],
                "issues": [
                    {
                        "code": "confirmation_param_mismatch",
                        "severity": "blocker",
                    }
                ],
                "input": {"skill_name": "create_cost_record"},
            }
        ]
        assert data["reflection_diagnostic"] == {
            "blocked": True,
            "decisions": ["block_write"],
            "issue_codes": ["confirmation_param_mismatch"],
        }
        assert "timeline" in data["drilldown_links"]


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
