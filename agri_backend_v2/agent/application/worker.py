"""Redis dispatch worker for Agent turns."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

from agent.config import settings
from agent.domains.harness.memory import service as memory
from agent.domains.harness.runtime.engine import run_turn
from agent.domains.harness.runtime.turn import StopReason, Turn, TurnPhase
from agent.platforms.persistence.mongo.chat_store import append_message
from agent.platforms.persistence.redis.coordination import (
    TurnLease,
    claim_recovered_lease,
    inspect_turn_lease,
    promote_turn,
    release_turn,
    renew_until_done,
    wake_conversation,
    wake_global_queue,
)
from agent.platforms.persistence.redis.redis_store import get_client, key
from agent.domains.harness.observability.trace import (
    clear_trace,
    flush_now,
    init_trace,
    trace_queue_wait,
    trace_turn_outcome,
)
from agent.domains.harness.observability.trace.context import trace_id_for_turn
from agent.platforms.persistence.redis.turn_store import (
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


def _state_int(value: object, fallback: int = 0) -> int:
    try:
        return int(value if value not in (None, "") else fallback)
    except (TypeError, ValueError):
        return fallback


def _state_bool(value: object) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes"}


async def _persist_session_state(turn: Turn) -> dict:
    """在 Mongo 可见消息落库后推进 Session state；失败不伪装成成功。"""
    result = await memory.persist_session_turn(
        conversation_id=turn.conversation_id,
        user_id=turn.user_id,
        farm_id=turn.farm_id,
        farm_uid=turn.farm_uid,
        expected_revision=turn.conversation_revision,
        turn_id=turn.turn_id,
        pending_action=turn.pending_approval,
        task_state=turn.task_state,
    )
    if result.get("status") not in {"disabled", "ready", "idempotent"}:
        logger.warning(
            "session state persistence incomplete turn_id=%s status=%s code=%s",
            turn.turn_id,
            result.get("status"),
            result.get("code"),
        )
    if result.get("status") in {"ready", "idempotent"}:
        turn.conversation_revision = _state_int(
            result.get("conversation_revision"), turn.conversation_revision
        )
        turn.summary_revision = _state_int(
            result.get("summary_revision"), turn.summary_revision
        )
        turn.reset_generation = _state_int(
            result.get("reset_generation"), turn.reset_generation
        )
        turn.context_source_status = str(
            result.get("source_status") or turn.context_source_status or "empty"
        )
        await update_turn(
            turn.turn_id,
            conversation_revision=turn.conversation_revision,
            summary_revision=turn.summary_revision,
            reset_generation=turn.reset_generation,
            source_status=turn.context_source_status,
            context_source_status=turn.context_source_status,
        )
    return result


async def _persist_observation(turn: Turn, *, assistant_answer: str) -> dict:
    """消息和 Session state 成功后提交一次受控 observation 事件。"""
    result = await memory.observe(
        user_id=turn.user_id,
        farm_id=turn.farm_id,
        conversation_id=turn.conversation_id,
        turn_id=turn.turn_id,
        user_input=turn.user_input,
        assistant_answer=assistant_answer,
        conversation_revision=turn.conversation_revision,
        idempotency_key=f"turn:{turn.turn_id}:memory-observation",
        metadata={
            "turn_status": turn.status,
            "stop_reason": turn.stop_reason.value if turn.stop_reason else None,
            "error_code": turn.error_code,
        },
    )
    if not result.get("persisted"):
        logger.warning(
            "memory observation persistence incomplete turn_id=%s status=%s code=%s",
            turn.turn_id,
            result.get("status"),
            result.get("code"),
        )
    return result


async def _persist_visible_assistant_message(
    turn: Turn,
    *,
    content: str,
    message_kind: str,
    trace_id: str,
) -> bool:
    """先保证 assistant 事实消息幂等落库，再推进 Session 与 observation。"""
    message_id = await append_message(
        conversation_id=turn.conversation_id,
        role="assistant",
        content=content,
        turn_id=turn.turn_id,
        trace_id=trace_id,
        message_kind=message_kind,
        user_id=turn.user_id,
        farm_id=turn.farm_id,
        idempotency_key=f"turn:{turn.turn_id}:assistant:{message_kind}",
    )
    if not message_id:
        await update_turn(
            turn.turn_id,
            message_persistence_status="unavailable",
            error_code="conversation_message_persist_failed",
        )
        logger.error(
            "assistant message persistence failed; session state not advanced turn_id=%s",
            turn.turn_id,
        )
        return False
    await _persist_session_state(turn)
    await _persist_observation(turn, assistant_answer=content)
    return True


async def _finish_assistant_persistence(
    turn: Turn,
    *,
    content: str,
    message_kind: str,
    trace_id: str,
) -> bool:
    """完成 assistant 事实、Session state 和 observation 后清除收尾标记。"""
    persisted = await _persist_visible_assistant_message(
        turn,
        content=content,
        message_kind=message_kind,
        trace_id=trace_id,
    )
    if persisted:
        await update_turn(turn.turn_id, finalization_pending=False)
    return persisted


async def _recover_pending_finalization(state: dict[str, str]) -> bool:
    """只恢复终态 Turn 的可见消息收尾，不重新进入 Runtime。"""
    content = state.get("final_answer", "")
    if not content:
        await update_turn(state["turn_id"], finalization_pending=False)
        return True
    turn = _turn_from_state(state)
    turn.status = state.get("status", turn.status)
    return await _finish_assistant_persistence(
        turn,
        content=content,
        message_kind="error_answer" if state.get("status") != "completed" else "final_answer",
        trace_id=state.get("trace_id") or trace_id_for_turn(turn.turn_id),
    )


async def _recover_interrupted_turn(turn: Turn, state: dict[str, str]) -> None:
    """Worker 丢失 lease 后只收口，不重新执行可能已提交的 Tool。"""
    error_info = turn.record_error(
        "worker_restarted",
        "执行 Worker 已中断，本轮未自动重试业务操作。",
        phase=TurnPhase.TERMINAL,
        stop_reason=StopReason.PIPELINE_CRASH,
        status="timeout",
    )
    turn.pending_approval = None
    answer = "本轮执行被 Worker 中断，系统未自动重复执行操作，请确认当前业务状态后重试。"
    trace_id = state.get("trace_id") or trace_id_for_turn(turn.turn_id)
    await update_turn(
        turn.turn_id,
        status="timeout",
        phase=turn.phase.value,
        stop_reason=turn.stop_reason.value,
        error_code=error_info["code"],
        error_message=error_info["message"],
        error_details=error_info,
        final_answer=answer,
        finalization_pending=True,
        pending_approval=None,
    )
    await publish_event(turn.turn_id, {"type": "error", "data": error_info})
    await publish_event(
        turn.turn_id,
        {"type": "final_answer", "data": {"text": answer}},
    )
    await publish_event(
        turn.turn_id,
        {"type": "done", "data": {"status": "timeout", "turn_id": turn.turn_id}},
    )
    await _finish_assistant_persistence(
        turn,
        content=answer,
        message_kind="error_answer",
        trace_id=trace_id,
    )


async def _prepare_execution_lease(
    turn: Turn, state: dict[str, str], lease: TurnLease
) -> bool:
    """按 Turn 状态选择排队提升、首次恢复、并发跳过或中断收口。"""
    lease_state = await inspect_turn_lease(lease)
    status = state.get("status", "")
    if lease_state == "held":
        return False
    if lease_state == "owned":
        return True
    if status in {"accepted", "queued"}:
        if status == "queued":
            return await promote_turn(lease)
        return await claim_recovered_lease(lease)
    await _recover_interrupted_turn(turn, state)
    return False


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
        task_state=_decode_json_field(state.get("task_state")),
        pending_approval=_decode_json_field(state.get("pending_approval")),
        final_answer=state.get("final_answer") or None,
        finalization_pending=_state_bool(state.get("finalization_pending")),
        conversation_revision=_state_int(state.get("conversation_revision")),
        summary_revision=_state_int(state.get("summary_revision")),
        reset_generation=_state_int(state.get("reset_generation")),
        context_source_status=str(
            state.get("source_status")
            or state.get("context_source_status")
            or "empty"
        ),
    )


def _decode_json_field(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


async def _run_turn(turn: Turn, state: dict[str, str]) -> None:
    scope = state["scope_hash"]
    lease = TurnLease(
        turn_id=turn.turn_id,
        scope_hash=scope,
        user_scope_hash=__import__(
            "agent.platforms.persistence.redis.coordination", fromlist=["user_scope_hash"]
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
    queue_wait_ms: int | None = None
    if state.get("queued") == "1" and state.get("status") in {"accepted", "queued"}:
        queue_entered_at = float(state.get("queue_entered_at") or time.time())
        queue_wait_ms = max(0, int((time.time() - queue_entered_at) * 1000))
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
    if not await _prepare_execution_lease(turn, state, lease):
        return
    if not await mark_running(turn.turn_id):
        return

    renew_stop = asyncio.Event()
    renew_task = asyncio.create_task(renew_until_done(lease, renew_stop))
    final_answer = ""
    init_trace(
        conversation_id=turn.conversation_id,
        turn_id=turn.turn_id,
        trace_id=state.get("trace_id", ""),
        request_id=state.get("request_id", ""),
        user_id=turn.user_id,
        farm_uid=turn.farm_uid,
    )
    if queue_wait_ms is not None:
        trace_queue_wait(queue_wait_ms)
    trace_id = state.get("trace_id") or trace_id_for_turn(turn.turn_id)
    # Session View 在 application/Worker 边界读取一次，Runtime 只消费不可变快照。
    try:
        turn.memory_snapshot = await memory.get_session_view(
            turn.conversation_id,
            user_id=turn.user_id,
            farm_id=turn.farm_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("session view preload failed turn_id=%s: %s", turn.turn_id, exc)
        turn.memory_snapshot = memory.empty_session_view(
            turn.conversation_id,
            user_id=turn.user_id,
            farm_id=turn.farm_id,
            source_status="unavailable",
        )
    turn.conversation_revision = _state_int(
        turn.memory_snapshot.get("conversation_revision")
    )
    turn.summary_revision = _state_int(turn.memory_snapshot.get("summary_revision"))
    turn.reset_generation = _state_int(turn.memory_snapshot.get("reset_generation"))
    turn.context_source_status = str(
        turn.memory_snapshot.get("source_status")
        or turn.memory_snapshot.get("context_source_status")
        or "empty"
    )
    await update_turn(
        turn.turn_id,
        conversation_revision=turn.conversation_revision,
        summary_revision=turn.summary_revision,
        reset_generation=turn.reset_generation,
        source_status=turn.context_source_status,
        context_source_status=turn.context_source_status,
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
                    await _persist_session_state(turn)
                if event_type == "final_answer":
                    final_answer = event.get("data", {}).get("text", "")
                if event_type == "done" and final_answer:
                    await update_turn(
                        turn.turn_id,
                        final_answer=final_answer,
                        finalization_pending=True,
                    )
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
            finalization_pending=bool(final_answer),
        )
        if final_answer:
            await _finish_assistant_persistence(
                turn,
                content=final_answer,
                message_kind="final_answer",
                trace_id=trace_id,
            )
        elif turn.status == "cancelled":
            turn.pending_approval = None
            await _persist_session_state(turn)
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
            finalization_pending=True,
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
        await _finish_assistant_persistence(
            turn,
            content=timeout_answer,
            message_kind="error_answer",
            trace_id=trace_id,
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
            finalization_pending=True,
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
        await _finish_assistant_persistence(
            turn,
            content=failure_answer,
            message_kind="error_answer",
            trace_id=trace_id,
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
        acknowledge = True
        try:
            state = await get_turn(turn_id) if turn_id else None
            if state:
                if _state_bool(state.get("finalization_pending")):
                    await _recover_pending_finalization(state)
                else:
                    await _run_turn(_turn_from_state(state), state)
                latest = await get_turn(turn_id)
                acknowledge = not (
                    latest and _state_bool(latest.get("finalization_pending"))
                )
        except Exception:
            acknowledge = False
            logger.exception(
                "agent turn processing failed; leave message pending "
                "turn_id=%s consumer=%s",
                turn_id,
                consumer,
            )
        finally:
            if acknowledge:
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
