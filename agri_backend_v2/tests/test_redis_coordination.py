"""Redis 并发协调层单元测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import TimeoutError as RedisTimeoutError

from agent.config import settings
from agent.platforms.persistence.redis import coordination
from agent.platforms.persistence.redis.redis_store import key


def test_scope_hash_isolated_by_user_farm_and_conversation() -> None:
    first = coordination.scope_hash("user-a", 1, "same")
    same_identity = coordination.scope_hash("user-a", 1, "same")
    other_user = coordination.scope_hash("user-b", 1, "same")
    other_farm = coordination.scope_hash("user-a", 2, "same")
    other_conversation = coordination.scope_hash("user-a", 1, "other")

    assert first == same_identity
    assert len({first, other_user, other_farm, other_conversation}) == 4


def test_key_uses_configured_prefix() -> None:
    original = settings.redis.key_prefix
    settings.redis.key_prefix = "fm:test:agent"
    try:
        assert key("turn", "t-1") == "fm:test:agent:turn:t-1"
    finally:
        settings.redis.key_prefix = original


@pytest.mark.asyncio
async def test_acquire_turn_maps_admission_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_enabled = settings.redis.enabled
    original_global = settings.redis.global_active_limit
    original_user = settings.redis.user_active_limit
    settings.redis.enabled = True
    settings.redis.global_active_limit = 8
    settings.redis.user_active_limit = 2

    async def fake_eval_script(script, keys, args):
        assert len(keys) == 6
        assert args[2:] == [8, 2, 2, 32, "turn-1"]
        return 0

    monkeypatch.setattr(coordination, "eval_script", fake_eval_script)
    try:
        lease = await coordination.acquire_turn(
            turn_id="turn-1",
            user_id="user-1",
            farm_id=1,
            conversation_id="conv-1",
        )
    finally:
        settings.redis.enabled = original_enabled
        settings.redis.global_active_limit = original_global
        settings.redis.user_active_limit = original_user

    assert lease.turn_id == "turn-1"
    assert lease.lock_key.endswith(":conversation:" + lease.scope_hash + ":lock")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "code"),
    [(1, "agent_overloaded"), (2, "user_concurrency_limit")],
)
async def test_acquire_turn_rejects_capacity_conflicts(
    monkeypatch: pytest.MonkeyPatch,
    result: int,
    code: str,
) -> None:
    original_enabled = settings.redis.enabled
    settings.redis.enabled = True

    async def fake_eval_script(script, keys, args):
        return result

    monkeypatch.setattr(coordination, "eval_script", fake_eval_script)
    try:
        with pytest.raises(coordination.TurnAdmissionError) as exc_info:
            await coordination.acquire_turn(
                turn_id="turn-1",
                user_id="user-1",
                farm_id=1,
                conversation_id="conv-1",
            )
    finally:
        settings.redis.enabled = original_enabled

    assert exc_info.value.code == code


@pytest.mark.asyncio
async def test_renew_timeout_is_unavailable_not_confirmed_lease_loss(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        coordination,
        "eval_script",
        AsyncMock(side_effect=RedisTimeoutError("读取超时")),
    )
    lease = coordination.TurnLease("turn-1", "scope-1", "user-1", "token-1")
    with pytest.raises(coordination.CoordinationError) as error:
        await coordination.renew_turn(lease)
    assert not isinstance(error.value, coordination.TurnLeaseLost)
    assert isinstance(error.value.__cause__, RedisTimeoutError)


@pytest.mark.asyncio
async def test_transient_renew_timeout_recovers_without_stopping_worker(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings.redis, "conversation_lock_ttl_ms", 200)
    monkeypatch.setattr(settings.redis, "conversation_lock_renew_ms", 15)
    monkeypatch.setattr(settings.redis, "socket_timeout_ms", 10)
    stop, ready = asyncio.Event(), asyncio.Event()
    calls = 0

    async def renew(_lease):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise coordination.CoordinationError("暂时超时")
        if calls == 3:
            stop.set()
        return True

    monkeypatch.setattr(coordination, "renew_turn", renew)
    lease = coordination.TurnLease("turn-1", "scope-1", "user-1", "token-1")
    await asyncio.wait_for(coordination.renew_until_done(lease, stop, ready=ready), 1)
    assert calls == 3
    assert ready.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["unavailable", "missing", "blocked"])
async def test_renew_failure_stops_at_confirmed_lease_deadline(
    monkeypatch, failure
) -> None:
    monkeypatch.setattr(settings.redis, "conversation_lock_ttl_ms", 60)
    monkeypatch.setattr(settings.redis, "conversation_lock_renew_ms", 15)
    monkeypatch.setattr(settings.redis, "socket_timeout_ms", 10)
    calls = 0

    async def renew(_lease):
        nonlocal calls
        calls += 1
        if calls == 1:
            return True
        if failure == "missing":
            return False
        if failure == "blocked":
            await asyncio.Event().wait()
        raise coordination.CoordinationError("持续超时")

    monkeypatch.setattr(coordination, "renew_turn", renew)
    lease = coordination.TurnLease("turn-1", "scope-1", "user-1", "token-1")
    with pytest.raises(coordination.TurnLeaseLost):
        await asyncio.wait_for(coordination.renew_until_done(lease, asyncio.Event()), 1)
    assert calls >= 2
