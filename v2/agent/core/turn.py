"""Turn data structure.

The Turn object flows through every pipeline node (context -> react loop ->
hitl -> tool -> reflect -> emit). Each node is a pure function `(Turn) -> Turn`.
This is the single source of truth for one user message processing.

See harness_study spec: docs/00-react-loop.md, docs/01-vertical-slice.md.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


TurnStatus = Literal[
    "running",            # ReAct loop iterating
    "awaiting_approval",  # Blocked on HITL gate
    "completed",          # Final answer emitted
    "rejected",           # User rejected HITL
    "failed",             # Error
]


@dataclass
class Turn:
    """One round of conversation. Mutated by react loop nodes."""

    # Identity.
    turn_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    conversation_id: str = "default"

    # Input.
    user_input: str = ""

    # Accumulated LLM messages (system + user + assistant + tool).
    messages: list[dict[str, Any]] = field(default_factory=list)

    # Tool metadata discovered from business server (cached for this turn).
    business_tools: list[dict[str, Any]] = field(default_factory=list)

    # Loop state.
    step_count: int = 0
    max_steps: int = 5
    status: TurnStatus = "running"

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

    # Output.
    final_answer: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    # events are SSE-flavored: {"type": "thought|action|observation|...",
    #                            "data": {...}, "ts": float}

    # Memory snapshot for this conversation at turn start.
    memory_snapshot: dict[str, Any] = field(default_factory=dict)

    # Errors.
    error: str | None = None

    def emit(self, event_type: str, data: dict | None = None) -> dict:
        """Append an SSE event to this turn. Returns the event for streaming."""
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
            "step_count": self.step_count,
            "pending_approval": self.pending_approval,
            "final_answer": self.final_answer,
            "error": self.error,
            "events_count": len(self.events),
        }
