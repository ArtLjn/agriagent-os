"""GET /api/v2/health + GET /api/v2/dev-users。"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

import httpx
from fastapi import HTTPException

from agent.api import api_router
from agent.config import memory_runtime, settings
from agent.deps import pending_approvals
from agent.platforms.persistence.mongo import chat_store
from agent.platforms.persistence.redis.redis_store import (
    get_client,
    key,
)
from agent.platforms.persistence.redis.redis_store import (
    status as redis_status,
)
from agent.platforms.persistence.redis.turn_store import pending_approval_count

logger = logging.getLogger(__name__)
_STARTED_AT = time.time()
_AGENT_SOURCE = Path(__file__).resolve().parents[1]
_MEMORY_SOURCES = [
    *(_AGENT_SOURCE / "domains/harness/memory").glob("*.py"),
    *(_AGENT_SOURCE / "prompts").glob("memory_*.md"),
    _AGENT_SOURCE / "platforms/llm/structured.py",
]
# 启动时固定指纹，不能每次请求读磁盘，否则旧进程会假装已加载新代码。
# 模板移出 Python 后仍须参与指纹，否则部署检查无法发现漏发的提示词版本。
_MEMORY_BUILD = hashlib.sha256(
    b"".join(path.read_bytes() for path in sorted(_MEMORY_SOURCES))
).hexdigest()[:16]


@api_router.get("/health")
async def health() -> dict:
    redis = await redis_status()
    mongo = await chat_store.status()
    dependencies_ok = (not redis["enabled"] or redis["reachable"]) and (
        not mongo["enabled"] or mongo["reachable"]
    )
    return {
        "status": "ok" if dependencies_ok else "degraded",
        "pending_approvals": await pending_approval_count(),
        "active_turns": await _active_turn_count(),
        "redis": redis,
        "mongo": mongo,
        "runtime": {
            "started_at": _STARTED_AT,
            "memory_build": _MEMORY_BUILD,
            "memory_mode": memory_runtime.context_mode,
            "memory_semantic_configured": bool(
                memory_runtime.rag_url and memory_runtime.rag_api_key
            ),
            "skill_router_mode": settings.context.skill_router_mode,
        },
    }


async def _active_turn_count() -> int:
    client = get_client()
    if client is None:
        return len(pending_approvals)
    return int(await client.scard(key("capacity", "active_turns")))


@api_router.get("/dev-users")
async def dev_users() -> dict:
    """开发环境：代理 Business 的用户切换接口。"""
    if settings.environment != "development":
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "开发用户接口未启用"},
        )
    url = f"{settings.business_mcp.api_url.rstrip('/')}/dev-users"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        logger.warning("dev-users proxy failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"code": "business_unavailable", "message": "业务服务不可用"},
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail={"code": "invalid_response", "message": "业务服务返回无效响应"},
        ) from exc

    if response.status_code >= 400:
        detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        raise HTTPException(status_code=response.status_code, detail=detail)
    return payload
