"""Redis 协调索引回收器。

Turn Hash 是状态事实来源；Set、List 和 Stream 是可重建索引，不能依赖它们
自行过期。清理器只删除已终态、已过期或找不到 Turn Hash 的索引成员。
"""

from __future__ import annotations

import asyncio
import logging
import time

from agent.config import settings
from agent.platforms.persistence.redis.coordination import user_scope_hash
from agent.platforms.persistence.redis.redis_store import get_client, key
from agent.platforms.persistence.redis.turn_store import (
    approval_key,
    get_turn,
    mark_timeout_if_active,
    publish_event,
)
from agent.platforms.persistence.redis import sse

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {
    "completed",
    "terminated",
    "failed",
    "rejected",
    "cancelled",
    "timeout",
}
_ACTIVE_STATUSES = {"accepted", "running", "awaiting_approval"}
_sweeper_task: asyncio.Task | None = None
_sweeper_stop: asyncio.Event | None = None


async def _scan(pattern: str) -> list[str]:
    client = get_client()
    if client is None:
        return []
    return [item async for item in client.scan_iter(match=pattern, count=200)]


def _age_seconds(state: dict[str, str]) -> float:
    try:
        return max(0.0, time.time() - float(state.get("updated_at", "0")))
    except (TypeError, ValueError):
        return float("inf")


async def _timeout_turn(turn_id: str, code: str) -> bool:
    if not await mark_timeout_if_active(turn_id, code):
        return False
    await publish_event(
        turn_id,
        {"type": "timeout", "data": {"code": code, "turn_id": turn_id}},
    )
    await publish_event(
        turn_id,
        {"type": "final_answer", "data": {"text": "本轮执行已超时，系统未确认业务操作是否完成。"}},
    )
    await publish_event(
        turn_id,
        sse.turn_terminated(
            turn_id,
            reason=code,
            message="本轮执行已超时，系统未确认业务操作是否完成。",
            step_count=0,
        ),
    )
    await publish_event(
        turn_id,
        {"type": "done", "data": {"status": "timeout", "turn_id": turn_id, "stop_reason": code}},
    )
    return True


async def _remove_turn_indexes(
    client,
    turn_id: str,
    state: dict[str, str] | None,
    *,
    remove_active: bool = True,
    remove_queue: bool = True,
) -> None:
    await client.srem(key("capacity", "queued_turns"), turn_id)
    await client.lrem(key("capacity", "queue"), 0, turn_id)
    if remove_active:
        await client.srem(key("capacity", "active_turns"), turn_id)
    if state:
        if remove_active:
            user_hash = user_scope_hash(
                state.get("user_id", ""), int(state.get("farm_id", "1"))
            )
            await client.srem(key("user", f"{user_hash}:active"), turn_id)
        if remove_queue and state.get("scope_hash"):
            await client.lrem(
                key("conversation", f"{state['scope_hash']}:queue"), 0, turn_id
            )


async def _cleanup_active_indexes() -> int:
    client = get_client()
    if client is None:
        return 0
    removed = 0
    active_key = key("capacity", "active_turns")
    turn_ids = await client.smembers(active_key)
    if not turn_ids:
        return 0
    async with client.pipeline(transaction=False) as pipe:
        for turn_id in turn_ids:
            pipe.hgetall(key("turn", turn_id))
        states = await pipe.execute()
    for turn_id, state in zip(turn_ids, states, strict=False):
        if isinstance(state, Exception):
            logger.warning(
                "sweeper turn read failed turn_id=%s error=%s",
                turn_id,
                type(state).__name__,
            )
            continue
        stale = state is None or state.get("status") in _TERMINAL_STATUSES
        if state and state.get("status") in _ACTIVE_STATUSES:
            lock_key = key("conversation", f"{state.get('scope_hash')}:lock")
            stale = not await client.exists(lock_key) and _age_seconds(state) > (
                settings.redis.conversation_lock_ttl_ms / 1000
            )
            if stale:
                await _timeout_turn(turn_id, "lease_expired")
        if stale:
            await _remove_turn_indexes(client, turn_id, state, remove_queue=False)
            removed += 1
    return removed


async def _cleanup_queue_ids(turn_ids: set[str]) -> int:
    client = get_client()
    if client is None:
        return 0
    removed = 0
    if not turn_ids:
        return 0
    async with client.pipeline(transaction=False) as pipe:
        for turn_id in turn_ids:
            pipe.hgetall(key("turn", turn_id))
        states = await pipe.execute()
    for turn_id, state in zip(turn_ids, states, strict=False):
        if isinstance(state, Exception):
            logger.warning(
                "sweeper queued turn read failed turn_id=%s error=%s",
                turn_id,
                type(state).__name__,
            )
            continue
        expired = (
            state
            and state.get("status") == "queued"
            and _age_seconds(state) > (settings.redis.queue_wait_timeout_seconds)
        )
        invalid = state is None or state.get("status") in _TERMINAL_STATUSES
        if expired:
            await _timeout_turn(turn_id, "queue_wait_timeout")
            state = await get_turn(turn_id)
            invalid = True
        if invalid or not state or state.get("status") != "queued":
            await _remove_turn_indexes(client, turn_id, state)
            removed += 1
    return removed


