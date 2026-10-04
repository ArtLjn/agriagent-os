"""Redis-backed turn state, idempotency, approvals and replayable events."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any

from agent.config import settings
from agent.domains.harness.runtime.turn import Turn
from agent.domains.harness.runtime.events import DomainEvent
from agent.platforms.persistence.redis.redis_store import get_client, key
from agent.domains.harness.observability.trace.collector import record_event
from agent.domains.harness.observability.trace.context import (
    current_span_id,
    get_trace,
    trace_id_for_turn,
)

logger = logging.getLogger(__name__)

# timeout/cancelled 是过程结果事件，允许随后发布唯一的 done 终态事件。
_TERMINAL_EVENTS = {"done"}
TERMINAL_STATUSES = frozenset(
    {"completed", "terminated", "failed", "rejected", "cancelled", "timeout"}
)
_OUTCOME_FIELDS = frozenset(
    {
        "status",
        "phase",
        "stop_reason",
        "error_code",
        "error_message",
        "error_details",
        "final_answer",
        "pending_approval",
    }
)

_UPDATE_TURN_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 0 then return 0 end
local fields = cjson.decode(ARGV[1])
local current = redis.call('HGET', KEYS[1], 'status')
local expected = cjson.decode(ARGV[5])
if #expected > 0 then
  local matches = false
  for _, status in ipairs(expected) do
    if current == status then matches = true end
  end
  if not matches then return 0 end
end
for _, status in ipairs(cjson.decode(ARGV[2])) do
  if current == status and fields.status and fields.status ~= current then
    return 0
  end
end
if redis.call('HEXISTS', KEYS[1], 'terminal_event') == 1 then
  for _, name in ipairs(cjson.decode(ARGV[3])) do
    if fields[name] ~= nil then return 0 end
  end
end
for name, value in pairs(fields) do redis.call('HSET', KEYS[1], name, value) end
redis.call('HINCRBY', KEYS[1], 'version', 1)
redis.call('EXPIRE', KEYS[1], ARGV[4])
return 1
"""

_PUBLISH_EVENT_SCRIPT = """
local last_seq = tonumber(redis.call('HGET', KEYS[1], 'last_event_seq') or '0')
if redis.call('EXISTS', KEYS[1]) == 0 or
   redis.call('HEXISTS', KEYS[1], 'terminal_event') == 1 then
  return {0, last_seq}
end
local fields = cjson.decode(ARGV[2])
local seq = redis.call('INCR', KEYS[3])
fields.seq = tostring(seq)
local args = {'MAXLEN', ARGV[3], '*'}
for name, value in pairs(fields) do
  table.insert(args, name)
  table.insert(args, value)
end
redis.call('XADD', KEYS[2], unpack(args))
redis.call('HSET', KEYS[1], 'last_event_seq', seq, 'updated_at', ARGV[5])
if fields.terminal == '1' then
  redis.call('HSET', KEYS[1], 'terminal_event', ARGV[1])
end
redis.call('HINCRBY', KEYS[1], 'version', 1)
for _, key in ipairs(KEYS) do redis.call('EXPIRE', key, ARGV[4]) end
return {1, seq}
"""
_EVENT_STATUS_AFTER = {
    "queued": "queued",
    "accepted": "accepted",
    "started": "running",
    "approval_required": "awaiting_approval",
    "approval_result": "running",
    "cancelled": "cancelled",
    "timeout": "timeout",
    "turn.completed": "completed",
    "turn.terminated": "terminated",
    "turn.failed": "failed",
    "step.started": "running",
    "step.completed": "running",
    "tool.failed": "failed",
    "error": "failed",
}


def _int_value(value: Any, fallback: int = 0) -> int:
    try:
        return int(value if value not in (None, "") else fallback)
    except (TypeError, ValueError):
        return fallback


def turn_key(turn_id: str) -> str:
    return key("turn", turn_id)


def event_key(turn_id: str) -> str:
    return key("events", turn_id)


def approval_key(turn_id: str) -> str:
    return key("approval", turn_id)


def idempotency_key(scope_hash: str, request_id: str) -> str:
    digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
    return key("idempotency", f"{scope_hash}:{digest}")


def dispatch_key() -> str:
    return key("dispatch", settings.redis.dispatch_stream)


