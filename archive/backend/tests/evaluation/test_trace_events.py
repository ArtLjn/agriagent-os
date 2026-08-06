"""测试平台 trace 事件名。"""

from app.platforms.evaluation.trace_events import (
    CONTEXT_BUILD,
    EVALUATION_CAPTURE,
    LLM_CALL,
    MEMORY_OBSERVE,
    PROMPT_RENDER,
    RESPONSE_FORMAT,
    TOOL_CALL,
    is_platform_trace_event,
    normalize_trace_event_name,
)


def test_required_platform_trace_events_are_registered() -> None:
    for event_name in [
        CONTEXT_BUILD,
        PROMPT_RENDER,
        LLM_CALL,
        TOOL_CALL,
        MEMORY_OBSERVE,
        RESPONSE_FORMAT,
        EVALUATION_CAPTURE,
    ]:
        assert is_platform_trace_event(event_name)


def test_skill_call_is_compatible_tool_call_alias() -> None:
    assert normalize_trace_event_name("skill_call") == TOOL_CALL
    assert is_platform_trace_event("skill_call")
