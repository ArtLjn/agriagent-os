"""no-tools 闲聊场景的 prompt 选择与泄漏兜底。"""

import logging

from langchain_core.messages import AIMessage, SystemMessage

from app.agent.router import RouterDecision
from app.agent.runtime.messages import _extract_tool_calls_from_content

logger = logging.getLogger(__name__)

SYSTEM_BASE_SCENE = "system_base"
SYSTEM_CHAT_SCENE = "system_chat"

_NO_TOOL_JSON_RETRY_SUFFIX = (
    "\n\n【重要提醒】当前没有绑定任何工具。上一条回复不能输出工具调用 JSON。"
    "请用自然中文直接回答用户；不要查询实时数据，不要输出工具名或 JSON。"
)
_NO_TOOL_JSON_FALLBACK = (
    "我刚才没组织好。这个问题可以直接聊，不需要调用工具。"
    "你可以继续问我农场管理、日常安排，或者直接和我闲聊。"
)


def select_system_prompt_scene(
    selected_tool_names: list[str],
    has_tool_results: bool,
    router_decision: RouterDecision,
) -> str:
    """选择 system prompt 场景，避免 no-tools 闲聊暴露工具协议。"""
    if has_tool_results:
        return SYSTEM_BASE_SCENE
    if selected_tool_names:
        return SYSTEM_BASE_SCENE
    if router_decision.fallback in {"no_tools", None}:
        return SYSTEM_CHAT_SCENE
    return SYSTEM_BASE_SCENE


def _build_friendly_no_tool_json_fallback(response: AIMessage) -> AIMessage:
    """no-tools 重试仍泄漏工具调用时，返回用户可理解的兜底回复。"""
    return AIMessage(
        content=_NO_TOOL_JSON_FALLBACK,
        response_metadata=response.response_metadata,
        id=response.id,
    )


async def retry_no_tool_json_leak(
    *,
    llm,
    system_text: str,
    messages: list,
    response: AIMessage,
    model_name: str,
) -> AIMessage:
    """no-tools 场景下模型误吐工具 JSON 时，重试生成自然语言。"""
    logger.warning(
        "no-tools 场景检测到工具 JSON 泄漏，尝试自然语言重试 | model=%s",
        model_name,
    )
    retry_system = SystemMessage(content=system_text + _NO_TOOL_JSON_RETRY_SUFFIX)
    try:
        retry_response = await llm.ainvoke([retry_system] + messages)
    except Exception as exc:
        logger.warning("no-tools JSON 泄漏重试失败，使用友好兜底 | error=%s", exc)
        return _build_friendly_no_tool_json_fallback(response)

    retry_calls = getattr(retry_response, "tool_calls", None) or []
    retry_parsed = _extract_tool_calls_from_content(retry_response.content or "")
    if retry_calls or retry_parsed:
        logger.warning(
            "no-tools JSON 泄漏重试后仍包含工具调用，使用友好兜底 | model=%s",
            model_name,
        )
        return _build_friendly_no_tool_json_fallback(retry_response)

    logger.info("no-tools JSON 泄漏重试成功，已转为自然语言回复 | model=%s", model_name)
    return retry_response
