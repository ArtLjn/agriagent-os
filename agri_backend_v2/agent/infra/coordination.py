"""Redis-backed admission control for Agent turns.

第一阶段只实现有界并发和同会话互斥，不在 HTTP 请求内做无界排队。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass

from agent.config import settings
from agent.infra.redis_store import eval_script, key

logger = logging.getLogger(__name__)

_ACQUIRE_SCRIPT = """
local lock_key = KEYS[1]
local global_key = KEYS[2]
local user_key = KEYS[3]
if redis.call('EXISTS', lock_key) == 1 then
  return 1
end
if redis.call('SCARD', global_key) >= tonumber(ARGV[3]) then
  return 2
end
if redis.call('SCARD', user_key) >= tonumber(ARGV[4]) then
  return 3
end
redis.call('SET', lock_key, ARGV[1], 'PX', ARGV[2])
redis.call('SADD', global_key, ARGV[5])
redis.call('SADD', user_key, ARGV[5])
return 0
"""

_ADMIT_SCRIPT = """
local lock_key = KEYS[1]
local global_key = KEYS[2]
local user_key = KEYS[3]
local conversation_queue = KEYS[4]
local global_queue = KEYS[5]
local global_wait_queue = KEYS[6]
if redis.call('EXISTS', lock_key) == 1 then
  if redis.call('LLEN', conversation_queue) >= tonumber(ARGV[5]) then
    return 4
  end
  if redis.call('LLEN', global_wait_queue) >= tonumber(ARGV[6]) then
    return 5
  end
  redis.call('RPUSH', conversation_queue, ARGV[7])
  redis.call('RPUSH', global_wait_queue, ARGV[7])
  redis.call('SADD', global_queue, ARGV[7])
  return 3
end
if redis.call('SCARD', global_key) >= tonumber(ARGV[3]) then
  if redis.call('LLEN', global_wait_queue) >= tonumber(ARGV[6]) then
    return 5
  end
  redis.call('RPUSH', global_wait_queue, ARGV[7])
  redis.call('SADD', global_queue, ARGV[7])
  return 6
end
if redis.call('SCARD', user_key) >= tonumber(ARGV[4]) then
  return 2
end
redis.call('SET', lock_key, ARGV[1], 'PX', ARGV[2])
redis.call('SADD', global_key, ARGV[7])
redis.call('SADD', user_key, ARGV[7])
return 0
"""

_PROMOTE_SCRIPT = """
local lock_key = KEYS[1]
local global_key = KEYS[2]
local user_key = KEYS[3]
local conversation_queue = KEYS[4]
local global_queue = KEYS[5]
local global_wait_queue = KEYS[6]
if redis.call('EXISTS', lock_key) == 1 then
  return 1
end
if redis.call('SCARD', global_key) >= tonumber(ARGV[3]) then
  return 2
end
if redis.call('SCARD', user_key) >= tonumber(ARGV[4]) then
  return 3
end
local removed = redis.call('LREM', conversation_queue, 1, ARGV[5])
if removed == 1 then
  redis.call('LREM', global_wait_queue, 1, ARGV[5])
else
  removed = redis.call('LREM', global_wait_queue, 1, ARGV[5])
end
if removed ~= 1 then return 4 end
redis.call('SREM', global_queue, ARGV[5])
redis.call('SET', lock_key, ARGV[1], 'PX', ARGV[2])
redis.call('SADD', global_key, ARGV[5])
redis.call('SADD', user_key, ARGV[5])
return 0
"""

_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
  return 0
end
redis.call('DEL', KEYS[1])
redis.call('SREM', KEYS[2], ARGV[2])
redis.call('SREM', KEYS[3], ARGV[2])
return 1
"""

_RENEW_SCRIPT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
  return 0
