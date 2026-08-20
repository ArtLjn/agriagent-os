"""agri_backend_v2 Trace 查询、证据状态和 timeline 聚合测试。"""

from __future__ import annotations

import pytest

from agent.api import traces as traces_api  # noqa: F401
from agent.config import settings
from agent.domains.harness.observability.trace import store
from agent.api import api_router


class FakeCursor:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = list(documents)

    def sort(self, spec, direction=None):
        if direction is not None:
            spec = [(spec, direction)]
        fields = spec if isinstance(spec, list) else [(spec, 1)]
        for field, direction in reversed(fields):
            self.documents.sort(
                key=lambda document: document.get(field) or "",
                reverse=direction < 0,
            )
        return self

    def limit(self, count: int):
        self.documents = self.documents[:count]
        return self

    async def to_list(self, length: int):
        return self.documents[:length]


class FakeCollection:
    def __init__(
        self, documents: list[dict], *, collection_names: list[str] | None = None
    ):
        self.documents = documents
        self.database = (
            FakeDatabase(collection_names) if collection_names is not None else None
        )

    def find(self, filter_doc: dict) -> FakeCursor:
        return FakeCursor(
            [document for document in self.documents if _matches(document, filter_doc)]
        )


class FakeDatabase:
    def __init__(self, collection_names: list[str]) -> None:
        self.collection_names = collection_names

    async def list_collection_names(self) -> list[str]:
        return self.collection_names


def _matches(document: dict, filter_doc: dict) -> bool:
    for key, expected in filter_doc.items():
        if key == "$and":
            if not all(_matches(document, branch) for branch in expected):
                return False
            continue
        if key == "$or":
            if not any(_matches(document, branch) for branch in expected):
                return False
            continue
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$exists" in expected and (key in document) != expected["$exists"]:
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$gt" in expected and not (
                actual is not None and actual > expected["$gt"]
            ):
                return False
            if "$lt" in expected and not (
                actual is not None and actual < expected["$lt"]
            ):
                return False
        elif actual != expected:
            return False
    return True


@pytest.fixture
def mongodb_enabled(monkeypatch):
    original = (
        settings.mongodb.enabled,
        settings.mongodb.uri,
        settings.mongodb.database,
    )
    settings.mongodb.enabled = True
    settings.mongodb.uri = "mongodb://fake"
    settings.mongodb.database = "test"
    yield
    settings.mongodb.enabled, settings.mongodb.uri, settings.mongodb.database = original


def test_trace_api_registers_formal_read_routes() -> None:
    paths = {route.path for route in api_router.routes}

    assert "/api/agri_backend_v2/traces/{trace_id}/nodes" in paths
    assert "/api/agri_backend_v2/traces/{trace_id}/events" in paths
    assert "/api/agri_backend_v2/traces/{trace_id}/timeline" in paths


@pytest.mark.asyncio
async def test_list_traces_filters_turn_and_identity(
    monkeypatch, mongodb_enabled
) -> None:
    records = FakeCollection(
        [{"request_id": "trace-1", "user_id": "u1", "farm_uid": "f1"}]
    )
    summaries = FakeCollection(
        [
            {
                "_id": "trace-1",
                "request_id": "trace-1",
                "trace_id": "trace-1",
                "conversation_id": "conv-1",
                "turn_id": "turn-1",
                "user_id": "u1",
                "farm_uid": "f1",
                "status": "success",
            },
            {
                "_id": "trace-other-user",
                "request_id": "trace-other-user",
                "conversation_id": "conv-1",
                "turn_id": "turn-1",
                "user_id": "u2",
                "farm_uid": "f1",
            },
        ]
    )
    monkeypatch.setattr(store, "_get_trace_collection", lambda: records)
    monkeypatch.setattr(store, "_get_summary_collection", lambda: summaries)

    result = await store.list_traces(
        conversation_id="conv-1",
        turn_id="turn-1",
        user_id="u1",
        farm_uid="f1",
    )

    assert [item["trace_id"] for item in result["items"]] == ["trace-1"]
    assert result["evidence_status"] == "ok"


