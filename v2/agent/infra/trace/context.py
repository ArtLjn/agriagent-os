"""Trace 上下文管理 — 基于 contextvars 的异步链路追踪。

参考 archive/backend/app/infra/trace_context.py，适配 v2 的 MongoDB 架构。
"""

from __future__ import annotations

import contextvars
import time
import uuid
from dataclasses import dataclass


@dataclass
class TraceInfo:
    """一次对话请求的追踪上下文。"""

    trace_id: str
    request_id: str
    conversation_id: str
    created_at: float
    turn_id: str = ""
    user_id: str = ""
    farm_uid: str = ""
    step_index: int = 0


_trace_ctx: contextvars.ContextVar[TraceInfo | None] = contextvars.ContextVar(
    "trace_ctx", default=None
)
_step_ctx: contextvars.ContextVar[int] = contextvars.ContextVar("trace_step", default=0)


def init_trace(
    conversation_id: str = "",
    turn_id: str = "",
    trace_id: str = "",
    request_id: str = "",
    user_id: str = "",
    farm_uid: str = "",
) -> TraceInfo:
    """初始化追踪上下文。"""
    stable_trace_id = trace_id or trace_id_for_turn(turn_id)
    trace = TraceInfo(
        trace_id=stable_trace_id,
        # request_id 是旧调用方仍在使用的兼容字段，不接受 client_request_id。
        request_id=request_id or stable_trace_id,
        conversation_id=conversation_id,
        created_at=time.time(),
        turn_id=turn_id,
        user_id=user_id,
        farm_uid=farm_uid,
    )
    _trace_ctx.set(trace)
    _step_ctx.set(0)
    return trace


def trace_id_for_turn(turn_id: str = "") -> str:
    """为 Turn 生成可重复的 trace_id，避免重连或 Worker 重试创建新链路。"""
    return f"trace_{turn_id}" if turn_id else f"trace_{uuid.uuid4().hex}"


def get_trace() -> TraceInfo | None:
    return _trace_ctx.get()


def clear_trace() -> None:
    _trace_ctx.set(None)
    _step_ctx.set(0)


def get_step_index() -> int:
    return _step_ctx.get()


def increment_step() -> int:
    new_val = _step_ctx.get() + 1
    _step_ctx.set(new_val)
    return new_val


def set_step_index(step: int | None) -> None:
    if step is not None:
        _step_ctx.set(step)
