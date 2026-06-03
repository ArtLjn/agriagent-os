"""Agent Executor 数据模型。"""

from dataclasses import dataclass, field
from typing import Any, Literal

ToolPermissionLevel = Literal["read", "write"]


@dataclass(frozen=True)
class ToolExecutionPlan:
    """一次工具执行计划。"""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    permission_level: ToolPermissionLevel = "read"
    requires_confirmation: bool = False


@dataclass(frozen=True)
class ToolExecutionResult:
    """工具执行结果摘要。"""

    name: str
    status: Literal["success", "pending", "error"]
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
