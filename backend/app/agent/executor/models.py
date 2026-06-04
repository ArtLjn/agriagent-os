"""Agent Executor 数据模型。"""

from dataclasses import dataclass, field
from typing import Any, Literal

ToolPermissionLevel = Literal["read", "write"]
PendingActionStatus = Literal[
    "unhandled",
    "confirmed",
    "canceled",
    "modified",
    "failed",
]


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


@dataclass(frozen=True)
class PendingActionDecision:
    """Pending action 处理决策。"""

    handled: bool
    status: PendingActionStatus
    reply: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def unhandled(cls) -> "PendingActionDecision":
        return cls(handled=False, status="unhandled")

    @classmethod
    def confirmed(
        cls,
        reply: str,
        metadata: dict[str, Any] | None = None,
    ) -> "PendingActionDecision":
        return cls(
            handled=True,
            status="confirmed",
            reply=reply,
            metadata=metadata or {},
        )

    @classmethod
    def canceled(cls, reply: str = "已取消操作。") -> "PendingActionDecision":
        return cls(handled=True, status="canceled", reply=reply)

    @classmethod
    def modified(cls) -> "PendingActionDecision":
        return cls(handled=False, status="modified")

    @classmethod
    def failed(cls, reply: str) -> "PendingActionDecision":
        return cls(handled=True, status="failed", reply=reply)
