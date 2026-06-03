"""Agent 图兼容入口。

新代码应优先从 `app.agent.runtime` 引入 Runtime 能力；本模块保留旧导入路径，
方便分阶段迁移测试和外部调用。
"""

from app.agent.runtime.graph_factory import compile_advisor_graph
from app.agent.runtime.nodes import (
    _build_circuit_key,
    _detect_missed_tool_call,
    _extract_tokens_used,
    _extract_tool_calls_from_content,
    _find_last_human_message,
    _get_classifier,
    _get_farm_context,
    _get_season,
    _llm_node,
    _parallel_tool_node,
    _record_llm_failure,
    _record_llm_success,
    _should_continue,
    _warm_tool_caches,
    sliding_window_compact,
)
from app.agent.runtime.state import AgentState

__all__ = [
    "AgentState",
    "_build_circuit_key",
    "_detect_missed_tool_call",
    "_extract_tokens_used",
    "_extract_tool_calls_from_content",
    "_find_last_human_message",
    "_get_classifier",
    "_get_farm_context",
    "_get_season",
    "_llm_node",
    "_parallel_tool_node",
    "_record_llm_failure",
    "_record_llm_success",
    "_should_continue",
    "_warm_tool_caches",
    "compile_advisor_graph",
    "sliding_window_compact",
]
