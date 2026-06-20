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
EXTERNAL_DATA_TERMS = (
    "今天",
    "天气",
    "气温",
    "降雨",
    "下雨",
    "适合",
    "实时",
    "现在",
    "当前",
    "查一下",
    "查询",
)
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
DISABLED_WORKER_STATUS_TERMS = (
    "inactive",
    "disabled",
    "deactivated",
    "已停用",
    "停用",
    "离职",
)
WORKER_FIELD_KEYS = (
    "worker",
    "workers",
    "worker_name",
    "worker_names",
    "labor_entries",
)
WAGE_FIELD_KEYS = (
    "unit_price",
    "default_unit_price",
    "paid_amount",
    "payable_amount",
    "unpaid_amount",
)
NO_WAGE_FIELD_KEYS = ("no_wage", "wage_policy")
NO_WAGE_VALUES = ("none", "no_wage", "free", "不计工资", "无工资")
WORK_ORDER_TOOLS = ("create_operation_work_order", "manage_wages")


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
    user_input_preview = _evidence_text(user_input)
    selected_tools_text = ", ".join(selected_tools) if selected_tools else "无"

    if (
        _needs_external_data(user_input)
        and not selected_tools
        and not successful_tools
        and not failed_tools
    ):
        candidates.append(
            _candidate(
                "wrong_tool_selection",
                "high",
                f"用户输入「{user_input_preview}」需要实时/外部数据，但 router 没有选择任何工具",
                user_input_preview,
                "wrong_tool_selection",
            )
        )
    if _claims_execution(assistant_reply) and not write_successful:
        candidates.append(
            _candidate(
                "hallucinated_execution",
                "high",
                f"回复声称已执行写入，但选中工具「{selected_tools_text}」未成功调用",
                selected_tools_text,
                "hallucinated_execution",
            )
        )
    if _is_question(user_input) and write_selected:
        write_text = ", ".join(write_selected)
        candidates.append(
            _candidate(
                "unsafe_write_on_question",
                "high",
                f"用户是查询/确认类问题「{user_input_preview}」，但 router 选择了写操作工具「{write_text}」",
                write_text,
                "pending_missed",
            )
        )
    missing_pending = [
        tool
        for tool in write_selected
        if write_successful and tool not in pending_tools
    ]
    if missing_pending:
        missing_text = ", ".join(missing_pending)
        candidates.append(
            _candidate(
                "pending_missed",
                "high",
                f"router 选择了写操作工具「{missing_text}」，但 pending lifecycle 中没有对应的确认计划",
                missing_text,
                "pending_missed",
            )
        )
    disabled_workers = _disabled_worker_evidence(events)
    if disabled_workers:
        workers_text = ", ".join(disabled_workers)
        candidates.append(
            _candidate(
                "disabled_worker_used",
                "high",
                f"已停用工人「{workers_text}」仍被安排到作业或工资记录中",
                workers_text,
                "disabled_worker_used",
            )
        )

    missing_wage_workers = _missing_wage_evidence(events)
    if missing_wage_workers:
        workers_text = ", ".join(missing_wage_workers)
        candidates.append(
            _candidate(
                "missing_wage",
                "high",
                f"作业包含工人「{workers_text}」，但没有工资单价、已付金额、不计工资或欠款策略",
                workers_text,
                "missing_wage",
            )
        )
    if failed_tools and _claims_execution(assistant_reply):
        failed_text = ", ".join(failed_tools)
        candidates.append(
            _candidate(
                "tool_error_ignored",
                "medium",
                f"工具「{failed_text}」调用失败后，回复仍呈现为已完成",
                failed_text,
                "tool_error_ignored",
            )
        )
    sensitive_hit = _sensitive_hit(assistant_reply)
    if sensitive_hit:
        candidates.append(
            _candidate(
                "sensitive_info_leak",
                "critical",
                f"回复疑似暴露内部信息（命中关键词「{sensitive_hit}」）",
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
            tools.update(
                str(step["skill_name"]) for step in steps if step.get("skill_name")
            )
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


def _needs_external_data(user_input: str | None) -> bool:
    return bool(user_input and any(term in user_input for term in EXTERNAL_DATA_TERMS))


def _evidence_text(value: str | None) -> str:
    text = (value or "").strip()
    return text[:80] if text else "no user input"


def _sensitive_hit(reply: str | None) -> str | None:
    if not reply:
        return None
    lower_reply = reply.lower()
    return next((term for term in SENSITIVE_REPLY_TERMS if term in lower_reply), None)


def _disabled_worker_evidence(events: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for event in events:
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if not _is_worker_write_payload(payload):
            continue
        names.extend(_disabled_worker_names(payload))
    return _unique(names)


def _missing_wage_evidence(events: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for event in events:
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if not _is_work_order_payload(payload):
            continue
        if _has_wage_policy(payload):
            continue
        worker_names = _worker_names(payload)
        if worker_names:
            names.extend(worker_names)
    return _unique(names)


def _is_worker_write_payload(payload: dict[str, Any]) -> bool:
    tool_name = str(payload.get("tool_name") or "").lower()
    return tool_name in WORK_ORDER_TOOLS or tool_name == "manage_workers"


def _is_work_order_payload(payload: dict[str, Any]) -> bool:
    tool_name = str(payload.get("tool_name") or "").lower()
    return tool_name in WORK_ORDER_TOOLS


def _disabled_worker_names(value: Any) -> list[str]:
    if isinstance(value, dict):
        status = _status_text(value)
        current_name = _name_text(value)
        names: list[str] = []
        if status and _is_disabled_status(status):
            names.append(current_name or status)
        for item in value.values():
            names.extend(_disabled_worker_names(item))
        return names
    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            names.extend(_disabled_worker_names(item))
        return names
    return []


def _worker_names(value: Any) -> list[str]:
    if isinstance(value, dict):
        names: list[str] = []
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in WORKER_FIELD_KEYS and isinstance(item, str):
                names.extend(_split_names(item))
            elif key_text in {"name", "worker_name"} and isinstance(item, str):
                names.extend(_split_names(item))
            else:
                names.extend(_worker_names(item))
        return names
    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            names.extend(_worker_names(item))
        return names
    return []


def _has_wage_policy(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in WAGE_FIELD_KEYS and item not in (None, "", 0, "0"):
                return True
            if key_text in NO_WAGE_FIELD_KEYS and _is_no_wage_value(item):
                return True
            if _has_wage_policy(item):
                return True
        return False
    if isinstance(value, list):
        return any(_has_wage_policy(item) for item in value)
    return False


def _status_text(value: dict[str, Any]) -> str | None:
    for key in ("status", "worker_status", "state"):
        if value.get(key) not in (None, ""):
            return str(value[key])
    return None


def _name_text(value: dict[str, Any]) -> str | None:
    for key in ("worker_name", "name"):
        if value.get(key) not in (None, ""):
            return str(value[key]).strip()
    return None


def _is_disabled_status(value: str) -> bool:
    normalized = value.lower()
    return any(term in normalized for term in DISABLED_WORKER_STATUS_TERMS)


def _is_no_wage_value(value: Any) -> bool:
    if value is True:
        return True
    normalized = str(value or "").strip().lower()
    return normalized in NO_WAGE_VALUES


def _split_names(value: str) -> list[str]:
    separators = [",", "，", "、", ";", "；"]
    text = value
    for separator in separators:
        text = text.replace(separator, ",")
    return [item.strip() for item in text.split(",") if item.strip()]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
