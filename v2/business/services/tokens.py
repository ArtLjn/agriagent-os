"""用户 Access JWT 签发与校验。

JWT payload 标准：
  - sub: user_id
  - phone: 用户手机号
  - role: user/admin
  - farm_uid: 关联农场 UUID
  - farm_id: 迁移期内部兼容字段，不作为对外租户标识
  - type: "access"
  - iat / exp / jti

签发时绑定 farm_uid，Business 再通过用户归属关系解析内部 farm_id。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from business.config import settings


class TokenExpiredError(Exception):
    """token 已过期。"""


class TokenInvalidError(Exception):
    """token 无效。"""


def create_access_token(
    user_id: str,
    phone: str | None = None,
    role: str = "user",
    farm_uid: str | None = None,
    farm_id: int | None = None,
    scope: str | None = None,
    expires_minutes: int | None = None,
) -> str:
    """签发标准 access token。

    Args:
        user_id: 用户 ID
        phone: 手机号（可选，便于日志展示）
        role: 角色（user/admin）
        farm_uid: 对外农场 UUID
        farm_id: 迁移期内部 ID，不作为对外租户标识
        expires_minutes: 过期分钟数，默认从 config 读

    Returns:
        JWT token 字符串
    """
    cfg = settings.auth
    if not cfg.jwt_secret:
        raise RuntimeError("JWT_SECRET 未配置，无法签发认证令牌")
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes
        if expires_minutes is not None
        else cfg.jwt_expire_minutes
    )
    payload: dict[str, Any] = {
        "iss": cfg.jwt_issuer,
        "aud": cfg.jwt_audience,
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    if phone is not None:
        payload["phone"] = phone
    if role is not None:
        payload["role"] = role
    payload["scope"] = scope or (
        "farm:read farm:write admin:*" if role == "admin" else "farm:read farm:write"
    )
    if farm_uid is not None:
        payload["farm_uid"] = farm_uid
    # 迁移期保留内部 farm_id，待 Agent Redis/Mongo 状态完成 farm_uid 化后删除。
    if farm_id is not None:
        payload["farm_id"] = farm_id
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """验证 access token，失败时抛出明确异常。"""
    cfg = settings.auth
    if not cfg.jwt_secret:
        raise RuntimeError("JWT_SECRET 未配置，无法校验认证令牌")
    try:
        payload = jwt.decode(
            token,
            cfg.jwt_secret,
            algorithms=[cfg.jwt_algorithm],
            issuer=cfg.jwt_issuer,
            audience=cfg.jwt_audience,
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError from exc
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError from exc
    if payload.get("type") != "access":
        raise TokenInvalidError
    return payload


def verify_token(token: str) -> dict | None:
    """验证 JWT token，成功返回 payload，失败返回 None。"""
    try:
        return decode_access_token(token)
    except (TokenExpiredError, TokenInvalidError):
        return None


__all__ = [
    "TokenExpiredError",
    "TokenInvalidError",
    "create_access_token",
    "decode_access_token",
    "verify_token",
]
