"""Worker Redis Stream pending message recovery tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agent.application import worker


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