@pytest.mark.asyncio
async def test_timeline_merges_nodes_and_events_without_payload_by_default(
    monkeypatch, mongodb_enabled
) -> None:
    nodes = FakeCollection(
        [
            {
                "trace_id": "trace-1",
                "request_id": "trace-1",
                "user_id": "u1",
                "farm_uid": "f1",
                "conversation_id": "conv-1",
                "turn_id": "turn-1",
                "node_type": "llm_call",
                "node_name": "planner",
                "step_index": 1,
                "start_time": "2026-08-18T10:00:02",
                "created_at": "2026-08-18T10:00:02",
            }
        ]
    )
    events = FakeCollection(
        [
            {
                "trace_id": "trace-1",
                "user_id": "u1",
                "farm_uid": "f1",
                "conversation_id": "conv-1",
                "turn_id": "turn-1",
                "event_id": "event-1",
                "seq": 1,
                "event_type": "started",
                "occurred_at": "2026-08-18T10:00:01",
                "data": {"secret": "should-not-be-default"},
            }
        ]
    )
    monkeypatch.setattr(store, "_get_trace_collection", lambda: nodes)
    monkeypatch.setattr(store, "_get_events_collection", lambda: events)

    result = await store.get_trace_timeline("trace-1", user_id="u1", farm_uid="f1")

    assert [item["record_kind"] for item in result["items"]] == ["event", "node"]
    assert [item["source"] for item in result["items"]] == [
        "traceEvents",
        "traceRecords",
    ]
    assert "data" not in result["items"][0]
    assert result["evidence_status"] == "ok"


@pytest.mark.asyncio
async def test_timeline_normalizes_utc_and_naive_timestamps(
    monkeypatch, mongodb_enabled
) -> None:
    nodes = FakeCollection(
        [
            {
                "trace_id": "trace-timezone",
                "user_id": "u1",
                "farm_uid": "f1",
                "node_type": "llm_call",
                "node_name": "model",
                "start_time": "2026-08-19T10:00:02Z",
            }
        ]
    )
    events = FakeCollection(
        [
            {
                "trace_id": "trace-timezone",
                "user_id": "u1",
                "farm_uid": "f1",
                "event_id": "event-timezone",
                "seq": 1,
                "event_type": "started",
                "occurred_at": "2026-08-19T10:00:01+00:00",
            }
        ]
    )
    monkeypatch.setattr(store, "_get_trace_collection", lambda: nodes)
    monkeypatch.setattr(store, "_get_events_collection", lambda: events)

    result = await store.get_trace_timeline(
        "trace-timezone", user_id="u1", farm_uid="f1"
    )

    assert [item["record_kind"] for item in result["items"]] == ["event", "node"]
    assert result["items"][0]["occurred_at"].endswith("Z")


@pytest.mark.asyncio
async def test_nodes_hide_resource_spans_by_default_and_can_expand_them(
    monkeypatch, mongodb_enabled
) -> None:
    nodes = FakeCollection(
        [
            {
                "trace_id": "trace-1",
                "user_id": "u1",
                "farm_uid": "f1",
                "node_type": "llm_call",
                "node_name": "model",
                "layer": "agent",
            },
            {
                "trace_id": "trace-1",
                "user_id": "u1",
                "farm_uid": "f1",
                "node_type": "mcp_call",
                "node_name": "get_weather",
                "layer": "resource",
            },
        ]
    )
    monkeypatch.setattr(store, "_get_trace_collection", lambda: nodes)

    compact = await store.get_trace_nodes(
        "trace-1", user_id="u1", farm_uid="f1"
    )
    expanded = await store.get_trace_nodes(
        "trace-1",
        include_resource_spans=True,
        user_id="u1",
        farm_uid="f1",
    )

    assert [node["node_type"] for node in compact["nodes"]] == ["llm_call"]
    assert {node["node_type"] for node in expanded["nodes"]} == {
        "llm_call",
        "mcp_call",
    }


@pytest.mark.asyncio
async def test_missing_trace_events_is_structured_not_available(
    monkeypatch, mongodb_enabled
) -> None:
    events = FakeCollection([], collection_names=["traceRecords"])
    monkeypatch.setattr(store, "_get_events_collection", lambda: events)

    result = await store.get_trace_events("trace-1", user_id="u1", farm_uid="f1")

    assert result["events"] == []
    assert result["evidence_status"] == "not_available"
    assert result["evidence"] == {
        "source": "traceEvents",
        "status": "missing",
        "code": "mongo_collection_missing",
    }


@pytest.mark.asyncio
async def test_mongo_not_configured_is_not_same_as_empty(monkeypatch) -> None:
    original = settings.mongodb.enabled
    settings.mongodb.enabled = False
    monkeypatch.setattr(store, "_get_events_collection", lambda: None)
    try:
        result = await store.get_trace_events("trace-1", user_id="u1", farm_uid="f1")
    finally:
        settings.mongodb.enabled = original

    assert result["evidence_status"] == "not_available"
    assert result["evidence"]["status"] == "not_configured"


@pytest.mark.asyncio
async def test_mongo_connection_failure_is_unavailable(
    monkeypatch, mongodb_enabled
) -> None:
    def fail_to_get_collection():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(store, "_get_events_collection", fail_to_get_collection)

    result = await store.get_trace_events("trace-1", user_id="u1", farm_uid="f1")

    assert result["evidence_status"] == "unavailable"
    assert result["evidence"]["status"] == "unavailable"
    assert result["evidence"]["code"] == "mongo_unavailable"
