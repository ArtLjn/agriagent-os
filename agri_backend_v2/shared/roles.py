"""用户角色及其授权语义的唯一后端定义。"""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """系统支持的用户角色。"""

    ADMIN = "admin"
    USER = "user"
    DEV = "dev"


class Permission(str, Enum):
    """接口和 MCP 工具使用的稳定权限名。"""

    AGENT_INVOKE = "agent:invoke"
    MCP_INVOKE = "mcp:invoke"
    CONVERSATION_READ = "conversation:read"
    CONVERSATION_WRITE = "conversation:write"
    TURN_APPROVE = "turn:approve"
    TURN_CANCEL = "turn:cancel"
    TRACE_READ = "trace:read"
    TRACE_DEBUG = "trace:debug"
    FARM_READ = "farm:read"
    FARM_WRITE = "farm:write"
    LOCATION_SEARCH = "location:search"
    PROFILE_READ = "profile:read"
    PROFILE_WRITE = "profile:write"
    ADMIN_USER_READ = "admin:user:read"
    ADMIN_USER_WRITE = "admin:user:write"
    ADMIN_DEBUG = "admin:debug"


NORMAL_USER_ROLES = frozenset({UserRole.USER, UserRole.DEV})
ADMIN_SCOPE = "farm:read farm:write admin:*"
NORMAL_USER_SCOPE = "farm:read farm:write"

_NORMAL_PERMISSIONS = frozenset(
    {
        Permission.AGENT_INVOKE,
        Permission.MCP_INVOKE,
        Permission.CONVERSATION_READ,
        Permission.CONVERSATION_WRITE,
        Permission.TURN_APPROVE,
        Permission.TURN_CANCEL,
        Permission.TRACE_READ,
        Permission.FARM_READ,
        Permission.FARM_WRITE,
        Permission.LOCATION_SEARCH,
        Permission.PROFILE_READ,
        Permission.PROFILE_WRITE,
    }
)
_ADMIN_PERMISSIONS = _NORMAL_PERMISSIONS | frozenset(
    {
        Permission.TRACE_DEBUG,
        Permission.ADMIN_USER_READ,
        Permission.ADMIN_USER_WRITE,
        Permission.ADMIN_DEBUG,
    }
)


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


def role_permissions(role: str | UserRole) -> frozenset[Permission]:
    """返回角色上限；未知角色默认拒绝而不是降级为普通用户。"""
    try:
        normalized = normalize_user_role(role)
    except ValueError:
        return frozenset()
    return _ADMIN_PERMISSIONS if normalized is UserRole.ADMIN else _NORMAL_PERMISSIONS


def scope_permissions(scope: str | None) -> frozenset[str]:
    """将 JWT/MCP scope 拆成权限字符串，缺失 scope 时保持拒绝。"""
    if not scope:
        return frozenset()
    return frozenset(str(scope).split())


def has_permission(
    role: str | UserRole,
    scope: str | None,
    permission: str | Permission,
) -> bool:
    """检查角色权限与 token scope 的交集，不让 token 扩大角色能力。"""
    try:
        required = (
            permission if isinstance(permission, Permission) else Permission(permission)
        )
    except ValueError:
        return False
    if required not in role_permissions(role):
        return False
    scopes = scope_permissions(scope)
    return required.value in scopes or f"{required.value.split(':', 1)[0]}:*" in scopes


__all__ = [
    "ADMIN_SCOPE",
    "NORMAL_USER_ROLES",
    "NORMAL_USER_SCOPE",
    "Permission",
    "UserRole",
    "has_permission",
    "is_admin_role",
    "is_normal_user_role",
    "normalize_user_role",
    "role_permissions",
    "scope_permissions",
    "scope_for_role",
]
