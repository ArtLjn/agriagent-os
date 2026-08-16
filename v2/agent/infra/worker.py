"""Redis dispatch worker for Agent turns."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from agent.config import settings
from agent.core.react import run_turn
from agent.core.turn import StopReason, Turn, TurnPhase
from agent.infra.chat_store import append_message
from agent.infra.coordination import (
    TurnLease,
    owns_turn_lease,
    promote_turn,
    release_turn,
    renew_until_done,
    wake_conversation,
    wake_global_queue,
)
from agent.infra.redis_store import get_client, key
from agent.infra.trace import (
    clear_trace,
    flush_now,
    init_trace,
    trace_turn_outcome,
)
from agent.infra.turn_store import (
    create_approval,
    dispatch_key,
    get_turn,
    mark_running,
    publish_event,
    update_turn,
    wait_approval,
)

logger = logging.getLogger(__name__)

_worker_tasks: list[asyncio.Task] = []
_worker_stop: asyncio.Event | None = None
_consumer_prefix = f"worker-{uuid.uuid4().hex[:10]}"


async def _ensure_group() -> None:
    client = get_client()
    if client is None:
        return
    try:
        await client.xgroup_create(
            dispatch_key(),
            settings.redis.dispatch_group,
            id="0-0",
            mkstream=True,
        )
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def _turn_from_state(state: dict[str, str]) -> Turn:
    return Turn(
        turn_id=state["turn_id"],
        conversation_id=state.get("conversation_id", "default"),
        memory_key=state.get("memory_key") or None,
        user_input=state.get("user_input", ""),
        user_id=state.get("user_id", ""),
        farm_uid=state.get("farm_uid", ""),
        farm_id=int(state.get("farm_id", "1")),
        role=state.get("role", "user"),
        token_id=state.get("token_id", ""),
        scope=state.get("scope", ""),
        agent_token=settings.auth.agent_service_token,
    )


async def _run_turn(turn: Turn, state: dict[str, str]) -> None:
    scope = state["scope_hash"]
    lease = TurnLease(
        turn_id=turn.turn_id,
        scope_hash=scope,
        user_scope_hash=__import__(
            "agent.infra.coordination", fromlist=["user_scope_hash"]
        ).user_scope_hash(turn.user_id, turn.farm_id),
        token=state["lease_token"],
    )
    current_state = await get_turn(turn.turn_id)
    if not current_state or current_state.get("status") in {
        "completed",
        "failed",
        "rejected",
        "cancelled",
        "timeout",
    }:
        return
    state = current_state
    owns_lease = await owns_turn_lease(lease)
    if state.get("queued") == "1" and state.get("status") in {"accepted", "queued"}:
        queue_entered_at = float(state.get("queue_entered_at") or time.time())
        if time.time() - queue_entered_at > settings.redis.queue_wait_timeout_seconds:
            await update_turn(
                turn.turn_id,
                status="timeout",
                error_code="queue_wait_timeout",
            )
            await publish_event(
                turn.turn_id,
                {
                    "type": "timeout",
                    "data": {"code": "queue_wait_timeout", "turn_id": turn.turn_id},
                },
            )
            return
        if not owns_lease and not await promote_turn(lease):
            await update_turn(turn.turn_id, status="queued")
            return
    elif not owns_lease:
        await update_turn(turn.turn_id, status="timeout", error_code="lease_expired")
        await publish_event(
            turn.turn_id,
            {
                "type": "timeout",
                "data": {"code": "lease_expired", "turn_id": turn.turn_id},
            },
        )
        return
    if not await mark_running(turn.turn_id):
        return

    renew_stop = asyncio.Event()
    renew_task = asyncio.create_task(renew_until_done(lease, renew_stop))
    final_answer = ""
    init_trace(
        conversation_id=turn.conversation_id,
        turn_id=turn.turn_id,
        user_id=turn.user_id,
        farm_uid=turn.farm_uid,
    )

    async def approval_waiter(turn_id: str) -> tuple[bool, str]:
        return await wait_approval(turn_id)

    try:
        async with asyncio.timeout(settings.redis.turn_execution_timeout_seconds):
            await update_turn(turn.turn_id, status="running")
            await publish_event(
                turn.turn_id,
                {
                    "type": "started",
                    "data": {"turn_id": turn.turn_id, "status": "running"},
                },
            )
            async for event in run_turn(turn, approval_waiter):
                latest = await get_turn(turn.turn_id)
                if latest and latest.get("status") == "cancelled":
                    turn.record_error(
                        "turn_cancelled",
                        "本轮任务已取消",
                        phase=turn.phase,
                        stop_reason=StopReason.USER_CANCELLED,
                        status="cancelled",
                    )
                    await publish_event(
                        turn.turn_id,
                        {
                            "type": "cancelled",
                            "data": {"code": "turn_cancelled", "turn_id": turn.turn_id},
                        },
                    )
                    break
                event_type = event.get("type", "")
                if event_type == "approval_required":
                    await create_approval(turn, event.get("data", {}))
                if event_type == "final_answer":
                    final_answer = event.get("data", {}).get("text", "")
                await publish_event(turn.turn_id, event)
        await update_turn(
            turn.turn_id,
            status=turn.status,
            phase=turn.phase.value,
            stop_reason=turn.stop_reason.value if turn.stop_reason else "",
            error_code=turn.error_code or "",
            error_message=turn.error_message or turn.error or "",
            error_details=turn.error_details,
            final_answer=final_answer,
        )
        if final_answer:
            await append_message(
                conversation_id=turn.conversation_id,
                role="assistant",
                content=final_answer,
                turn_id=turn.turn_id,
                user_id=turn.user_id,
                farm_id=turn.farm_id,
            )
    except TimeoutError:
        error_info = turn.record_error(
            "turn_timeout",
            "本轮执行超时",
            phase=turn.phase,
            stop_reason=StopReason.TURN_TIMEOUT,
            status="timeout",
        )
        timeout_answer = (
            "本轮执行超时，尚未确认请求是否完成，请稍后查看状态或重新发起。"
        )
        await update_turn(
            turn.turn_id,
            status="timeout",
            phase=turn.phase.value,
            stop_reason=turn.stop_reason.value,
            error_code=error_info["code"],
            error_message=error_info["message"],
            error_details=error_info,
            final_answer=timeout_answer,
        )
        await publish_event(
            turn.turn_id,
            {
                "type": "error",
                "data": error_info,
            },
        )
        await publish_event(
            turn.turn_id,
            {"type": "final_answer", "data": {"text": timeout_answer}},
        )
        await publish_event(
            turn.turn_id,
            {
                "type": "timeout",
                "data": {"code": "turn_timeout", "turn_id": turn.turn_id},
            },
        )
        await publish_event(
            turn.turn_id,
            {"type": "done", "data": {"status": "timeout", "turn_id": turn.turn_id}},
        )
    except Exception as exc:
        logger.exception("turn worker failed turn_id=%s", turn.turn_id)
        error_info = turn.record_error(
            "worker_failed",
            str(exc),
            phase=turn.phase or TurnPhase.SETUP,
            stop_reason=StopReason.PIPELINE_CRASH,
            status="failed",
        )
        failure_answer = "本轮执行失败，系统未能确认请求是否完成，请稍后重试。"
        await update_turn(
            turn.turn_id,
            status="failed",
            phase=turn.phase.value,
            stop_reason=turn.stop_reason.value,
            error_code=error_info["code"],
            error_message=error_info["message"],
            error_details=error_info,
            final_answer=failure_answer,
        )
        await publish_event(
            turn.turn_id,
            {"type": "error", "data": error_info},
        )
        await publish_event(
            turn.turn_id,
            {"type": "final_answer", "data": {"text": failure_answer}},
        )
        await publish_event(
            turn.turn_id,
            {"type": "done", "data": {"status": "failed", "turn_id": turn.turn_id}},
        )
    finally:
        renew_stop.set()
        await renew_task
        await release_turn(lease)
        await wake_conversation(scope)
        await wake_global_queue()
        trace_turn_outcome(turn.status, turn.error)
        await flush_now()
        clear_trace()


async def _worker_loop(stop: asyncio.Event, consumer: str) -> None:
    client = get_client()
    if client is None:
        return
    await _ensure_group()
    heartbeat_key = key("worker", consumer + ":heartbeat")
    reclaim_at = 0.0
    while not stop.is_set():
        try:
            await client.set(
                heartbeat_key,
                str(time.time()),
                ex=15,
            )
            if time.monotonic() >= reclaim_at:
                reclaim_at = time.monotonic() + 5
                reclaimed = await _reclaim_messages(client, consumer)
                await _process_messages(client, consumer, dispatch_key(), reclaimed)
            rows = await client.xreadgroup(
                settings.redis.dispatch_group,
                consumer,
                {dispatch_key(): ">"},
                count=1,
                block=1000,
            )
            if not rows:
                continue
            for stream, messages in rows:
                await _process_messages(client, consumer, stream, messages)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("agent dispatch worker loop failed")
            await asyncio.sleep(1)


async def _reclaim_messages(client, consumer: str) -> list[tuple[str, dict[str, str]]]:
    """兼容不同 Redis/redis-py：优先 XAUTOCLAIM，失败时回退。"""
    try:
        result = await client.xautoclaim(
            dispatch_key(),
            settings.redis.dispatch_group,
            consumer,
            min_idle_time=30_000,
            start_id="0-0",
            count=10,
        )
        if len(result) == 2:
            _, reclaimed = result
        elif len(result) == 3:
            _, reclaimed, _ = result
        else:
            raise RuntimeError(f"unexpected XAUTOCLAIM response length: {len(result)}")
        return reclaimed
    except Exception as exc:
        if (
            "unknown command" not in str(exc).lower()
            or "xautoclaim" not in str(exc).lower()
        ):
            raise
        pending = await client.xpending_range(
            dispatch_key(),
            settings.redis.dispatch_group,
            min="-",
            max="+",
            count=10,
        )
        ids = [
            item["message_id"]
            for item in pending
            if int(item.get("time_since_delivered", 0)) >= 30_000
        ]
        if not ids:
            return []
        return await client.xclaim(
            dispatch_key(),
            settings.redis.dispatch_group,
            consumer,
            min_idle_time=30_000,
            message_ids=ids,
        )


async def _process_messages(client, consumer, stream, messages) -> None:
    for message_id, fields in messages:
        turn_id = fields.get("turn_id")
        try:
            state = await get_turn(turn_id) if turn_id else None
            if state:
                await _run_turn(_turn_from_state(state), state)
        finally:
            await client.xack(stream, settings.redis.dispatch_group, message_id)


async def start() -> None:
    global _worker_tasks, _worker_stop
    if _worker_tasks:
        return
    _worker_stop = asyncio.Event()
    count = max(settings.redis.worker_count, 1)
    _worker_tasks = [
        asyncio.create_task(_worker_loop(_worker_stop, f"{_consumer_prefix}-{index}"))
        for index in range(count)
    ]
    logger.info("agent dispatch workers started count=%d", count)


async def stop() -> None:
    global _worker_tasks, _worker_stop
    if _worker_stop is not None:
        _worker_stop.set()
    for task in _worker_tasks:
        task.cancel()
    for task in _worker_tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass
    _worker_tasks = []
    _worker_stop = None
