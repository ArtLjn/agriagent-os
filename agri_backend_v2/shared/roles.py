"""用户角色及其授权语义的唯一后端定义。"""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """系统支持的用户角色。"""

    ADMIN = "admin"
    USER = "user"
    DEV = "dev"


NORMAL_USER_ROLES = frozenset({UserRole.USER, UserRole.DEV})
ADMIN_SCOPE = "farm:read farm:write admin:*"
NORMAL_USER_SCOPE = "farm:read farm:write"


def normalize_user_role(role: str | UserRole) -> UserRole:
    """将外部角色值收敛为受支持的枚举，拒绝未知角色。"""
    if isinstance(role, UserRole):
        return role
    try:
        return UserRole(str(role).strip().lower())
    except ValueError as exc:
        raise ValueError(f"不支持的用户角色: {role}") from exc


def is_admin_role(role: str | UserRole | None) -> bool:
    """判断角色是否拥有管理员调试和管理端权限。"""
    try:
        return normalize_user_role(role or UserRole.USER) is UserRole.ADMIN
    except ValueError:
        return False


def is_normal_user_role(role: str | UserRole | None) -> bool:
    """判断角色是否属于 user/dev 普通用户权限集合。"""
    try:
        return normalize_user_role(role or UserRole.USER) in NORMAL_USER_ROLES
    except ValueError:
        return False


def scope_for_role(role: str | UserRole) -> str:
    """根据角色生成 Token scope；dev 与 user 共用普通用户 scope。"""
    return ADMIN_SCOPE if is_admin_role(role) else NORMAL_USER_SCOPE


__all__ = [
    "ADMIN_SCOPE",
    "NORMAL_USER_ROLES",
    "NORMAL_USER_SCOPE",
    "UserRole",
    "is_admin_role",
    "is_normal_user_role",
    "normalize_user_role",
    "scope_for_role",
]
