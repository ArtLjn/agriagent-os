"""工具结果直返与工具调用白名单过滤。"""

import logging

from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)

DIRECT_RETURN_TOOLS: set[str] = {
    "get_debt_summary",
    "get_workers",
}


def can_return_direct_tool_messages(messages: list[ToolMessage]) -> bool:
    """判断直达工具结果是否可以绕过最终 LLM。"""
    for msg in messages:
        tool_name = getattr(msg, "name", None)
        if not tool_name:
            tool_call_id = str(getattr(msg, "tool_call_id", ""))
            if not tool_call_id.startswith("direct_"):
                return False
            tool_name = tool_call_id.removeprefix("direct_")
        if tool_name not in DIRECT_RETURN_TOOLS:
            return False
    return True


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
