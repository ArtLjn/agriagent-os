"""安全工具 — JWT 签发/验证 + bcrypt 密码哈希。"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    """对密码进行 bcrypt 哈希。"""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return bcrypt.checkpw(
        plain.encode("utf-8"), hashed.encode("utf-8")
    )


def create_access_token(
    user_id: str, expires_minutes: int | None = None
) -> str:
    """签发 JWT access token。"""
    cfg = settings.auth
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes
        if expires_minutes is not None
        else cfg.jwt_expire_minutes
    )
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)


def verify_token(token: str) -> dict | None:
    """验证 JWT token，成功返回 payload，失败返回 None。"""
    cfg = settings.auth
    try:
        return jwt.decode(
            token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm]
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