async def claim_idempotency(
    *,
    scope_hash: str,
    client_request_id: str,
    request_fingerprint: str,
    turn_id: str,
) -> tuple[bool, dict[str, Any] | None]:
    """Atomically claim a client request id or return its previous claim."""
    client = get_client()
    if client is None:
        raise RuntimeError("redis coordination is disabled")
    payload = json.dumps(
        {"turn_id": turn_id, "request_fingerprint": request_fingerprint},
        ensure_ascii=False,
    )
    redis_key = idempotency_key(scope_hash, client_request_id)
    claimed = await client.set(
        redis_key,
        payload,
        nx=True,
        ex=settings.redis.idempotency_ttl_seconds,
    )
    if claimed:
        return True, None
    existing = await client.get(redis_key)
    return False, json.loads(existing) if existing else None


async def release_idempotency(scope_hash: str, client_request_id: str) -> None:
    client = get_client()
    if client is not None:
        await client.delete(idempotency_key(scope_hash, client_request_id))


async def save_turn(
    turn: Turn,
    *,
    scope_hash: str,
    lease_token: str,
    queued: bool = False,
    queue_kind: str = "",
    trace_id: str = "",
    client_request_id: str = "",
) -> None:
    client = get_client()
    if client is None:
        raise RuntimeError("redis coordination is disabled")
    stable_trace_id = trace_id or trace_id_for_turn(turn.turn_id)
    await client.hset(
        turn_key(turn.turn_id),
        mapping={
            "turn_id": turn.turn_id,
            "user_id": turn.user_id,
            "farm_uid": turn.farm_uid,
            "farm_id": str(turn.farm_id),
            "role": turn.role,
            "token_id": turn.token_id,
            "scope": turn.scope,
            "conversation_id": turn.conversation_id,
            "conversation_revision": str(turn.conversation_revision),
            "summary_revision": str(turn.summary_revision),
            "reset_generation": str(turn.reset_generation),
            "source_status": turn.context_source_status,
            "context_source_status": turn.context_source_status,
            "trace_id": stable_trace_id,
            # request_id 只是兼容别名；幂等使用独立的 client_request_id，不能使用 Trace 主键。
            "request_id": stable_trace_id,
            "client_request_id": client_request_id,
            "memory_key": turn.memory_key or "",
            "user_input": turn.user_input,
            "scope_hash": scope_hash,
            "lease_token": lease_token,
            "status": "queued" if queued else "accepted",
            "queued": "1" if queued else "0",
            "queue_kind": queue_kind,
            "queue_entered_at": str(time.time()) if queued else "",
            "version": "1",
            "created_at": str(time.time()),
            "updated_at": str(time.time()),
        },
    )
    await client.expire(turn_key(turn.turn_id), settings.redis.turn_state_ttl_seconds)


async def get_turn(turn_id: str) -> dict[str, str] | None:
    client = get_client()
    if client is None:
        return None
    data = await client.hgetall(turn_key(turn_id))
    return data or None


def legacy_status_fields(turn: dict[str, str]) -> dict[str, str]:
    """为旧客户端提供 failed + error_code 兼容字段，不改变新状态事实。"""
    if turn.get("status") != "terminated":
        return turn
    reason = str(turn.get("stop_reason") or turn.get("error_code") or "terminated")
    turn.setdefault("legacy_status", "failed")
    turn.setdefault("legacy_error_code", reason)
    return turn


async def update_turn(
    turn_id: str, *, expected_statuses: tuple[str, ...] = (), **fields: Any
) -> bool:
    """原子推进状态，保留既有终态；done 后只允许持久化元数据收尾。"""
    client = get_client()
    if client is None:
        return False
    normalized = {
        name: value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False)
        if isinstance(value, (dict, list))
        else str(value)
        for name, value in fields.items()
    }
    normalized["updated_at"] = str(time.time())
    return bool(
        await client.eval(
            _UPDATE_TURN_SCRIPT,
            1,
            turn_key(turn_id),
            json.dumps(normalized, ensure_ascii=False),
            json.dumps(sorted(TERMINAL_STATUSES)),
            json.dumps(sorted(_OUTCOME_FIELDS)),
            settings.redis.turn_state_ttl_seconds,
            json.dumps(expected_statuses),
        )
    )


