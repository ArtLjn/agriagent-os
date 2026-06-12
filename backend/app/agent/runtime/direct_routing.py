"""确定性读工具直达路由规则。"""

import re
import logging

from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)

DIRECT_READ_TOOLS: set[str] = {
    "get_weather_forecast",
    "get_cost_summary",
    "get_debt_summary",
    "get_farm_status",
    "get_workers",
}

DIRECT_RETURN_TOOLS: set[str] = {
    "get_debt_summary",
    "get_workers",
}


def direct_query_tool_names(user_msg: str, selected_names: list[str]) -> list[str]:
    """返回可跳过 LLM 工具选择的读工具名称。"""
    names = list(selected_names)
    if (
        "get_crop_cycle_info" in names
        and "get_farm_status" in names
        and not mentions_cycle_id(user_msg)
    ):
        return ["get_farm_status"]
    return [name for name in names if name in DIRECT_READ_TOOLS]


def direct_query_tool_args(user_msg: str, tool_name: str) -> dict:
    """返回确定性直达工具的参数补全。"""
    if tool_name == "get_debt_summary" and wants_total_payable(user_msg):
        return {"scope": "total_payable"}
    return {}


def can_direct_route(
    user_msg: str, selected_names: list[str], direct_names: list[str]
) -> bool:
    if len(direct_names) == len(selected_names):
        return True
    return (
        direct_names == ["get_farm_status"]
        and set(selected_names) == {"get_crop_cycle_info", "get_farm_status"}
        and not mentions_cycle_id(user_msg)
    )


def can_skip_llm_tool_selection(
    *,
    user_msg: str,
    tools: list,
    selected_names: list[str],
    direct_names: list[str],
) -> bool:
    if selected_names and len(direct_names) == len(selected_names):
        return True
    if len(tools) == 1 or len(selected_names) < len(tools):
        return True
    return (
        direct_names == ["get_farm_status"]
        and set(selected_names) == {"get_crop_cycle_info", "get_farm_status"}
        and not mentions_cycle_id(user_msg)
    )


def mentions_cycle_id(user_msg: str) -> bool:
    """判断用户是否明确给出茬口/周期 ID。"""
    pattern = r"(?:茬口|周期|cycle)\s*\d+|\d+\s*(?:号|#)?\s*(?:茬口|周期)"
    return bool(re.search(pattern, user_msg))


def wants_total_payable(user_msg: str) -> bool:
    """判断用户是否在问普通赊账+未付人工的总欠款。"""
    if any(keyword in user_msg for keyword in ("人工", "工钱", "工资", "赊账")):
        return False
    return bool(
        re.search(r"(?:我)?还欠(?:多少钱|多少|啥|什么)?", user_msg)
        or any(
            keyword in user_msg for keyword in ("总欠款", "全部欠款", "欠别人多少钱")
        )
    )


def can_return_direct_tool_messages(messages: list[ToolMessage]) -> bool:
    """判断直达工具结果是否可以绕过最终 LLM。"""
    for msg in messages:
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
