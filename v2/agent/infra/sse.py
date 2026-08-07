"""SSE event types and helpers.

Event types emitted to the Web UI:
  - meta          : turn metadata (turn_id, conversation_id)
  - thought       : LLM reasoning (raw content)
  - plan          : multi-step plan (when LLM proposes plan)
  - action        : tool call initiated (name, arguments, rationale)
  - observation   : tool result (data, possibly trimmed)
  - approval_required : HITL gate fired (tool_name, args, risk_level)
  - approval_result   : user approved/rejected (decision, reason)
  - final_answer_start : begin streaming final answer (empty)
  - final_answer_delta  : incremental token of final answer
  - final_answer : assistant's final reply complete (text)
  - error         : pipeline failure (message)
  - done          : turn finished (status)
  - context_usage : token usage info (used, total, percent, level)
  - context_compressing : triggered when token usage hits hard threshold
  - context_compressed  : after summarizer finished compressing
  - doom_loop_warning   : detected repeated call pattern
  - verification_warning : pre_completion_checklist found issues
  - plan_created  : planner created a multi-step plan
  - plan_step_done : one step of plan finished

All events are JSON-serializable dicts. main.py converts to SSE wire format.
"""
from __future__ import annotations

import json
from typing import Any


def sse_event(event_type: str, data: dict[str, Any] | None = None) -> str:
    """Format a single SSE message: `event: TYPE\\ndata: JSON\\n\\n`."""
    payload = data or {}
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


# Convenience constructors.
def meta(turn_id: str, conversation_id: str, user_input: str, request_id: str = "") -> dict:
    return {
        "type": "meta",
        "data": {
            "turn_id": turn_id,
            "conversation_id": conversation_id,
            "user_input": user_input,
            "request_id": request_id,
        },
    }


def thought(content: str) -> dict:
    return {"type": "thought", "data": {"content": content}}


def plan(steps: list[str]) -> dict:
    return {"type": "plan", "data": {"steps": steps}}


def plan_created(goal: str, steps: list[dict]) -> dict:
    return {
        "type": "plan_created",
        "data": {"goal": goal, "step_count": len(steps), "steps": steps},
    }


def plan_step_done(step_index: int, skill: str, status: str, result: Any = None) -> dict:
    return {
        "type": "plan_step_done",
        "data": {
            "step_index": step_index,
            "skill": skill,
            "status": status,
            "result": result,
        },
    }


def action(tool_name: str, arguments: dict, rationale: str = "") -> dict:
    return {
        "type": "action",
        "data": {
            "tool_name": tool_name,
            "arguments": arguments,
            "rationale": rationale,
        },
    }


def observation(tool_name: str, data: Any, error: str | None = None) -> dict:
    return {
        "type": "observation",
        "data": {
            "tool_name": tool_name,
            "result": data,
            "error": error,
        },
    }


def approval_required(
    tool_name: str,
    arguments: dict,
    rationale: str,
    risk_level: str,
    turn_id: str,
) -> dict:
    return {
        "type": "approval_required",
        "data": {
            "turn_id": turn_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "rationale": rationale,
            "risk_level": risk_level,
        },
    }


def approval_result(decision: str, reason: str = "") -> dict:
    return {
        "type": "approval_result",
        "data": {"decision": decision, "reason": reason},
    }


def final_answer(text: str) -> dict:
    return {"type": "final_answer", "data": {"text": text}}


def final_answer_start() -> dict:
    return {"type": "final_answer_start", "data": {}}


def final_answer_delta(delta: str) -> dict:
    return {"type": "final_answer_delta", "data": {"delta": delta}}


def error_event(message: str, code: str = "internal") -> dict:
    return {"type": "error", "data": {"code": code, "message": message}}


def done(status: str, turn_id: str) -> dict:
    return {"type": "done", "data": {"status": status, "turn_id": turn_id}}


def context_usage(used: int, total: int, percent: int, level: str, step: int = 0) -> dict:
    return {
        "type": "context_usage",
        "data": {
            "used": used,
            "total": total,
            "percent": percent,
            "level": level,
            "step": step,
        },
    }


def context_compressing(trigger: str, before_percent: int) -> dict:
    return {
        "type": "context_compressing",
        "data": {"trigger": trigger, "before_percent": before_percent},
    }


def context_compressed(after_percent: int, summary_preview: str = "") -> dict:
    return {
        "type": "context_compressed",
        "data": {"after_percent": after_percent, "summary_preview": summary_preview},
    }


def doom_loop_warning(message: str, step: int = 0) -> dict:
    return {
        "type": "doom_loop_warning",
        "data": {"message": message, "step": step},
    }


def verification_warning(issues: list[str], step: int = 0) -> dict:
    return {
        "type": "verification_warning",
        "data": {"issues": issues, "step": step},
    }
