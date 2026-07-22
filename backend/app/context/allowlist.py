# backend/app/context/allowlist.py
"""ContextBundle 注入字段白名单契约。

设计原则（见 13_Agent范式规范化设计.md §5.9.2）：
- 只承载身份、指针、状态、偏好
- 禁止承载可被询问的查询答案（天气、农场状态、茬口详情等）
"""

ALLOWED_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        # 身份/指针
        "farm_profile",
        "farm",
        "user_profile",
        "session_meta",
        "current_crop_cycle_pointer",  # 只放 ID，不放详情
        "cycle",
        "ledger",
        "rag_knowledge",
        # 状态
        "active_task_state",
        "temporary_task_state",
        "pending_action_pointer",
        "pending_plan_pointer",
        "last_confirmed_at",
        # 偏好
        "user_settings",
        "assistant_role",
        "short_term_recent",
        "long_term_memory",
    }
)

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
    return key in ALLOWED_CONTEXT_KEYS


__all__ = [
    "ALLOWED_CONTEXT_KEYS",
    "FORBIDDEN_CONTEXT_KEYS",
    "is_allowed_key",
]
