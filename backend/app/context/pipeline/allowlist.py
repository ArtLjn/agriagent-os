# backend/app/context/allowlist.py
"""ContextBundle 注入字段白名单契约。

设计原则（见 13_Agent范式规范化设计.md §5.9.2）：
- 只承载身份、指针、状态、偏好
- 禁止承载可被询问的查询答案（天气、农场状态、茬口详情等）
"""

from app.context.core.registry import prompt_allowed_keys


ALLOWED_CONTEXT_KEYS: frozenset[str] = prompt_allowed_keys()

FORBIDDEN_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "weather_snapshot",
        "weather_summary",
        "farm_status_snapshot",
        "crop_cycle_details",
        "crop_stage_details",
        "recent_logs_summary",
        "worker_list_snapshot",
        "cost_summary_snapshot",
        "debt_summary_snapshot",
        "labor_payables_snapshot",
    }
)


def is_allowed_key(key: str) -> bool:
    """判断 block key 是否允许注入 ContextBundle。"""
    if key in FORBIDDEN_CONTEXT_KEYS:
        return False
    return key in ALLOWED_CONTEXT_KEYS


__all__ = [
    "ALLOWED_CONTEXT_KEYS",
    "FORBIDDEN_CONTEXT_KEYS",
    "is_allowed_key",
]