end
return redis.call('PEXPIRE', KEYS[1], ARGV[2])
"""


class CoordinationError(RuntimeError):
    """协调层不可用或配置无效。"""


class TurnAdmissionError(RuntimeError):
    """Turn 未通过并发准入，携带稳定错误码。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TurnAdmission:
    """准入结果；queued=True 时尚未占用活跃执行槽位。"""

    lease: "TurnLease"
    queued: bool = False
    queue_kind: str = ""


@dataclass(frozen=True)
class TurnLease:
    turn_id: str
    scope_hash: str
    user_scope_hash: str
    token: str

    @property
    def lock_key(self) -> str:
        return key("conversation", f"{self.scope_hash}:lock")

    @property
    def global_key(self) -> str:
        return key("capacity", "active_turns")

    @property
    def user_key(self) -> str:
        return key("user", f"{self.user_scope_hash}:active")

    @property
    def queue_key(self) -> str:
        return key("conversation", f"{self.scope_hash}:queue")

    @property
    def global_queue_key(self) -> str:
        return key("capacity", "queued_turns")

    @property
    def global_wait_queue_key(self) -> str:
        return key("capacity", "queue")


def scope_hash(user_id: str, farm_id: int, conversation_id: str) -> str:
    """按身份边界计算会话 scope，避免不同用户共享 conversation 锁。"""
    value = f"{user_id or 'anonymous'}|{farm_id}|{conversation_id}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def user_scope_hash(user_id: str, farm_id: int) -> str:
    value = f"{user_id or 'anonymous'}|{farm_id}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def acquire_turn(
    *,
    turn_id: str,
    user_id: str,
    farm_id: int,
    conversation_id: str,
) -> TurnLease:
    """兼容旧调用方：只接受立即运行的 turn。"""
    admission = await admit_turn(
        turn_id=turn_id,
        user_id=user_id,
        farm_id=farm_id,
        conversation_id=conversation_id,
    )
    if admission.queued:
        raise TurnAdmissionError(
            "conversation_busy", "当前会话已有运行中的 turn，请稍后重试"
        )
    return admission.lease


async def admit_turn(
    *,
    turn_id: str,
    user_id: str,
    farm_id: int,
    conversation_id: str,
) -> TurnAdmission:
    """原子申请活跃槽位，或加入有界的会话 FIFO 队列。"""
    cfg = settings.redis
    if not cfg.enabled:
        raise CoordinationError("redis coordination is disabled")
    if cfg.global_active_limit < 1 or cfg.user_active_limit < 1:
        raise CoordinationError("redis concurrency limits must be positive")

    lease = TurnLease(
        turn_id=turn_id,
        scope_hash=scope_hash(user_id, farm_id, conversation_id),
        user_scope_hash=user_scope_hash(user_id, farm_id),
        token=uuid.uuid4().hex,
    )
    try:
        result = await eval_script(
            _ADMIT_SCRIPT,
            [
                lease.lock_key,
                lease.global_key,
                lease.user_key,
                lease.queue_key,
                lease.global_queue_key,
                lease.global_wait_queue_key,
            ],
            [
                lease.token,
                cfg.conversation_lock_ttl_ms,
                cfg.global_active_limit,
                cfg.user_active_limit,
                cfg.conversation_queue_limit,
                cfg.global_queue_limit,
                lease.turn_id,
            ],
        )
    except Exception as exc:  # noqa: BLE001
        raise CoordinationError("redis coordination unavailable") from exc

    if result == 1:
        raise TurnAdmissionError("agent_overloaded", "Agent 当前并发容量已满")
    if result == 2:
        raise TurnAdmissionError("user_concurrency_limit", "当前用户并发容量已满")
    if result == 4:
        raise TurnAdmissionError("conversation_queue_full", "当前会话排队队列已满")
    if result == 5:
        raise TurnAdmissionError("agent_overloaded", "Agent 等待队列已满")
    if result == 6:
        return TurnAdmission(lease=lease, queued=True, queue_kind="global")
    if result == 3:
        return TurnAdmission(lease=lease, queued=True, queue_kind="conversation")
    if result != 0:
        raise CoordinationError("unexpected redis admission result")
    return TurnAdmission(lease=lease, queued=False, queue_kind="")


