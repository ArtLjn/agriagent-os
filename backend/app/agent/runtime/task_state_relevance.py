"""早期 TaskState 相关性判断。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.context.task_state import AgentTaskState

INJECT_THRESHOLD = 0.75

_AREA_RE = re.compile(r"\d+(?:\.\d+)?\s*亩")
_SEASON_RE = re.compile(r"(春季|夏季|秋季|冬季|春茬|夏茬|秋茬|冬茬)")
_UNIT_NAME_RE = re.compile(
    r"(?:叫|名称叫|名字叫|命名为|取名为)\s*([\u4e00-\u9fffA-Za-z0-9_-]{1,20})"
)
_BYPASS_RE = re.compile(
    r"(天气|气温|温度|下雨|降雨|雨量|风力|浇水|设置|账号|密码|登录|你是谁|"
    r"叫什么|开玩笑|闲聊|随便聊|讲个笑话|你好|早上好|晚上好)"
)
_SHORT_CONTINUE_RE = re.compile(
    r"^(继续|再试一下|确认|确定|可以|可以了|执行吧|创建吧)[。！？!?.,，、]*$"
)
_TASK_ACTION_CONTINUE_RE = re.compile(
    r"(确认(?:创建|执行)|按刚才(?:的方案)?(?:创建|执行)?|"
    r"就这样|按这个来|照这个做|执行吧|创建吧)"
)


@dataclass(frozen=True)
class TaskStateRelevanceDecision:
    """TaskState 注入决策。"""

    score: float
    decision: str
    reason: str
    should_inject: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "decision": self.decision,
            "reason": self.reason,
            "should_inject": self.should_inject,
        }


def task_state_payload(task: AgentTaskState | dict[str, Any] | None) -> dict | None:
    """把持久化任务状态转换成 trace/runtime 可序列化 payload。"""
    if task is None:
        return None
    if isinstance(task, dict):
        return dict(task)
    expires_at = getattr(task, "expires_at", None)
    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "goal": task.goal,
        "status": task.status,
        "entities": _json_value(task.entities_json, default={}),
        "observations": _json_value(task.observations_json, default=[]),
        "missing_information": _json_value(
            task.missing_information_json,
            default=[],
        ),
        "next_action": task.next_action,
        "expires_at": expires_at.isoformat()
        if isinstance(expires_at, datetime)
        else "",
    }


def evaluate_task_state_relevance(
    user_input: str,
    active_task: dict | None,
) -> TaskStateRelevanceDecision:
    """判断当前输入是否应承接 active task。"""
    if not active_task:
        return _decision(0.0, "no_active_task", "没有可恢复任务")

    normalized = _normalize(user_input)
    if not normalized:
        return _decision(0.0, "do_not_inject", "用户输入为空")
    if _looks_like_continuation(normalized):
        return _decision(0.9, "inject", "命中任务承接/确认表达")
    if _matches_missing_information(normalized, active_task):
        return _decision(0.85, "inject", "用户输入匹配当前任务缺失信息")
    if _looks_like_bypass_query(normalized):
        return _decision(0.1, "do_not_inject", "命中独立旁路查询")

    return _decision(0.45, "low_priority", "存在 active task，但缺少明确承接信号")


def task_state_routing_input(user_input: str, active_task: dict | None) -> str:
    """构造仅供早期 router/plan draft 使用的任务感知输入。"""
    if not active_task:
        return user_input
    lines = [f"当前任务：{active_task.get('task_type') or ''}"]
    missing = _format_list(active_task.get("missing_information"))
    if missing:
        lines.append(f"缺失信息：{missing}")
    entities = _format_entities(active_task.get("entities"))
    if entities:
        lines.append(f"已知实体：{entities}")
    next_action = str(active_task.get("next_action") or "").strip()
    if next_action:
        lines.append(f"下一步动作：{next_action}")
    lines.append(f"用户输入：{user_input}")
    return "\n".join(lines)


def routing_input_for_task_state(state: dict, user_input: str) -> str:
    """按 relevance 结果返回 router/plan 应使用的输入文本。"""
    relevance = state.get("task_state_relevance")
    should_inject = bool(
        isinstance(relevance, dict) and relevance.get("should_inject") is True
    )
    if not should_inject:
        return user_input
    prepared = state.get("task_state_routing_input")
    if isinstance(prepared, str) and prepared.strip():
        return prepared
    active_task = state.get("active_task_state")
    if not isinstance(active_task, dict):
        return user_input
    return task_state_routing_input(user_input, active_task)


def _decision(score: float, decision: str, reason: str) -> TaskStateRelevanceDecision:
    return TaskStateRelevanceDecision(
        score=score,
        decision=decision,
        reason=reason,
        should_inject=score >= INJECT_THRESHOLD and decision == "inject",
    )


def _json_value(value: Any, *, default: Any) -> Any:
    if value is None:
        return default
    return value


def _normalize(text: str) -> str:
    return "".join(str(text or "").split())


def _looks_like_bypass_query(normalized: str) -> bool:
    return bool(_BYPASS_RE.search(normalized))


def _looks_like_continuation(normalized: str) -> bool:
    stripped = re.sub(r"^(你好|您好)[。！？!?.,，、]*", "", normalized)
    return bool(
        _SHORT_CONTINUE_RE.match(stripped)
        or _TASK_ACTION_CONTINUE_RE.search(normalized)
    )


def _matches_missing_information(normalized: str, active_task: dict) -> bool:
    missing = _missing_text(active_task)
    if not missing:
        return False
    if any(key in missing for key in ("面积", "亩")) and _AREA_RE.search(normalized):
        return True
    if any(key in missing for key in ("季节", "茬口")) and _SEASON_RE.search(
        normalized
    ):
        return True
    if any(key in missing for key in ("种植单元名称", "地块名称", "名称")):
        return bool(
            _UNIT_NAME_RE.search(normalized) or _looks_like_short_unit_name(normalized)
        )
    return False


def _missing_text(active_task: dict) -> str:
    missing = active_task.get("missing_information")
    if isinstance(missing, list):
        return "；".join(str(item) for item in missing)
    return str(missing or "")


def _looks_like_short_unit_name(normalized: str) -> bool:
    return len(normalized) <= 12 and any(
        hint in normalized for hint in ("棚", "田", "地", "区")
    )


def _format_list(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    return "；".join(str(item) for item in value if item not in (None, ""))


def _format_entities(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    parts = []
    for key, item in value.items():
        if isinstance(item, dict | list):
            continue
        parts.append(f"{key}={item}")
    return "；".join(parts)


__all__ = [
    "TaskStateRelevanceDecision",
    "evaluate_task_state_relevance",
    "routing_input_for_task_state",
    "task_state_payload",
    "task_state_routing_input",
]
