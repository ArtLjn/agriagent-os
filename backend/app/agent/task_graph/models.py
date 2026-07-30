"""Agent Task Graph 通用数据契约。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.agent.task_types import TaskType

FactSourceKind = Literal[
    "user_input", "tool_result", "memory", "rag", "derived", "system"
]
PlanIROp = Literal[
    "query",
    "calculate",
    "synthesize",
    "branch",
    "parallel",
    "approval",
    "wait",
    "merge",
]
SideEffect = Literal["none", "pending_only", "write"]
FailurePolicy = Literal["repair", "ask_user", "skip", "hard_fail"]
OperatorType = Literal[
    "CAPABILITY", "IF", "FOR", "MAP", "PARALLEL", "WAIT", "APPROVAL", "MERGE"
]
ExecutionStatus = Literal[
    "created", "running", "paused", "waiting_user", "cancelled", "completed", "failed"
]
WaitingFor = Literal["slot", "confirmation", "external_result"]


class TraceableModel(BaseModel):
    """提供稳定 trace 序列化的基础模型。"""

    def to_trace_payload(self) -> dict[str, Any]:
        return _redact_payload(self.model_dump(mode="python"))


class FactSource(TraceableModel):
    kind: FactSourceKind
    ref: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class PlanningSlot(TraceableModel):
    name: str
    value: Any
    source: FactSource
    normalized_unit: str | None = None


class PlanningSlotSet(TraceableModel):
    task_type: TaskType
    slots: dict[str, PlanningSlot] = Field(default_factory=dict)
    missing_required_slots: list[str] = Field(default_factory=list)


class RawContext(TraceableModel):
    request_id: str
    session_id: str | None = None
    user_id: str | None = None
    memory_refs: list[Any] = Field(default_factory=list)
    history_refs: list[Any] = Field(default_factory=list)
    rag_refs: list[Any] = Field(default_factory=list)
    db_refs: list[Any] = Field(default_factory=list)
    tool_cache_refs: list[Any] = Field(default_factory=list)
    runtime_refs: list[Any] = Field(default_factory=list)
    trace_metadata: dict[str, Any] = Field(default_factory=dict)


class PlanningContext(TraceableModel):
    request_id: str
    session_id: str | None = None
    user_id: str | None = None
    task_type: TaskType
    slots: PlanningSlotSet
    context_summary: dict[str, Any] = Field(default_factory=dict)
    recent_task_refs: list[str] = Field(default_factory=list)
    facts: dict[str, PlanningSlot] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    risk_policy: dict[str, Any] = Field(default_factory=dict)


class PlanIRStep(TraceableModel):
    step_id: str
    op: PlanIROp
    capability: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    needs: list[str] = Field(default_factory=list)
    when: str | None = None
    optional: bool = False
    side_effect: SideEffect = "none"


class PlanIR(TraceableModel):
    ir_id: str
    task_type: TaskType
    intent: str
    planner_version: str
    context_hash: str
    steps: list[PlanIRStep] = Field(default_factory=list)
    response_contract: str


class NodeContract(TraceableModel):
    input_types: list[str] = Field(default_factory=list)
    output_type: str
    required_slots: list[str] = Field(default_factory=list)
    side_effect: SideEffect = "none"
    failure_policy: FailurePolicy = "repair"


class CapabilityInvocation(TraceableModel):
    capability: str
    operation: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    adapter_hint: str | None = None


class OperatorInvocation(TraceableModel):
    operator: OperatorType
    args: dict[str, Any] = Field(default_factory=dict)
    capability_invocation: CapabilityInvocation | None = None


class TaskGraphNode(TraceableModel):
    node_id: str
    label: str
    source_ir_step_id: str | None = None
    invocation: OperatorInvocation
    contract: NodeContract
    depends_on: list[str] = Field(default_factory=list)
    optional: bool = False


class TaskGraph(TraceableModel):
    graph_id: str
    source_ir_id: str
    task_type: TaskType
    planner_version: str
    context_hash: str
    nodes: list[TaskGraphNode] = Field(default_factory=list)
    response_contract: str


class CompileResult(TraceableModel):
    ir_id: str
    graph: TaskGraph
    compile_warnings: list[str] = Field(default_factory=list)
    contract_errors: list[str] = Field(default_factory=list)


class PlannerDecision(TraceableModel):
    task_type: TaskType
    rule_planner_version: str
    llm_planner_version: str | None = None
    plan_ir: PlanIR
    compile_result: CompileResult
    required_slot_questions: list[str] = Field(default_factory=list)
    hard_constraints_applied: list[str] = Field(default_factory=list)
    llm_used_for: list[str] = Field(default_factory=list)


class ExecutionState(TraceableModel):
    execution_id: str
    graph_id: str
    status: ExecutionStatus = "created"
    current_node_id: str | None = None
    checkpoint_id: str | None = None
    completed_node_ids: list[str] = Field(default_factory=list)
    failed_node_ids: list[str] = Field(default_factory=list)
    dead_node_ids: list[str] = Field(default_factory=list)
    skipped_node_ids: list[str] = Field(default_factory=list)
    retry_counts: dict[str, int] = Field(default_factory=dict)
    visited_node_ids: list[str] = Field(default_factory=list)
    pause_reason: str | None = None
    waiting_for: WaitingFor | None = None
    timeout_at: str | None = None
    last_error_code: str | None = None

    @model_validator(mode="after")
    def _validate_blocked_state_context(self) -> ExecutionState:
        if self.status == "waiting_user" and self.waiting_for is None:
            raise ValueError("waiting_user 状态必须携带 waiting_for")
        if self.status == "paused" and not self.pause_reason:
            raise ValueError("paused 状态必须携带 pause_reason")
        if self.status != "waiting_user" and self.waiting_for is not None:
            raise ValueError("非 waiting_user 状态不能携带 waiting_for")
        if self.status != "paused" and self.pause_reason:
            raise ValueError("非 paused 状态不能携带 pause_reason")
        return self

    def retry_limit_exceeded(self, node_id: str, max_retries: int) -> bool:
        return self.retry_counts.get(node_id, 0) > max_retries


class NodeResult(TraceableModel):
    node_id: str
    status: Literal["success", "skipped", "needs_user", "failed"]
    output_type: str | None = None
    output: dict[str, Any] | None = None
    facts: dict[str, PlanningSlot] = Field(default_factory=dict)
    error_code: str | None = None


class ValidationResult(TraceableModel):
    status: Literal["pass", "repair", "ask_user", "fail"]
    reasons: list[str] = Field(default_factory=list)
    accepted_facts: dict[str, PlanningSlot] = Field(default_factory=dict)
    rejected_facts: dict[str, str] = Field(default_factory=dict)


class PlanRewriteRequest(TraceableModel):
    graph_id: str
    execution_id: str
    source_ir_id: str
    failed_node_id: str
    reason_code: str
    available_context: PlanningContext
    runtime_state: ExecutionState
    prior_results: list[NodeResult] = Field(default_factory=list)


class EvaluationReport(TraceableModel):
    evaluation_id: str
    request_id: str
    task_type: TaskType
    planner_version: str
    slot_score: float = Field(ge=0.0, le=1.0)
    plan_ir_valid: bool
    graph_compile_success: bool
    contract_pass_rate: float = Field(ge=0.0, le=1.0)
    capability_success_rate: float = Field(ge=0.0, le=1.0)
    repair_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    hallucination_count: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    token_count: int = Field(ge=0)
    capability_metrics: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_capability_metrics(self) -> EvaluationReport:
        for capability, metrics in self.capability_metrics.items():
            if "success" not in metrics or not isinstance(metrics["success"], bool):
                raise ValueError(
                    f"{capability} capability_metrics 必须包含布尔 success"
                )
        return self


_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}
_SENSITIVE_SINGLE_PARTS = {"authorization", "credential", "password", "secret", "token"}


def _redact_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _redact_payload(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _is_sensitive_key(key) else _redact_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple | set):
        return [_redact_payload(item) for item in value]
    if isinstance(value, datetime):
        normalized = (
            value.astimezone(timezone.utc)
            if value.tzinfo
            else value.replace(tzinfo=timezone.utc)
        )
        return normalized.isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if callable(value):
        return f"<callable:{getattr(value, '__name__', type(value).__name__)}>"
    if isinstance(value, type):
        return f"<type:{value.__name__}>"
    return f"<{type(value).__name__}>"


def _is_sensitive_key(key: Any) -> bool:
    normalized = _normalize_key(str(key))
    if normalized in _SENSITIVE_KEYS:
        return True
    parts = set(normalized.split("_"))
    if parts & _SENSITIVE_SINGLE_PARTS:
        return True
    return {"api", "key"}.issubset(parts)


def _normalize_key(key: str) -> str:
    camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key.strip())
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", camel_split).strip("_").lower()
    return normalized