async def promote_turn(lease: TurnLease) -> bool:
    """将已排队 turn 提升为活跃 turn。"""
    try:
        result = await eval_script(
            _PROMOTE_SCRIPT,
            [
                lease.lock_key,
                lease.global_key,
                lease.user_key,
                lease.queue_key,
                lease.global_queue_key,
                lease.global_wait_queue_key,
            ],
            [
                lease.token,
                settings.redis.conversation_lock_ttl_ms,
                settings.redis.global_active_limit,
                settings.redis.user_active_limit,
                lease.turn_id,
            ],
        )
    except Exception as exc:  # noqa: BLE001
        raise CoordinationError("redis coordination unavailable") from exc
    return result == 0


async def renew_turn(lease: TurnLease) -> bool:
    """续租会话锁；返回 False 表示 lease 已不再属于当前 turn。"""
    try:
        result = await eval_script(
            _RENEW_SCRIPT,
            [lease.lock_key],
            [lease.token, settings.redis.conversation_lock_ttl_ms],
        )
    except Exception:  # noqa: BLE001
        logger.exception("failed to renew turn lease turn_id=%s", lease.turn_id)
        return False
    return result == 1


async def owns_turn_lease(lease: TurnLease) -> bool:
    client = __import__("agent.infra.redis_store", fromlist=["get_client"]).get_client()
    if client is None:
        return False
    return await client.get(lease.lock_key) == lease.token


async def release_turn(lease: TurnLease) -> bool:
    """仅允许持有当前 token 的 turn 释放锁和活跃槽位。"""
    try:
        result = await eval_script(
            _RELEASE_SCRIPT,
            [lease.lock_key, lease.global_key, lease.user_key],
            [lease.token, lease.turn_id],
        )
    except Exception:  # noqa: BLE001
        logger.exception("failed to release turn lease turn_id=%s", lease.turn_id)
        return False
    return result == 1


async def wake_conversation(scope: str) -> str | None:
    """取出会话队首，交给 dispatch stream 重新调度。"""
    client = __import__("agent.infra.redis_store", fromlist=["get_client"]).get_client()
    if client is None:
        return None
    queue_key = key("conversation", f"{scope}:queue")
    turn_id = await client.lindex(queue_key, 0)
    if not turn_id:
        return None
    await client.xadd(
        key("dispatch", settings.redis.dispatch_stream),
        {"turn_id": turn_id, "created_at": str(uuid.uuid4())},
        maxlen=settings.redis.global_queue_limit,
        approximate=False,
    )
    await client.expire(
        key("dispatch", settings.redis.dispatch_stream),
        settings.redis.dispatch_stream_ttl_seconds,
    )
    return turn_id


async def wake_global_queue() -> str | None:
    """将多个全局候选投递给 Worker，避免用户配额造成队首饥饿。"""
    client = __import__("agent.infra.redis_store", fromlist=["get_client"]).get_client()
    if client is None:
        return None
    candidates = await client.lrange(
        key("capacity", "queue"), 0, max(settings.redis.worker_count * 2, 1) - 1
    )
    if not candidates:
        return None
    for turn_id in candidates:
        await client.xadd(
            key("dispatch", settings.redis.dispatch_stream),
            {"turn_id": turn_id, "created_at": str(uuid.uuid4())},
            maxlen=settings.redis.global_queue_limit,
            approximate=False,
        )
    await client.expire(
        key("dispatch", settings.redis.dispatch_stream),
        settings.redis.dispatch_stream_ttl_seconds,
    )
    return candidates[0]


async def renew_until_done(lease: TurnLease, stop: asyncio.Event) -> None:
    """后台续租任务，客户端断开或 turn 完成时由调用方停止。"""
    interval = max(settings.redis.conversation_lock_renew_ms, 1000) / 1000
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            if not await renew_turn(lease):
                logger.error("turn lease lost turn_id=%s", lease.turn_id)
                return
