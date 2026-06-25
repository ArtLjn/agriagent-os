"""数据飞轮 LLM judge service primitives。"""

import json
import math
from typing import Any, Protocol

DEBUG_EXPORT_REQUEST_ID_LIMIT = 20
ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}
ALLOWED_JUDGE_LABELS = {
    "good_reply",
    "bad_reply",
    "wrong_tool_selection",
    "tool_parameter_mismatch",
    "pending_missed",
    "hallucinated_execution",
    "tool_error_ignored",
    "missing_wage",
    "disabled_worker_used",
    "needs_regression",
    "off_topic",
    "sensitive_info_leak",
    "unclear_intent",
    "not_actionable",
}
DEFAULT_PROMPT_VERSION = "data-flywheel-prelabel-v1"
JUDGE_SYSTEM_PROMPT = (
    "你是 Agent 数据飞轮质量预标注 judge。"
    "只返回 JSON，不要返回 Markdown。"
    "所有自然语言字段必须使用简体中文，包括 root_cause、reason、recommended_fix。"
    "不要使用英文解释。"
)
LABEL_DEFINITIONS = {
    "good_reply": "好回复：回答准确、完整，工具使用和事实依据都没有明显问题。",
    "bad_reply": "坏回复：整体回答不可接受，但无法归入更具体的问题标签。",
    "wrong_tool_selection": "工具选错：该用工具未用、用了错误工具，或实时/外部数据问题未选择查询工具。",
    "tool_parameter_mismatch": "工具参数不匹配：工具参数、实体、数量或作用域与用户意图/上下文不一致。",
    "pending_missed": "pending 漏拦截：写操作缺少用户确认计划或确认流程。",
    "hallucinated_execution": "幻觉执行：没有成功写操作证据却声称已经创建、安排、保存、删除等。",
    "tool_error_ignored": "工具错误被忽略：工具失败后回复仍当作成功处理。",
    "missing_wage": "工资缺失：涉及工人作业但缺少工资、欠款或不计工资策略。",
    "disabled_worker_used": "禁用工人：已停用/离职工人仍被安排作业或工资。",
    "needs_regression": "需要回归：适合沉淀为仿真或评测回放用例。",
    "off_topic": "答非所问：回复没有回应用户主要意图。",
    "sensitive_info_leak": "参数/提示泄露：回复泄露系统提示、密钥、模型参数等敏感信息。",
    "unclear_intent": "意图不清：用户输入本身无法判断，应追问澄清。",
    "not_actionable": "暂不处理：证据不足或问题不稳定，暂时不进入质量问题池。",
}
LABEL_SELECTION_RULES = (
    "优先使用 issue_candidates.suggested_label。"
    "当用户需要天气、今天、实时、外部数据或数据库查询，但 selected_tools 和 actual_tools 都为空时，"
    "优先选择 wrong_tool_selection，不要选择 not_actionable。"
    "只有在没有明确质量问题、也没有可执行改进方向时才选择 not_actionable。"
    "如果回复本身失败或泛化道歉导致用户意图未解决，至少选择 bad_reply；"
    "若根因是工具未选或选错，则同时选择 wrong_tool_selection。"
    "如果问题是批量范围、实体、数量、金额或指代上下文被错误收窄，选择 tool_parameter_mismatch。"
)


class DataFlywheelJudgeClient(Protocol):
    """LLM judge 客户端协议。"""

    judge_model: str
    prompt_version: str

    def judge(self, payload: dict[str, Any]) -> dict[str, Any]:
        """返回原始 judge JSON。"""


