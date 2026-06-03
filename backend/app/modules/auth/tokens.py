"""Auth JWT 签发与验证。"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


class TokenExpiredError(Exception):
    """token 已过期。"""


class TokenInvalidError(Exception):
    """token 无效。"""


def create_access_token(user_id: str, expires_minutes: int | None = None) -> str:
    """签发标准 access token。"""
    cfg = settings.auth
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes
        if expires_minutes is not None
        else cfg.jwt_expire_minutes
    )
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """验证 access token，失败时抛出明确异常。"""
    cfg = settings.auth
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError from exc
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError from exc
    if payload.get("type", "access") != "access":
        raise TokenInvalidError
    return payload


def verify_token(token: str) -> dict | None:
    """验证 JWT token，成功返回 payload，失败返回 None。"""
    try:
        return decode_access_token(token)
    except (TokenExpiredError, TokenInvalidError):
        return None
