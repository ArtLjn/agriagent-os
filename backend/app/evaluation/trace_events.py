"""Agent 平台 trace 事件名。"""

from app.observability.lifecycle import AgentLifecycleEvent, lifecycle_event_names

CONTEXT_BUILD = AgentLifecycleEvent.CONTEXT_BUILD.value
PROMPT_RENDER = AgentLifecycleEvent.PROMPT_RENDER.value
LLM_CALL = AgentLifecycleEvent.LLM_CALL.value
TOOL_CALL = AgentLifecycleEvent.TOOL_CALL.value
SKILL_CALL = "skill_call"
MEMORY_OBSERVE = AgentLifecycleEvent.MEMORY_OBSERVE.value
RESPONSE_FORMAT = AgentLifecycleEvent.RESPONSE_FORMAT.value
EVALUATION_CAPTURE = AgentLifecycleEvent.EVALUATION_CAPTURE.value

TRACE_EVENT_NAMES = lifecycle_event_names() | {SKILL_CALL}

TRACE_EVENT_ALIASES = {
    SKILL_CALL: TOOL_CALL,
}


def normalize_trace_event_name(node_type: str) -> str:
    """把历史事件名归一到平台事件名。"""
    return TRACE_EVENT_ALIASES.get(node_type, node_type)


def is_platform_trace_event(node_type: str) -> bool:
    """判断是否为平台生命周期事件。"""
    return normalize_trace_event_name(node_type) in TRACE_EVENT_NAMES
