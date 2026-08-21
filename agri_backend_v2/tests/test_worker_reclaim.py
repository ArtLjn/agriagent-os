"""Worker Redis Stream pending message recovery tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agent.application import worker
from agent.domains.harness.runtime.turn import Turn
from agent.platforms.persistence.redis.coordination import TurnLease


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        ("1-0", [("2-0", {"turn_id": "turn-2"})]),
        ("1-0", [("2-0", {"turn_id": "turn-2"})], []),
    ],
)
async def test_reclaim_supports_two_and_three_item_xautoclaim(
    monkeypatch: pytest.MonkeyPatch,
    response: tuple,
) -> None:
    client = AsyncMock()
    client.xautoclaim = AsyncMock(return_value=response)
    monkeypatch.setattr(worker, "dispatch_key", lambda: "test:dispatch")

    reclaimed = await worker._reclaim_messages(client, "worker-1")

    assert reclaimed == [("2-0", {"turn_id": "turn-2"})]
    client.xautoclaim.assert_awaited_once()
    client.xpending_range.assert_not_awaited()


@pytest.mark.asyncio
async def test_reclaim_falls_back_when_xautoclaim_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncMock()
    client.xautoclaim = AsyncMock(
        side_effect=RuntimeError("unknown command `XAUTOCLAIM`")
    )
    client.xpending_range = AsyncMock(
        return_value=[
            {"message_id": "2-0", "time_since_delivered": 31_000},
        ]
    )
    client.xclaim = AsyncMock(return_value=[("2-0", {"turn_id": "turn-2"})])
    monkeypatch.setattr(worker, "dispatch_key", lambda: "test:dispatch")

    reclaimed = await worker._reclaim_messages(client, "worker-1")

    assert reclaimed == [("2-0", {"turn_id": "turn-2"})]
    client.xpending_range.assert_awaited_once()
    client.xclaim.assert_awaited_once()


def _lease() -> TurnLease:
    return TurnLease(
        turn_id="turn-1",
        scope_hash="scope-1",
        user_scope_hash="user-scope-1",
        token="lease-1",
    )


@pytest.mark.asyncio
async def test_duplicate_dispatch_skips_turn_owned_by_another_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recover = AsyncMock()
    monkeypatch.setattr(
        worker, "inspect_turn_lease", AsyncMock(return_value="held")
    )
    monkeypatch.setattr(worker, "_recover_interrupted_turn", recover)

    should_run = await worker._prepare_execution_lease(
        Turn(turn_id="turn-1"), {"status": "running"}, _lease()
    )

    assert should_run is False
    recover.assert_not_awaited()


@pytest.mark.asyncio
async def test_accepted_turn_reclaims_missing_lease_without_replaying_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = AsyncMock(return_value=True)
    monkeypatch.setattr(
        worker, "inspect_turn_lease", AsyncMock(return_value="missing")
    )
    monkeypatch.setattr(worker, "claim_recovered_lease", claim)

    should_run = await worker._prepare_execution_lease(
        Turn(turn_id="turn-1"), {"status": "accepted"}, _lease()
    )

    assert should_run is True
    claim.assert_awaited_once()


@pytest.mark.asyncio
async def test_running_turn_with_missing_lease_is_finalized_without_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recover = AsyncMock()
    monkeypatch.setattr(
        worker, "inspect_turn_lease", AsyncMock(return_value="missing")
    )
    monkeypatch.setattr(worker, "_recover_interrupted_turn", recover)
    turn = Turn(turn_id="turn-1")
    state = {"status": "running"}

    should_run = await worker._prepare_execution_lease(turn, state, _lease())

    assert should_run is False
    recover.assert_awaited_once_with(turn, state)


@pytest.mark.asyncio
async def test_failed_turn_processing_leaves_dispatch_message_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncMock()
    monkeypatch.setattr(
        worker,
        "get_turn",
        AsyncMock(return_value={"turn_id": "turn-1", "status": "accepted"}),
    )
    monkeypatch.setattr(
        worker,
        "_run_turn",
        AsyncMock(side_effect=RuntimeError("worker process interrupted")),
    )

    await worker._process_messages(
        client,
        "worker-2",
        "dispatch-stream",
        [("1-0", {"turn_id": "turn-1"})],
    )

    client.xack.assert_not_awaited()


@pytest.mark.asyncio
async def test_pending_finalization_recovery_does_not_enter_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncMock()
    state = {
        "turn_id": "turn-1",
        "status": "failed",
        "final_answer": "失败答复",
        "finalization_pending": "1",
        "farm_id": "1",
        "user_id": "user-1",
        "conversation_id": "conversation-1",
    }
    run_turn = AsyncMock()
    finish = AsyncMock(return_value=True)
    recovered_state = {**state, "finalization_pending": "0"}
    get_turn = AsyncMock(side_effect=[state, recovered_state])
    monkeypatch.setattr(worker, "get_turn", get_turn)
    monkeypatch.setattr(worker, "run_turn", run_turn)
    monkeypatch.setattr(worker, "_finish_assistant_persistence", finish)
    update_turn = AsyncMock()
    monkeypatch.setattr(worker, "update_turn", update_turn)

    await worker._process_messages(
        client,
        "worker-2",
        "dispatch-stream",
        [("1-0", {"turn_id": "turn-1"})],
    )

    run_turn.assert_not_awaited()
    finish.assert_awaited_once()
    client.xack.assert_awaited_once()


@pytest.mark.asyncio
async def test_context_source_failure_finalizes_without_entering_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    turn = Turn(turn_id="turn-1", conversation_id="conversation-1")
    update_turn = AsyncMock()
    publish_event = AsyncMock()
    finish = AsyncMock(return_value=True)
    monkeypatch.setattr(worker, "update_turn", update_turn)
    monkeypatch.setattr(worker, "publish_event", publish_event)
    monkeypatch.setattr(worker, "_finish_assistant_persistence", finish)

    await worker._finalize_context_failure(
        turn,
        code="context_source_unavailable",
        message="Mongo unavailable",
        trace_id="trace-1",
    )

    assert update_turn.await_args.kwargs["error_code"] == "context_source_unavailable"
    assert publish_event.await_count == 3
    finish.assert_awaited_once()
