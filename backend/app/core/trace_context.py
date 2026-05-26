"""Trace 上下文管理 — 基于 contextvars 的异步链路追踪。"""

import contextvars
import time
import uuid
from dataclasses import dataclass


@dataclass
class TraceInfo:
    """一次对话请求的追踪上下文。"""
    request_id: str
    session_id: str
    farm_id: int
    created_at: float


_trace_ctx: contextvars.ContextVar[TraceInfo | None] = contextvars.ContextVar(
    "trace_ctx", default=None
)
_round_ctx: contextvars.ContextVar[int] = contextvars.ContextVar(
    "round_index", default=0
)


def init_trace(farm_id: int, session_id: str = "") -> TraceInfo:
    """初始化追踪上下文，生成唯一 request_id。"""
    trace = TraceInfo(
        request_id=uuid.uuid4().hex[:8],
        session_id=session_id,
        farm_id=farm_id,
        created_at=time.time(),
    )
    _trace_ctx.set(trace)
    _round_ctx.set(0)
    return trace


def get_trace() -> TraceInfo | None:
    """获取当前追踪上下文。"""
    return _trace_ctx.get()


def clear_trace() -> None:
    """清除追踪上下文。"""
    _trace_ctx.set(None)
    _round_ctx.set(0)


def get_round_index() -> int:
    """获取当前 LLM 循环轮次。"""
    return _round_ctx.get()


def increment_round() -> int:
    """轮次 +1，返回新值。"""
    new_val = _round_ctx.get() + 1
    _round_ctx.set(new_val)
    return new_val


__all__ = ["TraceInfo", "init_trace", "get_trace", "clear_trace", "get_round_index", "increment_round"]
