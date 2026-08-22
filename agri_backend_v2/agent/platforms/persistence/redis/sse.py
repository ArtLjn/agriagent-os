"""SSE event types and helpers.

Event types emitted to the Web UI:
  - meta          : turn metadata (turn_id, conversation_id)
  - thought       : LLM reasoning (raw content)
  - plan          : multi-step plan (when LLM proposes plan)
  - action        : tool call initiated (name, arguments, rationale)
  - tool_started  : Tool 开始执行，携带稳定调用标识
  - tool_finished : Tool 完成，携带耗时和结果/错误
  - observation   : tool result (data, possibly trimmed)
  - approval_required : HITL gate fired (tool_name, args, risk_level)
  - approval_result   : user approved/rejected (decision, reason)
  - operation_committed : write operation committed with structured result
  - write_committed_reply_failed : write succeeded but reply generation failed
  - final_answer_start : begin streaming final answer (empty)
  - final_answer_delta  : incremental token of final answer
  - assistant_delta     : incremental model output during reasoning
  - heartbeat           : the turn is still executing
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


def sse_event(
    event_type: str,
    data: dict[str, Any] | None = None,
    *,
    event_id: str = "",
) -> str:
    """Format a single SSE message: `event: TYPE\\ndata: JSON\\n\\n`."""
    payload = data or {}
    event_id_line = f"id: {event_id}\n" if event_id else ""
    return (
        f"event: {event_type}\n"
        f"{event_id_line}"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    )


# Convenience constructors.
def meta(
    turn_id: str, conversation_id: str, user_input: str, request_id: str = ""
) -> dict:
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


def assistant_delta(delta: str) -> dict:
    """在 Runtime 尚未确定是否为最终答复前，推送模型输出增量。"""
    return {"type": "assistant_delta", "data": {"delta": delta}}


def heartbeat(stage: str, step: int = 0) -> dict:
    """让长时间运行的 LLM 或 Skill 调用保持可观测，不伪造执行进度。"""
    return {"type": "heartbeat", "data": {"stage": stage, "step": step}}


def plan(steps: list[str]) -> dict:
    return {"type": "plan", "data": {"steps": steps}}


def plan_created(goal: str, steps: list[dict]) -> dict:
    return {
        "type": "plan_created",
        "data": {"goal": goal, "step_count": len(steps), "steps": steps},
    }


def plan_step_done(
    step_index: int, skill: str, status: str, result: Any = None
) -> dict:
    return {
        "type": "plan_step_done",
        "data": {
            "step_index": step_index,
            "skill": skill,
            "status": status,
            "result": result,
        },
    }


def step_started(turn_id: str, step_index: int) -> dict:
    """标记 ReAct Step 开始，供并行 Tool Batch 关联稳定的 step_index。"""
    return {
        "type": "step.started",
        "data": {"turn_id": turn_id, "step_index": step_index, "status": "running"},
    }


def step_completed(
    turn_id: str,
    step_index: int,
    *,
    status: str,
    tool_count: int = 0,
    error: dict[str, Any] | None = None,
) -> dict:
    """标记 Step 收口，错误信息只保留结构化摘要。"""
    data: dict[str, Any] = {
        "turn_id": turn_id,
        "step_index": step_index,
        "status": status,
        "tool_count": tool_count,
    }
    if error:
        data["error"] = error
    return {"type": "step.completed", "data": data}


def action(tool_name: str, arguments: dict, rationale: str = "") -> dict:
    return {
        "type": "action",
        "data": {
            "tool_name": tool_name,
            "arguments": arguments,
            "rationale": rationale,
        },
    }


def tool_started(
    turn_id: str,
    tool_call_id: str,
    tool_name: str,
    step: int,
    arguments: dict,
) -> dict:
    """标记 Tool 已进入执行，供长耗时调用和并行调用关联。"""
    return {
        "type": "tool_started",
        "data": {
            "turn_id": turn_id,
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "step": step,
            "arguments": arguments,
        },
    }


def tool_finished(
    turn_id: str,
    tool_call_id: str,
    tool_name: str,
    step: int,
    duration_ms: int,
    result: Any = None,
    error: dict[str, Any] | None = None,
) -> dict:
    """标记 Tool 完成，保留稳定调用 ID、耗时和结果/错误。"""
    return {
        "type": "tool_finished",
        "data": {
            "turn_id": turn_id,
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "step": step,
            "duration_ms": duration_ms,
            "result": result,
            "error": error,
        },
    }


def tool_failed(
    turn_id: str,
    tool_call_id: str,
    tool_name: str,
    step: int,
    error: dict[str, Any],
    duration_ms: int = 0,
) -> dict:
    """标记 Tool 失败，和 tool_started 使用同一个 tool_call_id 配对。"""
    return {
        "type": "tool.failed",
        "data": {
            "turn_id": turn_id,
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "step": step,
            "duration_ms": duration_ms,
            "error": error,
        },
    }


def observation(
    tool_name: str,
    data: Any,
    error: str | None = None,
    error_info: dict[str, Any] | None = None,
) -> dict:
    payload = {
        "tool_name": tool_name,
        "result": data,
        "error": error,
    }
    if error_info is not None:
        payload["error_info"] = error_info
    return {
        "type": "observation",
        "data": payload,
    }


def approval_required(
    tool_name: str,
    arguments: dict,
    rationale: str,
    risk_level: str,
    turn_id: str,
    summary: str = "",
    plan: dict | None = None,
) -> dict:
    data = {
        "turn_id": turn_id,
        "tool_name": tool_name,
        "arguments": arguments,
        "rationale": rationale,
        "risk_level": risk_level,
    }
    # 种植计划 prepare → commit 审批链路附加结构化计划摘要，供前端展示完整审批内容
    if summary:
        data["summary"] = summary
    if plan is not None:
        data["plan"] = plan
    return {"type": "approval_required", "data": data}


def approval_result(decision: str, reason: str = "") -> dict:
    return {
        "type": "approval_result",
        "data": {"decision": decision, "reason": reason},
    }


def operation_committed(result: dict[str, Any]) -> dict:
    return {"type": "operation_committed", "data": {"result": result}}


def write_committed_reply_failed(message: str) -> dict:
    return {
        "type": "write_committed_reply_failed",
        "data": {
            "code": "write_committed_reply_failed",
            "message": message,
        },
    }


def final_answer(text: str) -> dict:
    return {"type": "final_answer", "data": {"text": text}}


def final_answer_start() -> dict:
    return {"type": "final_answer_start", "data": {}}


def final_answer_delta(delta: str) -> dict:
    return {"type": "final_answer_delta", "data": {"delta": delta}}


def error_event(
    message: str,
    code: str = "internal",
    *,
    phase: str = "",
    tool_name: str = "",
    retryable: bool = False,
    attempt: int = 0,
    category: str = "",
) -> dict:
    data = {
        "code": code,
        "message": message,
        "phase": phase,
        "retryable": retryable,
        "attempt": attempt,
    }
    if category:
        data["category"] = category
    if tool_name:
        data["tool_name"] = tool_name
    return {"type": "error", "data": data}


def done(
    status: str,
    turn_id: str,
    *,
    stop_reason: str | None = None,
    step_count: int | None = None,
) -> dict:
    """构造唯一流关闭事件，并保留可解释的 Turn 终止上下文。"""
    data: dict[str, Any] = {"status": status, "turn_id": turn_id}
    if stop_reason:
        data["stop_reason"] = stop_reason
    if step_count is not None:
        data["step_count"] = step_count
    return {"type": "done", "data": data}


def turn_completed(
    turn_id: str, *, stop_reason: str, step_count: int
) -> dict:
    """发布业务成功终态；真正关闭 SSE 仍由 done 负责。"""
    return {
        "type": "turn.completed",
        "data": {
            "turn_id": turn_id,
            "status": "completed",
            "stop_reason": stop_reason,
            "step_count": step_count,
        },
    }


def turn_terminated(
    turn_id: str,
    *,
    reason: str,
    message: str,
    step_count: int,
    status: str = "terminated",
) -> dict:
    """发布预算/策略受控终态，不伪装成 error 事件。"""
    return {
        "type": "turn.terminated",
        "data": {
            "turn_id": turn_id,
            "status": status,
            "reason": reason,
            "message": message,
            "step_count": step_count,
        },
    }


def turn_failed(
    turn_id: str, *, stop_reason: str, error: dict[str, Any]
) -> dict:
    """发布执行失败语义终态；错误详情仍保留 code 和上下文。"""
    return {
        "type": "turn.failed",
        "data": {
            "turn_id": turn_id,
            "status": "failed",
            "stop_reason": stop_reason,
            "error": error,
        },
    }


def context_usage(
    used: int, total: int, percent: int, level: str, step: int = 0
) -> dict:
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
