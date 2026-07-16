"""兼容入口：Tool 预筛选已迁移到 app.agent.router.tool_selector。"""

from app.agent.router.tool_selector import (
    ToolSelectionResult,
    expand_by_chain,
    select_tools,
)
from app.agent.router.rules import QUERY_TRIGGERS, TOOL_CHAIN_MAP, WRITE_PATTERNS

__all__ = [
    "QUERY_TRIGGERS",
    "TOOL_CHAIN_MAP",
    "ToolSelectionResult",
    "WRITE_PATTERNS",
    "expand_by_chain",
    "select_tools",
]
