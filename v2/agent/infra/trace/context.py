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

    request_id: str
    conversation_id: str
    created_at: float
    turn_id: str = ""
    step_index: int = 0


_trace_ctx: contextvars.ContextVar[TraceInfo | None] = contextvars.ContextVar(
    "trace_ctx", default=None
)
_step_ctx: contextvars.ContextVar[int] = contextvars.ContextVar(
    "trace_step", default=0
)


def init_trace(
    conversation_id: str = "",
    turn_id: str = "",
    request_id: str = "",
) -> TraceInfo:
    """初始化追踪上下文。"""
    trace = TraceInfo(
        request_id=request_id or uuid.uuid4().hex[:8],
        conversation_id=conversation_id,
        created_at=time.time(),
        turn_id=turn_id,
    )
    _trace_ctx.set(trace)
    _step_ctx.set(0)
    return trace


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
