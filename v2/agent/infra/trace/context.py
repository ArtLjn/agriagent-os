"""Trace 上下文管理 — 基于 contextvars 的异步链路追踪。

参考 archive/backend/app/infra/trace_context.py，适配 v2 的 MongoDB 架构。
"""

from __future__ import annotations

from contextlib import contextmanager
import contextvars
import time
import uuid
from dataclasses import dataclass
from typing import Iterator


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
    root_span_id: str = ""
    sampling_level: int = 1


@dataclass(frozen=True)
class TraceSpanContext:
    """当前异步执行分支的 span 父子上下文。"""

    span_id: str
    parent_span_id: str | None


_trace_ctx: contextvars.ContextVar[TraceInfo | None] = contextvars.ContextVar(
    "trace_ctx", default=None
)
_step_ctx: contextvars.ContextVar[int] = contextvars.ContextVar("trace_step", default=0)
_span_ctx: contextvars.ContextVar[tuple[TraceSpanContext, ...]] = (
    contextvars.ContextVar("trace_span_stack", default=())
)


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
        root_span_id=_new_span_id("root"),
    )
    _trace_ctx.set(trace)
    _step_ctx.set(0)
    _span_ctx.set(())
    return trace


def trace_id_for_turn(turn_id: str = "") -> str:
    """为 Turn 生成可重复的 trace_id，避免重连或 Worker 重试创建新链路。"""
    return f"trace_{turn_id}" if turn_id else f"trace_{uuid.uuid4().hex}"


def get_trace() -> TraceInfo | None:
    return _trace_ctx.get()


def clear_trace() -> None:
    _trace_ctx.set(None)
    _step_ctx.set(0)
    _span_ctx.set(())


def get_step_index() -> int:
    return _step_ctx.get()


def increment_step() -> int:
    new_val = _step_ctx.get() + 1
    _step_ctx.set(new_val)
    return new_val


def set_step_index(step: int | None) -> None:
    if step is not None:
        _step_ctx.set(step)


def _new_span_id(prefix: str = "span") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def new_span_id() -> str:
    """生成可读且不携带业务数据的 span ID。"""
    return _new_span_id()


def current_span_id() -> str | None:
    """返回当前异步分支最近的 span。"""
    stack = _span_ctx.get()
    return stack[-1].span_id if stack else None


def current_parent_span_id() -> str | None:
    """返回新 span 应挂载的父节点。"""
    trace = get_trace()
    return current_span_id() or (trace.root_span_id if trace else None)


@contextmanager
def span_context(
    span_id: str | None = None, parent_span_id: str | None = None
) -> Iterator[TraceSpanContext]:
    """在异步任务的同步代码段中设置当前 span 父子关系。"""
    resolved_span_id = span_id or new_span_id()
    resolved_parent = parent_span_id or current_parent_span_id()
    span = TraceSpanContext(resolved_span_id, resolved_parent)
    token = _span_ctx.set((*_span_ctx.get(), span))
    try:
        yield span
    finally:
        _span_ctx.reset(token)
