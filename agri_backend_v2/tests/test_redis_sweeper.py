"""Redis 协调索引回收器测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agent.application import sweeper


@pytest.mark.asyncio
async def test_sweep_once_is_noop_when_redis_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sweeper, "get_client", lambda: None)

    assert await sweeper.sweep_once() == {
        "active": 0,
        "queue": 0,
        "approval": 0,
    }


@pytest.mark.asyncio
async def test_sweep_once_trims_and_expires_dispatch_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncMock()
    client.xtrim = AsyncMock(return_value=0)
    client.expire = AsyncMock(return_value=True)
    monkeypatch.setattr(sweeper, "get_client", lambda: client)
    monkeypatch.setattr(
        sweeper,
        "_cleanup_active_indexes",
        AsyncMock(return_value=2),
    )
    monkeypatch.setattr(
        sweeper,
        "_cleanup_queue_indexes",
        AsyncMock(return_value=3),
    )
    monkeypatch.setattr(
        sweeper,
        "_cleanup_user_indexes",
        AsyncMock(return_value=1),
    )
    monkeypatch.setattr(
        sweeper,
        "_cleanup_approval_indexes",
        AsyncMock(return_value=4),
    )

    result = await sweeper.sweep_once()

    assert result == {"active": 2, "queue": 3, "user": 1, "approval": 4}
    client.xtrim.assert_awaited_once()
    client.expire.assert_awaited_once()
