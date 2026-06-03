"""Agent 生命周期事件定义。"""

from app.core.compat import StrEnum


class AgentLifecycleEvent(StrEnum):
    """Agent 平台 trace 生命周期事件。"""

    CONTEXT_BUILD = "context_build"
    PROMPT_RENDER = "prompt_render"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    MEMORY_OBSERVE = "memory_observe"
    RESPONSE_FORMAT = "response_format"
    EVALUATION_CAPTURE = "evaluation_capture"


def lifecycle_event_names() -> set[str]:
    """返回所有平台生命周期事件名。"""
    return {event.value for event in AgentLifecycleEvent}
