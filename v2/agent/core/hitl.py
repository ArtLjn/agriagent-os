"""Human-in-the-Loop (HITL) gate.

Intercepts write operations and requires explicit user approval before
the react loop calls the business tool.

Risk classification:
  - read          : no gate (get_farm_status, get_weather, query_farm_logs)
  - write_confirm : gate (create_farm_log) — agent asks user to confirm
  - write_high    : gate + verify identity (delete_farm_log) — stricter

Risk is read from the tool description embedded [RISK: ...] marker,
set by business/tools/*.py.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from agent.core.turn import Turn

RiskLevel = Literal["read", "write_confirm", "write_high"]

_RISK_PATTERN = re.compile(r"\[RISK:\s*(\w+)\s*\]")


def classify(tool_description: str) -> RiskLevel:
    """Parse [RISK: ...] marker from tool description. Defaults to read."""
    m = _RISK_PATTERN.search(tool_description or "")
    if not m:
        return "read"
    level = m.group(1).lower()
    if level in ("write_confirm", "write_high"):
        return level  # type: ignore[return-value]
    return "read"


def needs_approval(risk: RiskLevel) -> bool:
    return risk in ("write_confirm", "write_high")


def gate(
    turn: Turn,
    tool_name: str,
    tool_description: str,
    arguments: dict[str, Any],
    tool_call_id: str,
    rationale: str = "",
) -> Turn:
    """Set up HITL gate on a turn.

    If tool is read-only, returns turn unchanged (caller proceeds to invoke).
    If write*, sets turn.pending_approval and status=awaiting_approval.

    rationale should explain why the agent wants to call this tool
    (extracted from LLM's preceding thought).
    """
    risk = classify(tool_description)
    if not needs_approval(risk):
        return turn  # no gate needed

    turn.pending_approval = {
        "tool_name": tool_name,
        "arguments": arguments,
        "rationale": rationale or f"调用写操作工具 {tool_name}",
        "risk_level": risk,
        "tool_call_id": tool_call_id,
    }
    turn.status = "awaiting_approval"
    return turn


def approve(turn: Turn, decision: bool, reason: str = "") -> Turn:
    """Apply user's approval decision to a gated turn.

    decision=True  : clear pending_approval, set approved=True, resume running.
    decision=False : set rejected_reason, status=rejected (caller ends turn).
    """
    if turn.pending_approval is None:
        return turn  # nothing to approve

    if decision:
        turn.approved = True
        turn.pending_approval = None
        turn.status = "running"
    else:
        turn.rejected_reason = reason or "user rejected"
        turn.pending_approval = None
        turn.status = "rejected"
    return turn