async def _cleanup_queue_indexes() -> int:
    client = get_client()
    if client is None:
        return 0
    ids = set(await client.smembers(key("capacity", "queued_turns")))
    ids.update(await client.lrange(key("capacity", "queue"), 0, -1))
    removed = await _cleanup_queue_ids(ids)
    for queue_key in await _scan(key("conversation", "*:queue")):
        conversation_ids = set(await client.lrange(queue_key, 0, -1))
        if not conversation_ids:
            continue
        async with client.pipeline(transaction=False) as pipe:
            for turn_id in conversation_ids:
                pipe.hgetall(key("turn", turn_id))
            states = await pipe.execute()
        for turn_id, state in zip(conversation_ids, states, strict=False):
            if isinstance(state, Exception):
                continue
            expired = (
                state
                and state.get("status") == "queued"
                and _age_seconds(state) > (settings.redis.queue_wait_timeout_seconds)
            )
            if expired:
                await _timeout_turn(turn_id, "queue_wait_timeout")
                state = await get_turn(turn_id)
            if not state or state.get("status") != "queued":
                await client.lrem(queue_key, 0, turn_id)
                await client.srem(key("capacity", "queued_turns"), turn_id)
                await client.lrem(key("capacity", "queue"), 0, turn_id)
                removed += 1
    return removed


async def _cleanup_user_indexes() -> int:
    """清理全局 active set 已不存在的用户索引和空用户 key。"""
    client = get_client()
    if client is None:
        return 0
    removed = 0
    global_active = key("capacity", "active_turns")
    for user_key in await _scan(key("user", "*:active")):
        turn_ids = await client.smembers(user_key)
        if not turn_ids:
            continue
        async with client.pipeline(transaction=False) as pipe:
            for turn_id in turn_ids:
                pipe.hgetall(key("turn", turn_id))
                pipe.sismember(global_active, turn_id)
            results = await pipe.execute()
        for offset, turn_id in enumerate(turn_ids):
            state = results[offset * 2]
            in_global_active = results[offset * 2 + 1]
            if isinstance(state, Exception) or isinstance(in_global_active, Exception):
                logger.warning(
                    "sweeper user index read failed turn_id=%s error=%s",
                    turn_id,
                    type(
                        state if isinstance(state, Exception) else in_global_active
                    ).__name__,
                )
                continue
            if (
                not state
                or state.get("status") in _TERMINAL_STATUSES
                or not in_global_active
            ):
                await client.srem(user_key, turn_id)
                removed += 1
    return removed


async def _cleanup_approval_indexes() -> int:
    client = get_client()
    if client is None:
        return 0
    removed = 0
    pending_key = key("approvals", "pending")
    for turn_id in await client.smembers(pending_key):
        approval = await client.hgetall(approval_key(turn_id))
        if approval.get("status") == "pending":
            continue
        state = await get_turn(turn_id)
        if state and state.get("status") not in _TERMINAL_STATUSES:
            await _timeout_turn(turn_id, "approval_expired")
        await client.srem(pending_key, turn_id)
        removed += 1
    return removed


async def sweep_once() -> dict[str, int]:
    """执行一轮索引回收，便于启动验收和定时任务复用。"""
    if get_client() is None:
        return {"active": 0, "queue": 0, "approval": 0}
    result = {
        "active": await _cleanup_active_indexes(),
        "queue": await _cleanup_queue_indexes(),
        "user": await _cleanup_user_indexes(),
        "approval": await _cleanup_approval_indexes(),
    }
    client = get_client()
    await client.xtrim(
        key("dispatch", settings.redis.dispatch_stream),
        maxlen=settings.redis.global_queue_limit,
        approximate=False,
    )
    await client.expire(
        key("dispatch", settings.redis.dispatch_stream),
        settings.redis.dispatch_stream_ttl_seconds,
    )
    logger.info("redis coordination sweep completed result=%s", result)
    return result


async def _run(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await sweep_once()
        except asyncio.CancelledError:
            return
        except Exception:  # noqa: BLE001
            logger.exception("redis coordination sweep failed")
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=max(settings.redis.cleanup_interval_seconds, 5)
            )
        except asyncio.TimeoutError:
            continue


async def start() -> None:
    global _sweeper_task, _sweeper_stop
    if _sweeper_task or get_client() is None:
        return
    _sweeper_stop = asyncio.Event()
    _sweeper_task = asyncio.create_task(_run(_sweeper_stop))
    logger.info(
        "redis coordination sweeper started interval_seconds=%d",
        settings.redis.cleanup_interval_seconds,
    )


async def stop() -> None:
    global _sweeper_task, _sweeper_stop
    if _sweeper_stop is not None:
        _sweeper_stop.set()
    if _sweeper_task is not None:
        _sweeper_task.cancel()
        try:
            await _sweeper_task
        except asyncio.CancelledError:
            pass
    _sweeper_task = None
    _sweeper_stop = None
