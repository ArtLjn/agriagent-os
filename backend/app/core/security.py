"""安全工具兼容入口。

具体实现已迁移到 Auth 模块。
"""

from app.modules.auth.password import hash_password, verify_password
from app.modules.auth.tokens import create_access_token, verify_token

__all__ = [
    "create_access_token",
    "hash_password",
    "verify_password",
    "verify_token",
]
