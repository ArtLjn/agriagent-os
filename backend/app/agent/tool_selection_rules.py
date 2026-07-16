"""兼容入口：Tool 选择规则已迁移到 app.agent.router.rules。"""

from app.agent.router.rules import (
    DISABLED_SKILLS,
    PLANTING_ADVICE_HINTS,
    QUERY_INTENT_HINTS,
    QUERY_TRIGGERS,
    TOOL_CHAIN_MAP,
    WRITE_INTENT_HINTS,
    WRITE_PATTERNS,
)

__all__ = [
    "DISABLED_SKILLS",
    "PLANTING_ADVICE_HINTS",
    "QUERY_INTENT_HINTS",
    "QUERY_TRIGGERS",
    "TOOL_CHAIN_MAP",
    "WRITE_INTENT_HINTS",
    "WRITE_PATTERNS",
]