async def mark_timeout_if_active(turn_id: str, error_code: str) -> bool:
    """CAS 标记仍处于活动态的 turn，避免清理器覆盖并发完成结果。"""
    client = get_client()
    if client is None:
        return False
    result = await client.eval(
        """
        local status = redis.call('HGET', KEYS[1], 'status')
        if status ~= 'accepted' and status ~= 'queued' and
           status ~= 'running' and status ~= 'awaiting_approval' then
          return 0
        end
        redis.call('HSET', KEYS[1], 'status', 'timeout',
          'error_code', ARGV[1], 'updated_at', ARGV[2])
        redis.call('HINCRBY', KEYS[1], 'version', 1)
        redis.call('EXPIRE', KEYS[1], ARGV[3])
        return 1
        """,
        1,
        turn_key(turn_id),
        error_code,
        str(time.time()),
        str(settings.redis.turn_state_ttl_seconds),
    )
    return bool(result)


async def mark_running(turn_id: str) -> bool:
    """Claim a turn exactly once after its conversation lease is active."""
    client = get_client()
    if client is None:
        return False
    result = await client.eval(
        """
        local status = redis.call('HGET', KEYS[1], 'status')
        if status ~= 'accepted' and status ~= 'queued' then return 0 end
        redis.call('HSET', KEYS[1], 'status', 'running', 'worker_id', ARGV[1])
        redis.call('HINCRBY', KEYS[1], 'version', 1)
        return 1
        """,
        1,
        turn_key(turn_id),
        str(__import__("uuid").uuid4().hex),
    )
    return bool(result)


async def dispatch_turn(turn_id: str) -> str:
    client = get_client()
    if client is None:
        raise RuntimeError("redis coordination is disabled")
    message_id = await client.xadd(
        dispatch_key(),
        {"turn_id": turn_id, "created_at": str(time.time())},
        maxlen=settings.redis.global_queue_limit,
        approximate=False,
    )
    await client.expire(dispatch_key(), settings.redis.dispatch_stream_ttl_seconds)
    return message_id


async def publish_event(turn_id: str, event: DomainEvent | dict[str, Any]) -> int:
    client = get_client()
    if client is None:
        raise RuntimeError("redis coordination is disabled")
    event_type = event.get("type", "")
    data = event.get("data", {})
    seq_key = key("event-seq", turn_id)
    terminal = event_type in _TERMINAL_EVENTS
    state = await client.hgetall(turn_key(turn_id))
    trace_id = str(
        event.get("trace_id") or state.get("trace_id") or trace_id_for_turn(turn_id)
    )
    request_id = str(event.get("request_id") or state.get("request_id") or trace_id)
    conversation_id = str(
        event.get("conversation_id")
        or data.get("conversation_id")
        or state.get("conversation_id")
        or ""
    )
    phase = str(event.get("phase") or data.get("phase") or state.get("phase") or "")
    raw_step = (
        event.get("step_index")
        or event.get("step")
        or data.get("step_index")
        or data.get("step")
        or state.get("step_index")
        or 0
    )
    try:
        step = int(raw_step)
    except (TypeError, ValueError):
        step = 0
    status_before = str(
        event.get("status_before")
        or data.get("status_before")
        or state.get("status")
        or ""
    )
    status_after = str(
        event.get("status_after")
        or data.get("status_after")
        or data.get("status")
        or _EVENT_STATUS_AFTER.get(event_type, status_before)
    )
    conversation_revision = _int_value(
        event.get("conversation_revision")
        or data.get("conversation_revision")
        or state.get("conversation_revision")
    )
    summary_revision = _int_value(
        event.get("summary_revision")
        or data.get("summary_revision")
        or state.get("summary_revision")
    )
    reset_generation = _int_value(
        event.get("reset_generation")
        or data.get("reset_generation")
        or state.get("reset_generation")
    )
    source_status = str(
        event.get("source_status")
        or data.get("source_status")
        or state.get("source_status")
        or state.get("context_source_status")
        or "empty"
    )
    data = {
        **data,
        "conversation_revision": conversation_revision,
        "summary_revision": summary_revision,
        "reset_generation": reset_generation,
        "source_status": source_status,
        "context_source_status": source_status,
    }
    occurred_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    event_id = str(event.get("event_id") or f"evt_{uuid.uuid4().hex}")
    trace_context = get_trace()
    span_id = str(
        event.get("span_id")
        or current_span_id()
        or (trace_context.root_span_id if trace_context else "")
        or ""
    )
    envelope = {
        "event_id": event_id,
        "trace_id": trace_id,
        "request_id": request_id,
        "user_id": state.get("user_id", ""),
        "farm_uid": state.get("farm_uid", ""),
        "farm_id": state.get("farm_id", ""),
        "turn_id": turn_id,
        "conversation_id": conversation_id,
        "span_id": span_id,
        "parent_span_id": event.get("parent_span_id"),
        "type": event_type,
        "event_type": event_type,
        "data": data,
        "occurred_at": occurred_at,
        "phase": phase,
        "step": step,
        "step_index": step,
        "terminal": terminal,
        "status_before": status_before,
        "status_after": status_after,
        "conversation_revision": conversation_revision,
        "summary_revision": summary_revision,
        "reset_generation": reset_generation,
        "source_status": source_status,
        "context_source_status": source_status,
    }
    fields = {
        "event_id": event_id,
        "trace_id": trace_id,
        "request_id": request_id,
        "user_id": state.get("user_id", ""),
        "farm_uid": state.get("farm_uid", ""),
        "farm_id": state.get("farm_id", ""),
        "turn_id": turn_id,
        "conversation_id": conversation_id,
        "span_id": span_id,
        "parent_span_id": str(event.get("parent_span_id") or ""),
        "type": event_type,
        "event_type": event_type,
        "data": json.dumps(data, ensure_ascii=False),
        "occurred_at": occurred_at,
        "phase": phase,
        "step": str(step),
        "step_index": str(step),
        "terminal": "1" if terminal else "0",
        "status_before": status_before,
        "status_after": status_after,
        "conversation_revision": str(conversation_revision),
        "summary_revision": str(summary_revision),
        "reset_generation": str(reset_generation),
        "source_status": source_status,
        "context_source_status": source_status,
    }
    # 序号分配、追加事件和 done 栅栏必须在同一原子操作内，关闭后不再接受任何事件。
    accepted, seq = await client.eval(
        _PUBLISH_EVENT_SCRIPT,
        3,
        turn_key(turn_id),
        event_key(turn_id),
        seq_key,
        event_type,
        json.dumps(fields, ensure_ascii=False),
        settings.redis.event_stream_maxlen,
        settings.redis.turn_state_ttl_seconds,
        str(time.time()),
    )
    seq = int(seq)
    if not accepted:
        return seq
    envelope["seq"] = seq
    try:
        # 收集器交接是同步且有界的；SSE 热路径不等待 Mongo 持久化。
        record_event(envelope)
    except Exception:  # noqa: BLE001
        logger.debug(
            "sse trace event handoff failed turn_id=%s", turn_id, exc_info=True
        )
    return seq


