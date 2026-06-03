"""认证服务兼容入口。

具体实现已迁移到 Auth 模块。
"""

from app.modules.auth.service import get_user_by_id, login, register

__all__ = ["get_user_by_id", "login", "register"]
