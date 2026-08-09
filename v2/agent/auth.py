"""JWT 身份解析。

从 Authorization: Bearer <jwt> 提取 user_id / farm_id，
供 route 层依赖注入使用。
"""

from __future__ import annotations

import logging

from agent.config import settings

logger = logging.getLogger(__name__)


def parse_identity(authorization: str | None) -> dict:
    """解析 JWT，返回 {"user_id": ..., "farm_id": ..., "agent_token": ...}。

    无 JWT 或解析失败时返回默认值（farm_id=1），保证开发模式可用。
    """
    default = {
        "user_id": "",
        "farm_id": settings.default_farm_id or 1,
        "agent_token": settings.auth.agent_service_token,
    }
    if not authorization or not authorization.startswith("Bearer "):
        return default
    token = authorization[7:]
    secret = settings.auth.jwt_secret or "dev-secret-key"
    try:
        import jwt

        payload = jwt.decode(token, secret, algorithms=[settings.auth.jwt_algorithm])
        return {
            "user_id": payload.get("sub", ""),
            "farm_id": payload.get("farm_id", default["farm_id"]),
            "agent_token": settings.auth.agent_service_token,
        }
    except Exception as exc:
        logger.warning("JWT parse failed, using default identity: %s", exc)
        return default
