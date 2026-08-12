"""GET /api/v2/health + GET /api/v2/dev-users。"""

from __future__ import annotations

import logging
import time

from fastapi import HTTPException

from agent.api import api_router
from agent.config import settings
from agent.deps import pending_approvals
from agent.infra.redis_store import get_client, key, status as redis_status
from agent.infra.turn_store import pending_approval_count

logger = logging.getLogger(__name__)


@api_router.get("/health")
async def health() -> dict:
    redis = await redis_status()
    return {
        "status": "ok" if not redis["enabled"] or redis["reachable"] else "degraded",
        "pending_approvals": await pending_approval_count(),
        "active_turns": await _active_turn_count(),
        "redis": redis,
    }


async def _active_turn_count() -> int:
    client = get_client()
    if client is None:
        return len(pending_approvals)
    return int(await client.scard(key("capacity", "active_turns")))


@api_router.get("/dev-users")
def dev_users() -> dict:
    """开发环境：返回数据库中的用户列表 + JWT token，供前端切换用户。"""
    from business.db import session_scope
    from business.models import Farm, User

    secret = settings.auth.jwt_secret or "dev-secret-key"
    algorithm = settings.auth.jwt_algorithm or "HS256"

    try:
        import jwt as pyjwt
    except ImportError:
        raise HTTPException(500, "PyJWT not installed")

    try:
        with session_scope() as db:
            rows = (
                db.query(User, Farm)
                .outerjoin(Farm, Farm.user_id == User.id)
                .filter(User.status == "active")
                .order_by(User.created_at)
                .limit(50)
                .all()
            )

            users = []
            now = int(time.time())
            exp = now + 30 * 86400

            for user, farm in rows:
                farm_id = farm.id if farm else (settings.default_farm_id or 1)
                payload = {
                    "sub": user.id,
                    "farm_id": farm_id,
                    "nickname": user.nickname,
                    "role": user.role,
                    "exp": exp,
                }
                token = pyjwt.encode(payload, secret, algorithm=algorithm)
                users.append(
                    {
                        "user_id": user.id,
                        "nickname": user.nickname,
                        "phone": user.phone,
                        "role": user.role,
                        "farm_id": farm_id,
                        "token": token,
                    }
                )

            return {"users": users, "total": len(users)}
    except Exception as exc:
        logger.warning("dev-users query failed: %s", exc)
        raise HTTPException(500, f"Failed to list users: {exc}")
