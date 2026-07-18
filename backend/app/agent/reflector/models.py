"""Agent Reflection 结构化模型。"""

from typing import Any

from pydantic import BaseModel, Field

from app.shared.compatibility import StrEnum


class ReflectionTrigger(StrEnum):
    PRE_WRITE_PLAN = "pre_write_plan"
    PRE_EXECUTION = "pre_execution"
    POST_TOOL_RESULT = "post_tool_result"
    PRE_FINAL_RESPONSE = "pre_final_response"
    FALLBACK_GUARD = "fallback_guard"


class ReflectionDecision(StrEnum):
    PASS = "pass"
    ASK_CLARIFICATION = "ask_clarification"
    REQUIRE_TOOL = "require_tool"
    BLOCK_WRITE = "block_write"
    RETRY_GENERATION = "retry_generation"
    FALLBACK_RESPONSE = "fallback_response"


class ReflectionSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class ReflectionIssue(BaseModel):
    code: str
    severity: ReflectionSeverity
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggested_decision: ReflectionDecision = ReflectionDecision.PASS

    def to_trace_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "evidence": self.evidence,
            "suggested_decision": self.suggested_decision.value,
        }


class ReflectionResult(BaseModel):
    trigger: ReflectionTrigger
    decision: ReflectionDecision = ReflectionDecision.PASS
    checks: list[str] = Field(default_factory=list)
    issues: list[ReflectionIssue] = Field(default_factory=list)
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def has_blocker(self) -> bool:
        return any(
            issue.severity == ReflectionSeverity.BLOCKER for issue in self.issues
        )

    @classmethod
    def passed(
        cls,
        trigger: ReflectionTrigger,
        *,
        reason: str = "反思检查通过。",
        checks: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ReflectionResult":
        return cls(
            trigger=trigger,
            decision=ReflectionDecision.PASS,
            checks=checks or [],
            reason=reason,
            metadata=metadata or {},
        )

    def to_trace_payload(self) -> dict[str, Any]:
        return {
            "trigger": self.trigger.value,
            "decision": self.decision.value,
            "reason": self.reason,
            "checks": self.checks,
            "issues": [issue.to_trace_payload() for issue in self.issues],
            "metadata": self.metadata,
        }
