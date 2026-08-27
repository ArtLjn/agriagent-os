"""MCP 工具共享的已验证身份读取工具。"""

from __future__ import annotations

import logging

from shared.roles import Permission, has_permission

logger = logging.getLogger(__name__)


class McpToolAuthorizationError(Exception):
    """MCP 工具缺少最小权限时抛出的可序列化授权错误。"""

    code = "permission_denied"

    def __init__(self, permission: Permission):
        self.permission = permission
        super().__init__(f"MCP 工具需要权限: {permission.value}")


_TOOL_OPERATION_PERMISSIONS = {
    "manage_cost": {
        "query": Permission.FARM_READ,
        "summary": Permission.FARM_READ,
        "profit": Permission.FARM_READ,
        "categories": Permission.FARM_READ,
        "create": Permission.FARM_WRITE,
        "delete": Permission.FARM_WRITE,
        "create_category": Permission.FARM_WRITE,
        "delete_category": Permission.FARM_WRITE,
    },
    "manage_planting_units": {
        "query": Permission.FARM_READ,
        "detail": Permission.FARM_READ,
        "create": Permission.FARM_WRITE,
    },
    "manage_crop_cycle": {
        "query": Permission.FARM_READ,
        "detail": Permission.FARM_READ,
        "templates": Permission.FARM_READ,
        "system_templates": Permission.FARM_READ,
        "create": Permission.FARM_WRITE,
        "advance": Permission.FARM_WRITE,
        "update": Permission.FARM_WRITE,
        "delete": Permission.FARM_WRITE,
    },
    "manage_crop_templates": {
        "query": Permission.FARM_READ,
        "create": Permission.FARM_WRITE,
        "import_system": Permission.FARM_WRITE,
    },
    "manage_debt": {
        "query": Permission.FARM_READ,
        "summary": Permission.FARM_READ,
        "create": Permission.FARM_WRITE,
        "repay": Permission.FARM_WRITE,
    },
    "manage_farm_logs": {
        "query": Permission.FARM_READ,
        "create": Permission.FARM_WRITE,
        "update": Permission.FARM_WRITE,
        "delete": Permission.FARM_WRITE,
    },
    "manage_work_orders": {
        "query": Permission.FARM_READ,
        "detail": Permission.FARM_READ,
        "wages": Permission.FARM_READ,
        "create": Permission.FARM_WRITE,
        "add_labor": Permission.FARM_WRITE,
        "update": Permission.FARM_WRITE,
        "settle": Permission.FARM_WRITE,
    },
    "manage_workers": {
        "query": Permission.FARM_READ,
        "create": Permission.FARM_WRITE,
        "update": Permission.FARM_WRITE,
        "delete": Permission.FARM_WRITE,
    },
    "get_weather": {"query": Permission.FARM_READ},
    "search_cities": {"query": Permission.LOCATION_SEARCH},
    "manage_user_settings": {
        "query": Permission.PROFILE_READ,
        "update": Permission.PROFILE_WRITE,
    },
    "commit_planting_plan": {"commit": Permission.FARM_WRITE},
    "prepare_planting_plan": {"prepare": Permission.FARM_READ},
}


def get_farm_id_from_headers(permission: Permission = Permission.FARM_READ) -> int:
    """从 MCP 鉴权 middleware 注入的 Principal 读取内部 farm_id。"""
    return get_principal(permission)["farm_id"]


def get_user_id_from_headers(permission: Permission = Permission.PROFILE_READ) -> str:
    """从 MCP 鉴权 middleware 注入的 Principal 读取用户 ID。"""
    return get_principal(permission)["user_id"]


def get_principal(permission: Permission | None = None) -> dict:
    """读取已验证 Principal；缺失时 fail closed。"""
    from fastmcp.server.dependencies import get_http_request

    request = get_http_request()
    principal = getattr(request.state, "principal", None)
    if not principal:
        raise RuntimeError("MCP request principal missing")
    if not has_permission(
        principal.get("role"), principal.get("scope"), Permission.MCP_INVOKE
    ):
        raise McpToolAuthorizationError(Permission.MCP_INVOKE)
    if permission is not None and not has_permission(
        principal.get("role"), principal.get("scope"), permission
    ):
        raise McpToolAuthorizationError(permission)
    return principal


def permission_for_tool(tool_name: str, operation: str) -> Permission | None:
    """按工具和操作查找最小权限，未知操作保持兼容并返回空值。"""
    permissions = _TOOL_OPERATION_PERMISSIONS.get(tool_name, {})
    return permissions.get((operation or "").lower())


def require_farm_operation_permission(
    operation: str,
    *,
    tool_name: str | None = None,
    read_operations: set[str] | None = None,
    write_operations: set[str] | None = None,
) -> dict:
    """在访问数据库前按集中映射校验 MCP 工具权限。

    新工具应传入 tool_name 使用集中策略；保留读写集合参数兼容迁移期调用方。
    """
    normalized = (operation or "").lower()
    permission = permission_for_tool(tool_name, normalized) if tool_name else None
    if tool_name is None:
        permission = (
            Permission.FARM_WRITE
            if normalized in (write_operations or set())
            else Permission.FARM_READ
            if normalized in (read_operations or set())
            else None
        )
    return get_principal(permission)
