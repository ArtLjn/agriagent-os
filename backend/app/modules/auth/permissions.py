"""Auth 权限判断。"""

from app.models.user import User


def is_admin(user: User) -> bool:
    """判断用户是否为管理员。"""
    return user.role == "admin"
