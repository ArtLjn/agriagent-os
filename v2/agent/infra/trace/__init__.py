"""Trace 收集模块。

提供基于 contextvars 的异步链路追踪 + MongoDB 批量写入 + 查询接口。

用法：
    from agent.infra.trace import init_trace, trace_llm_call, trace_tool_call

    # 请求开始时初始化
    init_trace(conversation_id="default", turn_id="abc123")

    # LLM 调用后记录
    trace_llm_call(model="qwen3.6-flash", messages=msgs, response=resp, token_usage=usage)

    # 工具调用后记录
    trace_tool_call(tool_name="get_farm_status", arguments=args, result=result)

    # 查询接口（供 API 层使用）
    from agent.infra.trace.store import list_traces, get_trace_nodes, get_trace_summary
"""
from agent.infra.trace.context import (
    TraceInfo,
    init_trace,
    get_trace,
    clear_trace,
    get_step_index,
    increment_step,
    set_step_index,
)
from agent.infra.trace.collector import (
    record,
    flush_now,
    start_trace_system,
    stop_trace_system,
    trace_llm_call,
    trace_tool_call,
)
from agent.infra.trace.summary import (
    build_trace_request_summary,
    summary_to_mongo_doc,
    summary_from_mongo_doc,
)

__all__ = [
    "TraceInfo",
    "init_trace",
    "get_trace",
    "clear_trace",
    "get_step_index",
    "increment_step",
    "set_step_index",
    "record",
    "flush_now",
    "start_trace_system",
    "stop_trace_system",
    "trace_llm_call",
    "trace_tool_call",
    "build_trace_request_summary",
    "summary_to_mongo_doc",
    "summary_from_mongo_doc",
]
