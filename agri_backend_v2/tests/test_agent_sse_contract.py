"""SSE 公共契约的最小回归测试。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from agent.api import turns
from agent.domains.harness.runtime.projection import (
    ProjectionPermissionError,
    project_event,
    resolve_presentation_profile,
)
from agent.platforms.persistence.redis import sse, turn_store


def test_done_keeps_termination_context_without_breaking_legacy_shape() -> None:
    legacy = sse.done("completed", "turn-1")
    current = sse.done(
        "terminated",
        "turn-2",
        stop_reason="step_budget_exhausted",
        step_count=5,
    )

    assert legacy == {
        "type": "done",
        "data": {"status": "completed", "turn_id": "turn-1"},
    }
    assert current["data"] == {
        "status": "terminated",
        "turn_id": "turn-2",
        "stop_reason": "step_budget_exhausted",
        "step_count": 5,
    }


def test_sse_event_id_is_transport_cursor() -> None:
    wire = sse.sse_event(
        "done",
        {"event_id": "evt-7", "seq": 7},
        event_id="evt-7",
    )

    assert wire.startswith("event: done\nid: evt-7\n")
    payload = json.loads(wire.split("data: ", 1)[1])
    assert payload == {"event_id": "evt-7", "seq": 7}


def test_step_and_tool_failure_events_share_explicit_correlation_fields() -> None:
    started = sse.step_started("turn-1", 2)
    completed = sse.step_completed("turn-1", 2, status="failed", tool_count=1)
    failed = sse.tool_failed(
        "turn-1",
        "call-1",
        "get_weather",
        2,
        {"code": "tool_failed", "message": "查询失败"},
    )

    assert started["type"] == "step.started"
    assert completed["data"]["step_index"] == 2
    assert failed["data"]["tool_call_id"] == "call-1"
    assert failed["data"]["step"] == 2


def test_terminated_state_exposes_legacy_failed_fields() -> None:
    state = {"status": "terminated", "stop_reason": "step_budget_exhausted"}

    assert turn_store.legacy_status_fields(state) == {
        "status": "terminated",
        "stop_reason": "step_budget_exhausted",
        "legacy_status": "failed",
        "legacy_error_code": "step_budget_exhausted",
    }


def test_user_projection_hides_reasoning_and_internal_fields() -> None:
    projected = project_event(
        {
            "type": "thought",
            "event_id": "evt-1",
            "trace_id": "trace-1",
            "data": {"content": "隐藏推理", "authorization": "secret"},
        },
        profile="user",
        execution_identity={"user_id": "user-1"},
        viewer_identity={"user_id": "user-1", "role": "user"},
    )

    assert projected is None


def test_user_projection_keeps_replay_identity_without_diagnostics() -> None:
    projected = project_event(
        {
            "type": "accepted",
            "event_id": "evt-public",
            "turn_id": "turn-public",
            "conversation_id": "conversation-public",
            "seq": 1,
            "trace_id": "trace-private",
            "data": {},
        },
        profile="user",
        execution_identity={"user_id": "user-1"},
        viewer_identity={"user_id": "user-1", "role": "user"},
    )

    assert projected == {
        "type": "progress",
        "data": {"message": "正在处理请求"},
        "event_id": "evt-public",
        "turn_id": "turn-public",
        "conversation_id": "conversation-public",
    }


def test_admin_projection_keeps_diagnostic_envelope_but_redacts_sensitive_data() -> None:
    projected = project_event(
        {
            "type": "action",
            "event_id": "evt-1",
            "seq": 1,
            "trace_id": "trace-1",
            "data": {"tool_name": "get_weather", "authorization": "secret"},
        },
        profile="admin_debug",
        execution_identity={"user_id": "user-1"},
        viewer_identity={"user_id": "admin-1", "role": "admin"},
    )

    assert projected is not None
    assert projected["presentation_profile"] == "admin_debug"
    assert projected["impersonation"] is True
    assert projected["data"]["authorization"] == "[REDACTED]"


def test_only_admin_viewer_can_request_debug_projection() -> None:
    with pytest.raises(ProjectionPermissionError):
        resolve_presentation_profile(
            execution_identity={"user_id": "user-1"},
            viewer_identity={"user_id": "user-1", "role": "user"},
            requested="admin_debug",
        )


@pytest.mark.asyncio
async def test_turn_events_reuses_event_id_as_sse_id(monkeypatch) -> None:
    async def fake_get_turn(_turn_id: str) -> dict[str, str]:
        return {"user_id": "user-1", "farm_id": "1", "status": "completed"}

    async def fake_stream_events(_turn_id: str, *, after_seq: int = 0):
        assert after_seq == 0
        yield {
            "seq": 1,
            "event_id": "evt-turn-1",
            "type": "done",
            "data": {"status": "completed", "turn_id": "turn-1"},
            "terminal": True,
        }

    monkeypatch.setattr(turns, "get_turn", fake_get_turn)
    monkeypatch.setattr(turns, "_check_access", lambda *_args: None)
    monkeypatch.setattr(turns, "stream_events", fake_stream_events)

    response = await turns.turn_events(
        "turn-1",
        after_seq=0,
        authorization="Bearer test",
    )
    chunks = [chunk async for chunk in response.body_iterator]

    assert chunks == [
        "event: done\n"
        "id: evt-turn-1\n"
        'data: {"status": "completed", "seq": 1, '
        '"event_id": "evt-turn-1"}\n\n'
    ]


@pytest.mark.asyncio
async def test_turn_events_resolves_last_event_id_without_reexecuting_turn(
    monkeypatch,
) -> None:
    async def fake_get_turn(_turn_id: str) -> dict[str, str]:
        return {"user_id": "user-1", "farm_id": "1", "status": "completed"}

    async def fake_resolve_event_seq(_turn_id: str, event_id: str) -> int:
        assert event_id == "evt-turn-7"
        return 7

    async def fake_stream_events(_turn_id: str, *, after_seq: int = 0):
        assert after_seq == 7
        yield {
            "seq": 8,
            "event_id": "evt-turn-8",
            "type": "done",
            "data": {"status": "completed", "turn_id": "turn-1"},
            "terminal": True,
        }

    monkeypatch.setattr(turns, "get_turn", fake_get_turn)
    monkeypatch.setattr(turns, "_check_access", lambda *_args: None)
    monkeypatch.setattr(turns, "resolve_event_seq", fake_resolve_event_seq)
    monkeypatch.setattr(turns, "stream_events", fake_stream_events)

    response = await turns.turn_events(
        "turn-1",
        after_seq=None,
        authorization="Bearer test",
        last_event_id="evt-turn-7",
    )
    chunks = [chunk async for chunk in response.body_iterator]

    assert 'id: evt-turn-8\n' in chunks[0]
    assert '"seq": 8' in chunks[0]


@pytest.mark.asyncio
async def test_cancelled_queued_turn_persists_stop_reason_before_done(monkeypatch) -> None:
    update = AsyncMock()
    publish = AsyncMock()

    async def fake_get_turn(_turn_id: str) -> dict[str, str]:
        return {
            "turn_id": "turn-cancel",
            "user_id": "user-1",
            "farm_id": "1",
            "conversation_id": "conversation-1",
            "scope_hash": "scope-1",
            "status": "accepted",
        }

    monkeypatch.setattr(turns, "get_turn", fake_get_turn)
    monkeypatch.setattr(turns, "_check_access", lambda *_args: None)
    monkeypatch.setattr(turns, "update_turn", update)
    monkeypatch.setattr(turns, "publish_event", publish)
    monkeypatch.setattr(turns, "remove_from_queues", AsyncMock())

    result = await turns.cancel_turn("turn-cancel", authorization="Bearer test")

    assert result["status"] == "cancelled"
    assert update.await_args_list[0].kwargs == {
        "status": "cancelled",
        "phase": "terminal",
        "stop_reason": "user_cancelled",
        "error_code": "turn_cancelled",
        "error_message": "本轮任务已取消",
        "finalization_pending": False,
    }
    assert update.await_args_list[1].kwargs == {"finalization_pending": False}
    published = [call.args[1] for call in publish.await_args_list]
    assert [event["type"] for event in published] == [
        "cancelled",
        "final_answer",
        "turn.terminated",
        "done",
    ]
    assert published[2]["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_resolve_event_seq_returns_none_for_evicted_event(monkeypatch) -> None:
    async def fake_read_events(_turn_id: str) -> list[dict[str, object]]:
        return [{"event_id": "evt-current", "seq": 3}]

    monkeypatch.setattr(turn_store, "read_events", fake_read_events)

    assert await turn_store.resolve_event_seq("turn-1", "evt-evicted") is None
