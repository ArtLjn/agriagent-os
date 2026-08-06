"""Task Graph 原始上下文构建。"""

from __future__ import annotations

from typing import Any

from app.agent.task_graph.models import RawContext


def build_raw_context(
    *,
    user_input: str,
    request_id: str,
    session_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    last_failed_task_graph_id: str | None = None,
) -> RawContext:
    trace_metadata = dict(metadata or {})
    trace_metadata["user_input"] = user_input
    runtime_refs = [last_failed_task_graph_id] if last_failed_task_graph_id else []
    return RawContext(
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        runtime_refs=runtime_refs,
        trace_metadata=trace_metadata,
    )
