"""Runtime 最终回复前 Reflection 辅助逻辑。"""

from langchain_core.messages import AIMessage, ToolMessage

from app.agent.reflector import (
    ReflectionDecision,
    ReflectionResult,
    ReflectorService,
    has_write_success_claim,
)
from app.infra.pending_actions import is_write_skill


def apply_post_tool_reflection(
    *,
    response: AIMessage,
    tool_messages: list[ToolMessage],
    selected_tool_names: list[str],
    farm_id: int,
    session_id: str | None,
    intent: str,
    user_message: str = "",
    plan_draft: dict | None = None,
) -> AIMessage:
    """最终文本返回前执行工具结果一致性检查。"""
    final_text = str(response.content or "")
    if (
        not tool_messages
        and not selected_tool_names
        and not has_write_success_claim(final_text)
    ):
        return response

    tool_call_ids = [
        str(getattr(message, "tool_call_id", ""))
        for message in tool_messages
        if getattr(message, "tool_call_id", None)
    ]
    reflection_result = ReflectorService().check_tool_response(
        tool_messages=tool_messages,
        final_text=final_text,
        selected_tools=selected_tool_names,
        tool_calls=response.tool_calls or [],
        trace_metadata={
            "farm_id": farm_id,
            "session_id": session_id,
            "intent": intent,
            "user_message": user_message[:500],
            "selected_tools": selected_tool_names,
            "tool_call_ids": tool_call_ids,
            "response_preview": final_text[:200],
            "plan_draft": plan_draft or {},
        },
    )
    if reflection_result.decision == ReflectionDecision.PASS:
        return response

    if reflection_result.decision == ReflectionDecision.FALLBACK_RESPONSE:
        safe_text = _fallback_guard_response(reflection_result)
    elif reflection_result.decision in {
        ReflectionDecision.REQUIRE_TOOL,
        ReflectionDecision.RETRY_GENERATION,
    }:
        safe_text = _missing_tool_fallback(
            final_text=final_text,
            selected_tool_names=selected_tool_names,
        )
        if safe_text is None:
            return response
    else:
        return response

    return AIMessage(
        content=safe_text,
        response_metadata=response.response_metadata,
        id=response.id,
    )


def _missing_tool_fallback(
    *,
    final_text: str,
    selected_tool_names: list[str],
) -> str | None:
    if any(is_write_skill(tool_name) for tool_name in selected_tool_names):
        if _is_write_fail_closed_text(final_text):
            return None
        return (
            "这条操作还没有执行。系统没有生成可确认的待执行动作。"
            "请重新描述要新增、修改或结算的对象和关键参数，"
            "我会先生成待确认操作，确认后再执行。"
        )
    return "需要先调用工具获取真实数据，请稍后重试。"


def _is_write_fail_closed_text(text: str) -> bool:
    """识别已明确说明写操作未执行的安全文案。"""
    return "还没有执行" in text or "没有生成可确认" in text


def _fallback_guard_response(reflection_result: ReflectionResult) -> str:
    """把内部反思原因转换为用户可读的安全回复。"""
    if any(
        issue.code == "no_tool_write_success_claim"
        for issue in reflection_result.issues
    ):
        return (
            "这条操作还没有执行。请重新描述要记录或修改的内容，"
            "我会先生成待确认操作，确认后再执行。"
        )
    if reflection_result.reason:
        return reflection_result.reason
    if reflection_result.issues:
        return reflection_result.issues[0].message
    return "工具结果与回复不一致，已阻止不可靠回复。"
