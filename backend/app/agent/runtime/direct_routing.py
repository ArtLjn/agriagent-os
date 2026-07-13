"""工具结果直返与工具调用白名单过滤。"""

import logging

from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)

DIRECT_RETURN_TOOLS: set[str] = {"get_workers"}
DIRECT_RETURN_MANAGE_COST_OPERATIONS: set[str] = {"query_debt"}


def can_return_direct_tool_messages(messages: list[ToolMessage]) -> bool:
    """判断直达工具结果是否可以绕过最终 LLM。"""
    for msg in messages:
        tool_name, operation = _tool_identity(msg)
        if not tool_name:
            return False
        if tool_name == "manage_cost":
            if operation not in DIRECT_RETURN_MANAGE_COST_OPERATIONS:
                return False
            continue
        if tool_name not in DIRECT_RETURN_TOOLS:
            return False
    return True


def _tool_identity(msg: ToolMessage) -> tuple[str | None, str | None]:
    tool_name = getattr(msg, "name", None)
    operation = _message_operation(msg)
    if tool_name:
        return str(tool_name), operation

    tool_call_id = str(getattr(msg, "tool_call_id", ""))
    if not tool_call_id.startswith("direct_"):
        return None, None
    direct_name = tool_call_id.removeprefix("direct_")
    if direct_name.startswith("manage_cost_"):
        return "manage_cost", direct_name.removeprefix("manage_cost_")
    return direct_name, operation


def _message_operation(msg: ToolMessage) -> str | None:
    additional_kwargs = getattr(msg, "additional_kwargs", None)
    if isinstance(additional_kwargs, dict):
        operation = additional_kwargs.get("operation")
        if operation:
            return str(operation)
    return None


def filter_tool_calls_by_selected(
    tool_calls: list[dict],
    selected_tools: list,
) -> list[dict]:
    """只保留本轮绑定给 LLM 的工具调用，避免手动 JSON 解析越权执行。"""
    allowed_names = {tool.name for tool in selected_tools}
    if not allowed_names:
        return []

    filtered = [tc for tc in tool_calls if tc.get("name") in allowed_names]
    dropped = [
        tc.get("name") for tc in tool_calls if tc.get("name") not in allowed_names
    ]
    if dropped:
        logger.warning(
            "过滤未绑定工具调用 | dropped=%s | allowed=%s",
            dropped,
            sorted(allowed_names),
        )
    return filtered