class OpenAIDataFlywheelJudgeClient:
    """使用 OpenAI-compatible chat completions 调用 DataFlywheel judge。"""

    def __init__(
        self,
        *,
        client: Any,
        judge_model: str,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
    ) -> None:
        self._client = client
        self.judge_model = judge_model
        self.prompt_version = prompt_version

    def judge(self, payload: dict[str, Any]) -> dict[str, Any]:
        """调用 LLM 并解析 JSON judge 输出。"""
        response = self._client.chat.completions.create(
            model=self.judge_model,
            messages=[
                {
                    "role": "system",
                    "content": JUDGE_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        try:
            raw = json.loads(_completion_content(response))
        except json.JSONDecodeError:
            return {}
        return raw if isinstance(raw, dict) else {}


def build_judge_input(detail: dict[str, Any]) -> dict[str, Any]:
    """从 sample detail 构造 judge 输入。"""
    sample = detail.get("sample") or {}
    router_decision = detail.get("router_decision") or {}
    tool_events = _list_value(detail.get("tool_events"))
    pending_lifecycle = _list_value(detail.get("pending_lifecycle"))
    messages = _list_value(detail.get("messages"))

    return {
        "task": "judge_agent_turn_quality",
        "prompt_version": DEFAULT_PROMPT_VERSION,
        "judge_instructions": (
            "请基于 sample 与 debug_evidence 判断该 Agent turn 的质量问题。"
            "所有自然语言输出必须使用简体中文。"
            "labels 只能从 label_definitions 的 key 中选择。"
        ),
        "label_definitions": LABEL_DEFINITIONS,
        "label_selection_rules": LABEL_SELECTION_RULES,
        "sample": {
            "sample_id": sample.get("sample_id"),
            "sample_type": sample.get("sample_type"),
            "session_id": sample.get("session_id"),
            "turn_id": sample.get("turn_id"),
            "request_id": sample.get("request_id"),
            "user_input": _message_content(messages, "user")
            or sample.get("user_input_preview"),
            "assistant_reply": _message_content(messages, "assistant")
            or sample.get("assistant_reply_preview"),
            "selected_tools": _selected_tools(router_decision),
            "actual_tools": _actual_tools(tool_events),
            "issue_candidates": _list_value(detail.get("issue_candidates")),
        },
        "debug_evidence": {
            "router_decision": _slim_router_decision(router_decision),
            "tool_events": _slim_tool_events(tool_events),
            "pending_lifecycle": _slim_pending_lifecycle(pending_lifecycle),
            "source": _slim_source(detail.get("source")),
            "debug_export_summary": _debug_export_summary(detail.get("debug_export")),
        },
        "output_schema": {
            "type": "object",
            "required": [
                "labels",
                "root_cause",
                "severity",
                "confidence",
                "reason",
                "recommended_fix",
            ],
            "properties": {
                "labels": {"type": "array", "items": {"type": "string"}},
                "root_cause": {"type": ["string", "null"]},
                "severity": {"type": "string"},
                "confidence": {"type": "number"},
                "reason": {"type": "string"},
                "recommended_fix": {"type": ["string", "null"]},
            },
        },
    }


def normalize_judge_output(raw: Any) -> dict[str, Any]:
    """归一化 LLM judge 输出，保证可安全入库。"""
    if not isinstance(raw, dict):
        raw = {}

    labels = [
        str(label)
        for label in _list_value(raw.get("labels"))
        if str(label) in ALLOWED_JUDGE_LABELS
    ]
    if not labels:
        labels = ["not_actionable"]

    severity = str(raw.get("severity") or "medium")
    if severity not in ALLOWED_SEVERITIES:
        severity = "medium"

    reason = str(raw.get("reason") or "").strip()
    if not reason:
        reason = "LLM judge 未返回判断理由。"

    return {
        "labels": labels,
        "root_cause": _text(raw.get("root_cause")),
        "severity": severity,
        "confidence": _clamp_confidence(raw.get("confidence")),
        "reason": reason,
        "recommended_fix": _text(raw.get("recommended_fix")),
    }


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(confidence):
        return 0.0
    return max(0.0, min(1.0, confidence))


def _message_content(messages: list[Any], role: str) -> str | None:
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != role:
            continue
        content = message.get("content")
        if content:
            return str(content)
    return None


def _selected_tools(router_decision: dict[str, Any]) -> list[str]:
    tools = router_decision.get("selected_tools") or []
    if not isinstance(tools, list):
        return []
    return [str(tool) for tool in tools if tool]


def _actual_tools(tool_events: list[Any]) -> list[str]:
    tools: list[str] = []
    for event in tool_events:
        tool_name = _tool_name(event)
        if tool_name:
            tools.append(tool_name)
    return tools


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _slim_router_decision(router_decision: Any) -> dict[str, Any]:
    if not isinstance(router_decision, dict):
        return {}
    return {
        key: router_decision.get(key)
        for key in ("selected_tools", "rejected_tools", "fallback", "reason")
        if key in router_decision
    }


def _slim_tool_events(tool_events: list[Any]) -> list[dict[str, Any]]:
    slim_events: list[dict[str, Any]] = []
    for event in tool_events:
        if not isinstance(event, dict):
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        slim_events.append(
            {
                "event_type": event.get("event_type"),
                "tool_name": _tool_name(event),
                "error": payload.get("error") or event.get("error"),
                "status": payload.get("status") or event.get("status"),
            }
        )
    return slim_events


def _slim_pending_lifecycle(events: list[Any]) -> list[dict[str, Any]]:
    slim_events: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        slim_events.append(
            {
                "event_type": event.get("event_type"),
                "plan_id": payload.get("plan_id") or event.get("plan_id"),
                "status": payload.get("status") or event.get("status"),
                "skill_name": payload.get("skill_name") or event.get("skill_name"),
                "steps": _slim_pending_steps(payload.get("steps")),
            }
        )
    return slim_events


def _slim_pending_steps(steps: Any) -> list[dict[str, Any]]:
    slim_steps: list[dict[str, Any]] = []
    for step in _list_value(steps):
        if not isinstance(step, dict):
            continue
        slim_steps.append(
            {
                key: step.get(key)
                for key in ("skill_name", "status", "action")
                if key in step
            }
        )
    return slim_steps


def _slim_source(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    return {
        key: source.get(key)
        for key in (
            "event_file",
            "event_seq_start",
            "event_seq_end",
            "event_log_status",
            "chat_record_source",
            "missing_event_segments",
        )
        if key in source
    }


def _debug_export_summary(debug_export: Any) -> dict[str, Any]:
    if not isinstance(debug_export, dict):
        return {}
    turns = _list_value(debug_export.get("turns"))
    request_ids = [
        str(turn["request_id"])
        for turn in turns
        if isinstance(turn, dict) and turn.get("request_id")
    ]
    return {
        "session_id": _debug_export_session_id(debug_export),
        "turn_count": len(turns),
        "request_ids": request_ids[:DEBUG_EXPORT_REQUEST_ID_LIMIT],
    }


def _debug_export_session_id(debug_export: dict[str, Any]) -> Any:
    session = debug_export.get("session") or {}
    if not isinstance(session, dict):
        return None
    return session.get("session_id")


def _completion_content(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "".join(parts)
    return ""


def _tool_name(event: Any) -> str | None:
    if not isinstance(event, dict):
        return None
    payload = event.get("payload") or {}
    if isinstance(payload, dict) and payload.get("tool_name"):
        return str(payload["tool_name"])
    if event.get("tool_name"):
        return str(event["tool_name"])
    return None
