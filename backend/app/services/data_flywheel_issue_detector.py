"""数据飞轮问题候选规则检测。"""

from typing import Any

SENSITIVE_REPLY_TERMS = (
    "api_key",
    "appsecret",
    "secret",
    "system prompt",
    "temperature",
    "top_p",
    ".env",
)
EXECUTION_CLAIMS = (
    "已创建",
    "已修改",
    "已更新",
    "已删除",
    "已记录",
    "已安排",
    "已执行",
    "已保存",
    "已结清",
)
QUESTION_TERMS = ("？", "?", "吗", "如何", "怎么", "哪些", "有没有", "查询", "查一下")
WRITE_TOOL_TERMS = (
    "create",
    "update",
    "delete",
    "manage",
    "settle",
    "confirm",
    "save",
    "add",
    "remove",
    "work_order",
    "wage",
    "labor",
    "cost",
    "log",
)


def detect_issue_candidates(
    *,
    user_input: str | None,
    assistant_reply: str | None,
    selected_tools: list[str],
    events: list[dict[str, Any]],
    pending_lifecycle: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """基于轻量规则检测需要人工确认的问题候选。"""
    candidates: list[dict[str, str]] = []
    successful_tools = _successful_tools(events)
    failed_tools = _failed_tools(events)
    write_selected = [tool for tool in selected_tools if _is_write_tool(tool)]
    write_successful = [tool for tool in successful_tools if _is_write_tool(tool)]
    pending_tools = _pending_tools(pending_lifecycle)

    if _claims_execution(assistant_reply) and not write_successful:
        candidates.append(
            _candidate(
                "hallucinated_execution",
                "high",
                "回复声称已执行写入，但没有成功的写操作工具调用",
                ", ".join(selected_tools) or "no selected tool",
                "hallucinated_execution",
            )
        )
    if _is_question(user_input) and write_selected:
        candidates.append(
            _candidate(
                "unsafe_write_on_question",
                "high",
                "用户是查询/确认类问题，但 router 选择了写操作工具",
                ", ".join(write_selected),
                "pending_missed",
            )
        )
    missing_pending = [
        tool for tool in write_selected if write_successful and tool not in pending_tools
    ]
    if missing_pending:
        candidates.append(
            _candidate(
                "pending_missed",
                "high",
                "router 选择了写操作工具，但 pending lifecycle 中没有对应的确认计划",
                ", ".join(missing_pending),
                "pending_missed",
            )
        )
    if failed_tools and _claims_execution(assistant_reply):
        candidates.append(
            _candidate(
                "tool_error_ignored",
                "medium",
                "工具调用失败后，回复仍呈现为已完成",
                ", ".join(failed_tools),
                "bad_reply",
            )
        )
    sensitive_hit = _sensitive_hit(assistant_reply)
    if sensitive_hit:
        candidates.append(
            _candidate(
                "sensitive_info_leak",
                "critical",
                "回复疑似暴露模型参数或系统提示",
                sensitive_hit,
                "sensitive_info_leak",
            )
        )
    return candidates


def _candidate(
    issue_type: str,
    severity: str,
    reason: str,
    evidence: str,
    suggested_label: str,
) -> dict[str, str]:
    return {
        "type": issue_type,
        "severity": severity,
        "reason": reason,
        "evidence": evidence,
        "suggested_label": suggested_label,
    }


def _successful_tools(events: list[dict[str, Any]]) -> list[str]:
    return _tools_by_event_type(events, "tool.call.finished")


def _failed_tools(events: list[dict[str, Any]]) -> list[str]:
    return _tools_by_event_type(events, "tool.call.failed")


def _tools_by_event_type(events: list[dict[str, Any]], event_type: str) -> list[str]:
    tools: list[str] = []
    for event in events:
        if event.get("event_type") != event_type:
            continue
        payload = event.get("payload") or {}
        if isinstance(payload, dict) and payload.get("tool_name"):
            tools.append(str(payload["tool_name"]))
    return tools


def _pending_tools(pending_lifecycle: list[dict[str, Any]]) -> set[str]:
    tools: set[str] = set()
    for event in pending_lifecycle:
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        steps = payload.get("steps")
        if isinstance(steps, list):
            tools.update(str(step["skill_name"]) for step in steps if step.get("skill_name"))
        if payload.get("skill_name"):
            tools.add(str(payload["skill_name"]))
    return tools


def _is_write_tool(tool_name: str) -> bool:
    normalized = tool_name.lower()
    return any(term in normalized for term in WRITE_TOOL_TERMS)


def _claims_execution(reply: str | None) -> bool:
    return bool(reply and any(term in reply for term in EXECUTION_CLAIMS))


def _is_question(user_input: str | None) -> bool:
    return bool(user_input and any(term in user_input for term in QUESTION_TERMS))


def _sensitive_hit(reply: str | None) -> str | None:
    if not reply:
        return None
    lower_reply = reply.lower()
    return next((term for term in SENSITIVE_REPLY_TERMS if term in lower_reply), None)
