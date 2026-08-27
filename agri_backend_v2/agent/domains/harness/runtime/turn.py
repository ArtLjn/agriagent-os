"""Turn data structure.

The Turn object flows through every pipeline node (context -> react loop ->
hitl -> tool -> reflect -> emit). Each node is a pure function `(Turn) -> Turn`.
This is the single source of truth for one user message processing.

See harness_study spec: docs/00-react-loop.md, docs/01-vertical-slice.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from agent.domains.harness.context.models import ContextBundle
from shared.roles import UserRole

TurnStatus = Literal[
    "running",  # ReAct loop iterating
    "accepted",  # 已创建，等待 Worker 领取
    "queued",  # 等待会话或全局执行槽位
    "awaiting_approval",  # Blocked on HITL gate
    "completed",  # Final answer emitted
    "terminated",  # Controlled termination, not an execution fault
    "rejected",  # User rejected HITL
    "failed",  # Error
    "cancelled",  # User cancelled
    "timeout",  # Queue or approval timeout
]


class TurnPhase(str, Enum):
    """Runtime 执行阶段，与持久化 TurnStatus 分离。"""

    SETUP = "setup"
    REASONING = "reasoning"
    TOOL_PREPARING = "tool_preparing"
    TOOL_EXECUTING = "tool_executing"
    AWAITING_APPROVAL = "awaiting_approval"
    OBSERVING = "observing"
    FINALIZING = "finalizing"
    TERMINAL = "terminal"


class StopReason(str, Enum):
    """驱动 Turn 进入终态的确定性原因。"""

    MODEL_COMPLETED = "model_completed"
    STEP_BUDGET_EXHAUSTED = "step_budget_exhausted"
    TOKEN_BUDGET_EXHAUSTED = "token_budget_exhausted"
    DOOM_LOOP_DETECTED = "doom_loop_detected"
    RESUME_REQUIRES_NEW_ACTION = "resume_requires_new_action"
    LLM_FAILED = "llm_failed"
    TOOL_FAILED = "tool_failed"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_EXPIRED = "approval_expired"
    USER_CANCELLED = "user_cancelled"
    TURN_TIMEOUT = "turn_timeout"
    CONTEXT_UNAVAILABLE = "context_unavailable"
    SOURCE_DIVERGENCE = "source_divergence"
    PIPELINE_CRASH = "pipeline_crash"


@dataclass
class Turn:
    """One round of conversation. Mutated by react loop nodes."""

    # Identity.
    turn_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    conversation_id: str = "default"
    # 展示用 conversation_id 与身份隔离后的记忆 key 分离。
    memory_key: str | None = None

    # Input.
    user_input: str = ""

    # Identity（farm_uid 是对外可信标识，farm_id 仅为 Redis/历史状态兼容）。
    user_id: str = ""
    farm_uid: str = ""
    farm_id: int = 1
    role: str = UserRole.USER.value
    token_id: str = ""
    scope: str = ""
    agent_token: str = ""

    # Accumulated LLM messages (system + user + assistant + tool).
    messages: list[dict[str, Any]] = field(default_factory=list)

    # Tool metadata discovered from business server (cached for this turn).
    business_tools: list[dict[str, Any]] = field(default_factory=list)

    # Loop state.
    step_count: int = 0
    max_steps: int = 20
    status: TurnStatus = "running"
    phase: TurnPhase = TurnPhase.SETUP
    stop_reason: StopReason | None = None

    # HITL gate.
    pending_approval: dict[str, Any] | None = None
    # pending_approval = {
    #   "tool_name": str,
    #   "arguments": dict,
    #   "rationale": str,            # why agent wants to call this
    #   "risk_level": "write_confirm" | "write_high",
    #   "tool_call_id": str,         # LLM's tool_call.id (to resume after)
    #   "original_assistant_msg": dict,  # full assistant msg w/ tool_calls
    # }
    approved: bool = False
    rejected_reason: str | None = None
    # 当前 Turn 的可恢复临时任务投影；长期事实不存放在这里。
    task_state: dict[str, Any] | None = None

    # Output.
    final_answer: str | None = None
    committed_result: dict[str, Any] | None = None
    finalization_pending: bool = False
    finalization_request: dict[str, Any] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    # events are SSE-flavored: {"type": "thought|action|observation|...",
    #                            "data": {...}, "ts": float}

    # Memory snapshot for this conversation at turn start.
    memory_snapshot: dict[str, Any] = field(default_factory=dict)
    # Turn 内固定的起始 Context 投影；动态 observation 不回写 snapshot。
    context_bundle: ContextBundle | None = None
    conversation_revision: int = 0
    summary_revision: int = 0
    reset_generation: int = 0
    context_source_status: str = "empty"

    # Errors. error 保留为兼容字段，结构化信息使用下列字段。
    error: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] = field(default_factory=dict)

    def set_phase(self, phase: TurnPhase) -> None:
        """记录当前 Runtime 阶段，不改变持久化业务状态。"""
        self.phase = phase

    def record_error(
        self,
        code: str,
        message: str,
        *,
        phase: TurnPhase | None = None,
        tool_name: str = "",
        retryable: bool = False,
        attempt: int = 0,
        category: str = "",
        stop_reason: StopReason | None = None,
        status: TurnStatus | None = "failed",
    ) -> dict[str, Any]:
        """记录结构化错误，同时保留旧 error 字段和状态语义。"""
        if phase is not None:
            self.phase = phase
        self.error = code
        self.error_code = code
        self.error_message = message
        self.error_details = {
            "code": code,
            "message": message,
            "phase": self.phase.value,
            "tool_name": tool_name,
            "retryable": retryable,
            "attempt": attempt,
        }
        if category:
            self.error_details["category"] = category
        if stop_reason is not None:
            self.stop_reason = stop_reason
        if status is not None:
            self.status = status
        if status in {
            "completed",
            "terminated",
            "failed",
            "rejected",
            "cancelled",
            "timeout",
        }:
            self.phase = TurnPhase.TERMINAL
        return dict(self.error_details)

    def record_termination(
        self,
        reason: StopReason,
        message: str,
        *,
        phase: TurnPhase | None = None,
    ) -> dict[str, Any]:
        """记录受控终止，避免把预算耗尽误记为系统异常。"""
        if phase is not None:
            self.phase = phase
        self.status = "terminated"
        self.stop_reason = reason
        self.error = None
        self.error_code = None
        self.error_message = message
        self.error_details = {
            "code": reason.value,
            "message": message,
            "phase": self.phase.value,
            "retryable": False,
            "attempt": 0,
        }
        self.phase = TurnPhase.TERMINAL
        return dict(self.error_details)

    def emit(self, event_type: str, data: dict | None = None) -> dict:
        """记录领域事件；seq/event_id 由持久化 Publisher 在边界统一补充。"""
        import time

        event = {
            "type": event_type,
            "data": data or {},
            "ts": time.time(),
            "turn_id": self.turn_id,
            "step": self.step_count,
        }
        self.events.append(event)
        return event

    def snapshot(self) -> dict[str, Any]:
        """Public view of turn (for /status endpoint)."""
        return {
            "turn_id": self.turn_id,
            "conversation_id": self.conversation_id,
            "status": self.status,
            "phase": self.phase.value,
            "stop_reason": self.stop_reason.value if self.stop_reason else None,
            "step_count": self.step_count,
            "pending_approval": self.pending_approval,
            "task_state": self.task_state,
            "final_answer": self.final_answer,
            "committed_result": self.committed_result,
            "finalization_pending": self.finalization_pending,
            "error": self.error,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "events_count": len(self.events),
            "conversation_revision": self.conversation_revision,
            "summary_revision": self.summary_revision,
            "reset_generation": self.reset_generation,
            "context_source_status": self.context_source_status,
        }
