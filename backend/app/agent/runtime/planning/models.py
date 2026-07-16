"""PlanDraft 领域模型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

RouteType = Literal[
    "direct_reply",
    "read_plan",
    "write_pending_action",
    "write_pending_plan",
    "clarification",
]
PlanSource = Literal["rule_gate", "llm_structured_planner", "hybrid"]
StepRisk = Literal["none", "read", "write_confirm", "write_high"]
ValidationStatus = Literal["valid", "blocked"]


@dataclass(frozen=True)
class PlanStep:
    """PlanDraft 中的一个执行步骤。"""

    step_id: str
    skill_name: str
    params: dict[str, Any] = field(default_factory=dict)
    risk: StepRisk = "none"
    depends_on: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_trace_payload(self) -> dict[str, Any]:
        """返回可序列化 trace 数据。"""
        return _redact_payload(asdict(self))


@dataclass(frozen=True)
class InferredField:
    """验证阶段推断出的字段。"""

    field_path: str
    value: Any
    source: str
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_trace_payload(self) -> dict[str, Any]:
        """返回可序列化 trace 数据。"""
        return asdict(self)


@dataclass(frozen=True)
class PlanIssue:
    """PlanDraft 验证问题。"""

    code: str
    message: str
    field_path: str | None = None
    blocking: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_trace_payload(self) -> dict[str, Any]:
        """返回可序列化 trace 数据。"""
        return asdict(self)


@dataclass(frozen=True)
class PlanValidationResult:
    """PlanDraft 验证结果。"""

    status: ValidationStatus
    safe_route_type: RouteType
    missing_fields: list[str] = field(default_factory=list)
    inferred_fields: list[InferredField] = field(default_factory=list)
    issues: list[PlanIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """是否允许继续进入原路由的执行阶段。"""
        return self.status == "valid"

    def to_trace_payload(self) -> dict[str, Any]:
        """返回可序列化 trace 数据。"""
        return asdict(self)


@dataclass(frozen=True)
class PlanDraft:
    """Agent 单轮对话的轻量规划合同。"""

    turn_id: str
    session_id: str
    farm_id: int
    raw_user_input: str
    route_type: RouteType
    steps: list[PlanStep] = field(default_factory=list)
    intent_frames: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    selected_tools: list[str] = field(default_factory=list)
    source: PlanSource = "rule_gate"
    validation: PlanValidationResult | None = None

    def to_trace_payload(self) -> dict[str, Any]:
        """返回可序列化 trace 数据。"""
        return _redact_payload(asdict(self))


_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}


def _redact_payload(value: Any) -> Any:
    """脱敏 trace payload，避免调试导出泄漏凭据。"""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_key(key) else _redact_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    return value


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key).strip().lower()
    return normalized in _SENSITIVE_KEYS
