"""Auth 密码哈希与校验（从 archive 复用）。

bcrypt 哈希与校验，独立于 ORM 和数据库。
"""
from __future__ import annotations

import bcrypt

from business.config import settings


def hash_password(password: str) -> str:
    """对密码进行 bcrypt 哈希。

    使用 config.auth.bcrypt_rounds 配置工作因子（默认 12）。
    """
    rounds = settings.auth.bcrypt_rounds
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


__all__ = ["hash_password", "verify_password"]
