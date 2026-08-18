"""Trace collector Mongo projection contract tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.infra.trace import collector


class _FakeEventCollection:
    def __init__(self) -> None:
        self.docs: dict[tuple[str, str], dict] = {}
        self.update_calls: list[tuple[dict, dict, bool]] = []
        self.indexes: list[tuple[tuple[tuple[str, int], ...], dict]] = []

    async def update_one(self, selector: dict, update: dict, *, upsert: bool):
        self.update_calls.append((selector, update, upsert))
        identity = (selector["trace_id"], selector["event_id"])
        existing = self.docs.get(identity)
        if existing is None:
            assert upsert is True
            self.docs[identity] = dict(update["$set"])
            return SimpleNamespace(acknowledged=True, upserted_id=identity)
        existing.update(update["$set"])
        return SimpleNamespace(acknowledged=True, upserted_id=None)

    async def create_index(self, keys, **options):
        self.indexes.append((tuple(keys), dict(options)))
        return f"index-{len(self.indexes)}"


def _event(event_id: str = "evt-1") -> dict:
    return {
        "record_kind": "sse_event",
        "trace_id": "trace-1",
        "request_id": "trace-1",
        "user_id": "user-1",
        "farm_uid": "farm-1",
        "conversation_id": "conversation-1",
        "turn_id": "turn-1",
        "event_id": event_id,
        "event_type": "started",
        "seq": 1,
        "phase": "reasoning",
        "step_index": 1,
        "terminal": False,
        "status_before": "accepted",
        "status_after": "running",
        "occurred_at": "2026-08-18T10:00:00Z",
        "data": {},
    }


def test_trace_llm_call_keeps_model_input_and_output(monkeypatch) -> None:
    collector._queue.clear()
    monkeypatch.setattr(
        collector,
        "get_trace",
        lambda: SimpleNamespace(
            trace_id="trace-1",
            request_id="request-1",
            conversation_id="conversation-1",
            turn_id="turn-1",
            user_id="user-1",
            farm_uid="farm-1",
        ),
    )
    monkeypatch.setattr(collector, "get_step_index", lambda: 1)

    messages = [{"role": "user", "content": "查询天气"}]
    response = {"content": "杭州 28 度", "tool_calls": []}
    collector.trace_llm_call(
        model="qwen3.6-flash",
        messages=messages,
        response=response,
    )

    node = collector._queue[-1]
    assert node["input_data"]["messages"] == messages
    assert node["output_data"] == response


@pytest.mark.asyncio
async def test_flush_now_projects_events_when_trace_queue_is_empty(monkeypatch) -> None:
    event_coll = _FakeEventCollection()
    collector._queue.clear()
    collector._event_queue.clear()
    collector._event_queue.append(_event())
    monkeypatch.setattr(collector, "_get_collection", lambda: None)
    monkeypatch.setattr(collector, "_get_event_collection", lambda: event_coll)

    count = await collector.flush_now()

    assert count == 1
    assert len(event_coll.docs) == 1
    assert event_coll.docs[("trace-1", "evt-1")]["user_id"] == "user-1"
    assert event_coll.docs[("trace-1", "evt-1")]["farm_uid"] == "farm-1"
    assert not collector._event_queue


@pytest.mark.asyncio
async def test_event_projection_is_idempotent_for_replayed_event(monkeypatch) -> None:
    event_coll = _FakeEventCollection()
    collector._queue.clear()
    collector._event_queue.clear()
    event = _event()
    collector._event_queue.extend([dict(event), dict(event)])
    monkeypatch.setattr(collector, "_get_event_collection", lambda: event_coll)

    count = await collector.flush_now()

    assert count == 2
    assert len(event_coll.docs) == 1
    assert len(event_coll.update_calls) == 2
    assert event_coll.update_calls[0][0] == {
        "trace_id": "trace-1",
        "event_id": "evt-1",
    }
    assert all(call[2] is True for call in event_coll.update_calls)


@pytest.mark.asyncio
async def test_failed_event_projection_is_retained_and_not_marked_persisted(
    monkeypatch, caplog
) -> None:
    class _FailingCollection:
        async def update_one(self, *_args, **_kwargs):
            raise RuntimeError("mongo unavailable")

    collector._queue.clear()
    collector._event_queue.clear()
    collector._event_queue.append(_event())
    monkeypatch.setattr(
        collector, "_get_event_collection", lambda: _FailingCollection()
    )

    with caplog.at_level("ERROR"):
        count = await collector.flush_now()

    assert count == 0
    assert len(collector._event_queue) == 1
    assert "trace event projection failed" in caplog.text
    assert "trace_id=trace-1" in caplog.text
    assert "event_id=evt-1" in caplog.text


@pytest.mark.asyncio
async def test_start_trace_system_initializes_trace_indexes(monkeypatch) -> None:
    trace_coll = _FakeEventCollection()
    summary_coll = _FakeEventCollection()
    event_coll = _FakeEventCollection()
    collector._queue.clear()
    collector._event_queue.clear()
    monkeypatch.setattr(collector, "_get_collection", lambda: trace_coll)
    monkeypatch.setattr(collector, "_get_summary_collection", lambda: summary_coll)
    monkeypatch.setattr(collector, "_get_event_collection", lambda: event_coll)

    await collector.start_trace_system()
    try:
        event_indexes = {
            (keys, tuple(sorted(options.items())))
            for keys, options in event_coll.indexes
        }
        assert (
            (("trace_id", 1), ("event_id", 1)),
            (("background", True), ("unique", True)),
        ) in event_indexes
        assert (
            (("trace_id", 1), ("seq", 1)),
            (("background", True), ("unique", True)),
        ) in event_indexes
        assert any(
            keys == (("turn_id", 1), ("occurred_at", 1))
            for keys, _options in event_coll.indexes
        )
        assert any(
            keys == (("trace_id", 1), ("step_index", 1))
            for keys, _options in trace_coll.indexes
        )
        assert any(
            keys == (("conversation_id", 1), ("created_at", -1))
            for keys, _options in summary_coll.indexes
        )
    finally:
        await collector.stop_trace_system()
