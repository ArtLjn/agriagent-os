"""Agent 平台可观测性入口。"""

from collections import Counter
from threading import Lock

from app.shared.compatibility import StrEnum


class AgentLifecycleEvent(StrEnum):
    """Agent 平台 trace 生命周期事件。"""

    CONTEXT_BUILD = "context_build"
    PROMPT_RENDER = "prompt_render"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    MEMORY_OBSERVE = "memory_observe"
    RESPONSE_FORMAT = "response_format"
    EVALUATION_CAPTURE = "evaluation_capture"


_lock = Lock()
_counters: Counter[tuple[str, tuple[tuple[str, str], ...]]] = Counter()


def lifecycle_event_names() -> set[str]:
    """返回所有平台生命周期事件名。"""
    return {event.value for event in AgentLifecycleEvent}


def increment_counter(name: str, labels: dict[str, str] | None = None) -> None:
    """递增一个带标签的计数器。"""
    label_items = tuple(sorted((labels or {}).items()))
    with _lock:
        _counters[(name, label_items)] += 1


def get_counter(name: str, labels: dict[str, str] | None = None) -> int:
    """读取计数器值，供测试和调试使用。"""
    label_items = tuple(sorted((labels or {}).items()))
    with _lock:
        return _counters[(name, label_items)]


def reset_metrics() -> None:
    """清空进程内指标，供测试使用。"""
    with _lock:
        _counters.clear()


def session_summary_generated_total() -> int:
    """会话摘要生成成功次数。"""
    return get_counter("session_summary_generated_total")


def session_summary_skipped_total(reason: str) -> int:
    """会话摘要跳过次数。"""
    return get_counter("session_summary_skipped_total", {"reason": reason})


def session_summary_failed_total() -> int:
    """会话摘要失败次数。"""
    return get_counter("session_summary_failed_total")


__all__ = [
    "AgentLifecycleEvent",
    "get_counter",
    "increment_counter",
    "lifecycle_event_names",
    "reset_metrics",
    "session_summary_failed_total",
    "session_summary_generated_total",
    "session_summary_skipped_total",
]
