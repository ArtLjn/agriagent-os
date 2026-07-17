"""农事作业单 Skill alias 兼容规则。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.skills.registry import load_skill_registry

MANAGE_WORK_ORDERS = "manage_work_orders"

CREATE_WORK_ORDER = "create_work_order"
QUERY_WORK_ORDERS = "query_work_orders"
UPDATE_WORK_ORDER = "update_work_order"

WORK_ORDER_OPERATIONS = frozenset(
    {
        CREATE_WORK_ORDER,
        QUERY_WORK_ORDERS,
        UPDATE_WORK_ORDER,
    }
)
WORK_ORDER_WRITE_OPERATIONS = frozenset({CREATE_WORK_ORDER, UPDATE_WORK_ORDER})
WORK_ORDER_ALIASES = frozenset(
    {
        "create_operation_work_order",
        "get_operation_work_orders",
        "update_operation_work_order",
    }
)
WORK_ORDER_COMPAT_NAMES = frozenset({MANAGE_WORK_ORDERS, *WORK_ORDER_ALIASES})


def canonical_work_order_tool_name(name: str) -> str:
    """返回作业单 capability 的物理 runtime tool name。"""
    if name == MANAGE_WORK_ORDERS:
        return name
    alias = _resolve_work_order_alias(name)
    return alias.capability if alias is not None else name


def operation_for_work_order_call(name: str, args: Mapping[str, Any] | None) -> str | None:
    """从 tool name 或 operation 参数解析作业单 operation。"""
    operation = str((args or {}).get("operation") or "").strip()
    if operation in _registry_work_order_operations():
        return operation
    alias = _resolve_work_order_alias(name)
    return alias.operation if alias is not None else None


def with_work_order_operation(name: str, args: Mapping[str, Any] | None) -> dict[str, Any]:
    """为旧 alias 调用补齐 operation，保留原始参数。"""
    normalized = dict(args or {})
    operation = operation_for_work_order_call(name, normalized)
    if operation:
        normalized.setdefault("operation", operation)
    return normalized


def is_work_order_write_call(name: str, args: Mapping[str, Any] | None) -> bool:
    """判断当前作业单调用是否需要写确认。"""
    return operation_for_work_order_call(name, args) in WORK_ORDER_WRITE_OPERATIONS


def is_work_order_read_call(name: str, args: Mapping[str, Any] | None) -> bool:
    """判断当前作业单调用是否是只读查询。"""
    return operation_for_work_order_call(name, args) == QUERY_WORK_ORDERS


def resolve_available_work_order_tool(name: str, available_names: set[str]) -> str:
    """根据当前可用工具把旧 alias 映射到物理工具。"""
    if name in available_names:
        return name
    canonical = canonical_work_order_tool_name(name)
    if canonical in available_names:
        return canonical
    return name


def _resolve_work_order_alias(name: str):
    try:
        alias = load_skill_registry().resolve_alias(name)
    except (OSError, ValueError):
        return None
    if alias is None or alias.capability != MANAGE_WORK_ORDERS:
        return None
    return alias


def _registry_work_order_operations() -> frozenset[str]:
    try:
        capability = load_skill_registry().capabilities.get(MANAGE_WORK_ORDERS)
    except (OSError, ValueError):
        return WORK_ORDER_OPERATIONS
    if capability is None:
        return WORK_ORDER_OPERATIONS
    return frozenset(capability.operations)


__all__ = [
    "CREATE_WORK_ORDER",
    "MANAGE_WORK_ORDERS",
    "QUERY_WORK_ORDERS",
    "UPDATE_WORK_ORDER",
    "WORK_ORDER_ALIASES",
    "WORK_ORDER_COMPAT_NAMES",
    "WORK_ORDER_OPERATIONS",
    "WORK_ORDER_WRITE_OPERATIONS",
    "canonical_work_order_tool_name",
    "is_work_order_read_call",
    "is_work_order_write_call",
    "operation_for_work_order_call",
    "resolve_available_work_order_tool",
    "with_work_order_operation",
]