class RedisEventPublisher:
    """Runtime 领域事件到 Redis Event Stream 的适配器。"""

    async def publish(self, turn_id: str, event: DomainEvent) -> int:
        return await publish_event(turn_id, event)


async def read_events(turn_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
    client = get_client()
    if client is None:
        return []
    state = await client.hgetall(turn_key(turn_id))
    rows = await client.xrange(event_key(turn_id), min="-", max="+")
    events: list[dict[str, Any]] = []
    for stream_id, fields in rows:
        seq = int(fields.get("seq", "0"))
        if seq <= after_seq:
            continue
        events.append(
            {
                "seq": seq,
                "event_id": fields.get(
                    "event_id", f"evt_legacy_{str(stream_id).replace('-', '_')}"
                ),
                "trace_id": fields.get(
                    "trace_id", state.get("trace_id") or trace_id_for_turn(turn_id)
                ),
                "request_id": fields.get(
                    "request_id", state.get("request_id") or state.get("trace_id", "")
                ),
                "turn_id": fields.get("turn_id", turn_id),
                "conversation_id": fields.get(
                    "conversation_id", state.get("conversation_id", "")
                ),
                "span_id": fields.get("span_id") or state.get("span_id", ""),
                "parent_span_id": fields.get("parent_span_id") or None,
                "type": fields.get("type", ""),
                "event_type": fields.get("event_type", fields.get("type", "")),
                "data": json.loads(fields.get("data", "{}")),
                "occurred_at": fields.get("occurred_at", ""),
                "phase": fields.get("phase", ""),
                "step": int(fields.get("step", fields.get("step_index", "0")) or 0),
                "step_index": int(
                    fields.get("step_index", fields.get("step", "0")) or 0
                ),
                "terminal": fields.get("terminal") == "1",
                "status_before": fields.get("status_before", ""),
                "status_after": fields.get("status_after", ""),
                "conversation_revision": _int_value(
                    fields.get(
                        "conversation_revision", state.get("conversation_revision", "0")
                    )
                ),
                "summary_revision": _int_value(
                    fields.get("summary_revision", state.get("summary_revision", "0"))
                ),
                "reset_generation": _int_value(
                    fields.get("reset_generation", state.get("reset_generation", "0"))
                ),
                "source_status": fields.get(
                    "source_status",
                    state.get("source_status")
                    or state.get("context_source_status")
                    or "empty",
                ),
                "context_source_status": fields.get(
                    "context_source_status",
                    fields.get(
                        "source_status",
                        state.get("source_status")
                        or state.get("context_source_status")
                        or "empty",
                    ),
                ),
            }
        )
    return events


async def resolve_event_seq(turn_id: str, event_id: str) -> int | None:
    """将 SSE Last-Event-ID 映射为 Turn 内的 seq，供断线恢复复用。"""
    if not event_id:
        return None
    events = await read_events(turn_id)
    for event in events:
        if event.get("event_id") == event_id:
            return int(event["seq"])
    # 事件可能已因 Stream 保留窗口淘汰；返回 None 让调用方安全回放保留窗口。
    return None


async def stream_events(
    turn_id: str,
    *,
    after_seq: int = 0,
    poll_interval: float = 0.25,
    max_wait_seconds: float = 900,
) -> AsyncIterator[dict[str, Any]]:
    """Replay existing events, then poll until a terminal event arrives."""
    deadline = time.monotonic() + max_wait_seconds
    next_seq = after_seq
    while time.monotonic() < deadline:
        events = await read_events(turn_id, next_seq)
        if events:
            for event in events:
                next_seq = max(next_seq, event["seq"])
                yield event
                if event["terminal"]:
                    return
            continue
        state = await get_turn(turn_id)
        if state and state.get("status") in {
            "completed",
            "terminated",
            "failed",
            "rejected",
            "cancelled",
            "timeout",
        }:
            # 取消/回收可能已先写入终态，但 Worker 仍需要发布用户答复和
            # semantic terminal；此时不能提前合成 done 截断后续事件。
            if str(state.get("finalization_pending", "")).lower() in {
                "1",
                "true",
                "yes",
            }:
                await asyncio.sleep(poll_interval)
                continue
            done_event = {
                "type": "done",
                "data": {
                    "status": state["status"],
                    "turn_id": turn_id,
                    **(
                        {"stop_reason": state["stop_reason"]}
                        if state.get("stop_reason")
                        else {}
                    ),
                    **(
                        {"step_count": _int_value(state.get("step_count"))}
                        if state.get("step_count") is not None
                        else {}
                    ),
                },
            }
            # Worker 崩溃或旧数据可能只留下终态状态，没有写入 done。
            # 将补发终态持久化，保证下一次 after_seq 重连不会再次合成同一事件。
            client = get_client()
            if client is not None:
                published_seq = await publish_event(turn_id, done_event)
                replayed = await read_events(turn_id, next_seq)
                for event in replayed:
                    next_seq = max(next_seq, event["seq"])
                    yield event
                    if event["terminal"]:
                        return
                if published_seq > next_seq:
                    yield _synthetic_event(
                        turn_id,
                        seq=published_seq,
                        event_type="done",
                        data=done_event["data"],
                        state=state,
                        event_id=f"evt_done_{turn_id}",
                    )
                return
            yield _synthetic_event(
                turn_id,
                seq=max(next_seq, int(state.get("last_event_seq", "0") or 0)) + 1,
                event_type="done",
                data=done_event["data"],
                state=state,
                event_id=f"evt_done_{turn_id}",
            )
            return
        await asyncio.sleep(poll_interval)
    yield _synthetic_event(
        turn_id,
        seq=next_seq,
        event_type="stream_timeout",
        data={
            "code": "stream_timeout",
            "message": "事件流等待超时，Turn 仍未发布终态。",
            "turn_id": turn_id,
        },
        event_id=f"evt_stream_timeout_{turn_id}_{next_seq}",
    )


def _synthetic_event(
    turn_id: str,
    *,
    seq: int,
    event_type: str,
    data: dict[str, Any],
    state: dict[str, str] | None = None,
    event_id: str,
) -> dict[str, Any]:
    """为旧 Turn 状态或流等待超时生成明确的、非持久化事件 envelope。"""
    state = state or {}
    trace_id = state.get("trace_id") or trace_id_for_turn(turn_id)
    occurred_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    step = int(state.get("step_index", "0") or 0)
    return {
        "seq": seq,
        "event_id": event_id,
        "trace_id": trace_id,
        "request_id": state.get("request_id") or trace_id,
        "turn_id": turn_id,
        "conversation_id": state.get("conversation_id", ""),
        "type": event_type,
        "event_type": event_type,
        "data": data,
        "occurred_at": occurred_at,
        "phase": state.get("phase", ""),
        "step": step,
        "step_index": step,
        "terminal": event_type == "done",
        "status_before": state.get("status", ""),
        "status_after": str(
            data.get("status")
            if isinstance(data, dict) and data.get("status")
            else _EVENT_STATUS_AFTER.get(event_type, state.get("status", ""))
        ),
    }


async def create_approval(turn: Turn, event_data: dict[str, Any]) -> None:
    client = get_client()
    if client is None:
        raise RuntimeError("redis coordination is disabled")
    pending_action = dict(event_data)
    pending_action.setdefault("status", "pending")
    pending_action.setdefault("source_turn_id", turn.turn_id)
    pending_action.setdefault(
        "created_at",
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    )
    pending_action.setdefault(
        "expires_at",
        (
            datetime.now(timezone.utc)
            + timedelta(seconds=settings.redis.approval_ttl_seconds)
        )
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    )
    turn.pending_approval = pending_action
    await client.hset(
        approval_key(turn.turn_id),
        mapping={
            "turn_id": turn.turn_id,
            "tool_name": pending_action.get("tool_name", ""),
            "risk_level": pending_action.get("risk_level", ""),
            "arguments": json.dumps(
                pending_action.get("arguments", {}), ensure_ascii=False
            ),
            "status": "pending",
            "created_at": str(time.time()),
        },
    )
    await client.expire(approval_key(turn.turn_id), settings.redis.approval_ttl_seconds)
    await client.sadd(key("approvals", "pending"), turn.turn_id)
    await update_turn(
        turn.turn_id,
        status="awaiting_approval",
        pending_approval=pending_action,
    )


_RESOLVE_APPROVAL = """
if redis.call('HGET', KEYS[1], 'status') ~= 'pending' then
  return 0
end
redis.call('HSET', KEYS[1], 'status', ARGV[1], 'reason', ARGV[2], 'resolved_at', ARGV[3])
redis.call('SREM', KEYS[2], ARGV[4])
return 1
"""


async def resolve_approval(turn_id: str, decision: bool, reason: str) -> bool:
    client = get_client()
    if client is None:
        return False
    status = "approved" if decision else "rejected"
    result = await client.eval(
        _RESOLVE_APPROVAL,
        2,
        approval_key(turn_id),
        key("approvals", "pending"),
        status,
        reason,
        str(time.time()),
        turn_id,
    )
    if result:
        await update_turn(
            turn_id,
            status="running" if decision else "rejected",
            approval_decision="approved" if decision else "rejected",
        )
    return bool(result)


async def wait_approval(turn_id: str, poll_interval: float = 0.25) -> tuple[bool, str]:
    deadline = time.monotonic() + settings.redis.approval_ttl_seconds
    while time.monotonic() < deadline:
        client = get_client()
        if client is None:
            raise RuntimeError("redis coordination is disabled")
        approval = await client.hgetall(approval_key(turn_id))
        turn = await get_turn(turn_id)
        if turn and turn.get("status") == "cancelled":
            return False, "turn_cancelled"
        status = approval.get("status")
        if status == "approved":
            return True, approval.get("reason", "")
        if status == "rejected":
            return False, approval.get("reason", "user rejected")
        await asyncio.sleep(poll_interval)
    await update_turn(turn_id, status="timeout", error_code="approval_expired")
    return False, "approval_expired"


async def pending_approval_count() -> int:
    client = get_client()
    if client is None:
        return 0
    return int(await client.scard(key("approvals", "pending")))


async def remove_from_queues(turn_id: str, scope_hash: str) -> None:
    """Remove a cancelled queued turn from every queue atomically enough for retry."""
    client = get_client()
    if client is None:
        return
    await client.lrem(key("conversation", f"{scope_hash}:queue"), 0, turn_id)
    await client.lrem(key("capacity", "queue"), 0, turn_id)
    await client.srem(key("capacity", "queued_turns"), turn_id)
