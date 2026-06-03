"""Agent Planner 数据模型。"""

from dataclasses import dataclass, field
from typing import Any, Literal

PlanIntent = Literal["greeting", "query", "write", "agent"]


@dataclass(frozen=True)
class ToolCandidatePlan:
    """工具候选计划。"""

    intent: PlanIntent
    selected_tools: list[str] = field(default_factory=list)
    expanded_tools: list[str] = field(default_factory=list)
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
