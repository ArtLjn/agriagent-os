"""Redis 并发协调层单元测试。"""

from __future__ import annotations

import pytest

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
