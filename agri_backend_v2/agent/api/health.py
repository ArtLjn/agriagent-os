"""GET /api/v2/health + GET /api/v2/dev-users。"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

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
from shared.roles import UserRole

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
def dev_users() -> dict:
    """开发环境：返回数据库中的用户列表 + JWT token，供前端切换用户。"""
    if settings.environment != "development":
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "开发用户接口未启用"},
        )
    from business.db import session_scope
    from business.models import Farm, User

    secret = settings.auth.jwt_secret
    algorithm = settings.auth.jwt_algorithm or "HS256"
    if not secret:
        raise HTTPException(
            status_code=503,
            detail={"code": "auth_unavailable", "message": "JWT_SECRET 未配置"},
        )

    try:
        import jwt as pyjwt
    except ImportError:
        raise HTTPException(500, "PyJWT not installed")

    try:
        with session_scope() as db:
            rows = (
                db.query(User, Farm)
                .outerjoin(Farm, Farm.user_id == User.id)
                .filter(User.status == "active", User.role == UserRole.DEV.value)
                .order_by(User.created_at)
                .limit(50)
                .all()
            )

            users = []
            now = int(time.time())
            exp = now + 30 * 86400

            for user, farm in rows:
                farm_id = farm.id if farm else None
                farm_uid = farm.uid if farm else None
                if farm is None:
                    continue
                payload = {
                    "iss": settings.auth.jwt_issuer,
                    "aud": settings.auth.jwt_audience,
                    "sub": user.id,
                    "farm_uid": farm_uid,
                    # Redis/Mongo 迁移完成后删除；当前 Agent 仍用它计算内部 scope。
                    "farm_id": farm_id,
                    "nickname": user.nickname,
                    "role": user.role,
                    "type": "access",
                    "scope": "farm:read farm:write",
                    "iat": now,
                    "nbf": now,
                    "exp": exp,
                    "jti": f"dev-{user.id}-{now}",
                }
                token = pyjwt.encode(payload, secret, algorithm=algorithm)
                users.append(
                    {
                        "user_id": user.id,
                        "nickname": user.nickname,
                        "phone": user.phone,
                        "role": user.role,
                        "farm_uid": farm_uid,
                        "farm_id": farm_id,
                        "token": token,
                    }
                )

            return {"users": users, "total": len(users)}
    except Exception as exc:  # noqa: BLE001 -- 开发账号查询的数据库边界统一转成 HTTP 错误。
        logger.warning("dev-users query failed: %s", exc)
        raise HTTPException(500, f"Failed to list users: {exc}")
