"""兼容入口：Tool 预筛选已迁移到 app.agent.router.tool_selector。"""

from app.agent.router.tool_selector import (
    ToolSelectionResult,
    expand_by_chain,
    select_tools,
)
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
    "ToolSelectionResult",
    "WRITE_INTENT_HINTS",
    "WRITE_PATTERNS",
    "expand_by_chain",
    "select_tools",
]
