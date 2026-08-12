"""Redis 共享协调层连接管理。

Redis 是 Agent turn、会话锁、审批和事件队列的协调基础设施；它不可用时，
上层不应绕过协调层继续执行可能产生业务写入的 turn。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from agent.config import settings

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None
_client: Redis | None = None


def get_client() -> Redis | None:
    """返回共享异步客户端；Redis 禁用时返回 None。"""
    global _pool, _client
    cfg = settings.redis
    if not cfg.enabled:
        return None
    if _client is None:
        _pool = ConnectionPool(
            host=cfg.host,
            port=cfg.port,
            db=cfg.database,
            username=cfg.username or None,
            password=cfg.password or None,
            max_connections=cfg.max_connections,
            socket_connect_timeout=cfg.connect_timeout_ms / 1000,
            socket_timeout=cfg.socket_timeout_ms / 1000,
            decode_responses=True,
        )
        _client = Redis(connection_pool=_pool)
    return _client


def key(resource: str, identifier: str) -> str:
    """Build a namespaced Redis key without exposing credentials."""
    return f"{settings.redis.key_prefix}:{resource}:{identifier}"


async def eval_script(
    script: str,
    keys: Sequence[str],
    args: Sequence[str | int],
) -> int:
    """Execute a small atomic coordination script."""
    client = get_client()
    if client is None:
        raise RuntimeError("redis coordination is disabled")
    result = await client.eval(script, len(keys), *keys, *[str(arg) for arg in args])
    return int(result)


async def check_connection() -> bool:
    """检查 Redis 连通性，启动阶段失败只降级为不可用状态。"""
    client = get_client()
    if client is None:
        logger.info("redis disabled; Agent coordination is not enabled")
        return False
    try:
        await client.ping()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "redis connection check failed host=%s port=%s error=%s",
            settings.redis.host,
            settings.redis.port,
            type(exc).__name__,
        )
        return False
    logger.info(
        "redis connection ok host=%s port=%s db=%s",
        settings.redis.host,
        settings.redis.port,
        settings.redis.database,
    )
    return True


async def status() -> dict[str, object]:
    """返回不包含凭据的 Redis 健康状态。"""
    if not settings.redis.enabled:
        return {"enabled": False, "reachable": False}
    reachable = await check_connection()
    return {
        "enabled": True,
        "reachable": reachable,
        "host": settings.redis.host,
        "port": settings.redis.port,
        "database": settings.redis.database,
    }


async def close() -> None:
    """关闭共享连接池。"""
    global _pool, _client
    if _client is not None:
        await _client.aclose()
    if _pool is not None:
        await _pool.disconnect()
    _client = None
    _pool = None
