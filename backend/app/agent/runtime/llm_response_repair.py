"""Agent Runtime LLM 响应修正逻辑。"""

import logging

from langchain_core.messages import AIMessage, SystemMessage

from app.agent.runtime.chat_fallbacks import retry_no_tool_json_leak
from app.agent.runtime.direct_routing import filter_tool_calls_by_selected
from app.agent.runtime.messages import (
    _detect_missed_tool_call,
    _extract_tool_calls_from_content,
)
from app.infra.pending_actions import is_write_skill

logger = logging.getLogger(__name__)


async def _normalize_content_tool_calls(
    *,
    response: AIMessage,
    llm,
    system_text: str,
    messages: list,
    model_name: str,
    selected_tools: list,
) -> AIMessage:
    """兼容 content 内 JSON 工具调用。"""
    if response.tool_calls:
        return response

    parsed_tool_calls = _extract_tool_calls_from_content(response.content or "")
    if parsed_tool_calls and not selected_tools:
        response = await retry_no_tool_json_leak(
            llm=llm,
            system_text=system_text,
            messages=messages,
            response=response,
            model_name=model_name,
        )
        parsed_tool_calls = _extract_tool_calls_from_content(response.content or "")
    return _content_tool_calls_response(
        response=response,
        parsed_tool_calls=parsed_tool_calls,
        selected_tools=selected_tools,
        model_name=model_name,
    )


def _content_tool_calls_response(
    *,
    response: AIMessage,
    parsed_tool_calls: list[dict] | None,
    selected_tools: list,
    model_name: str,
) -> AIMessage:
    if not parsed_tool_calls:
        return response
    filtered_tool_calls = filter_tool_calls_by_selected(
        parsed_tool_calls, selected_tools
    )
    if not filtered_tool_calls:
        return response
    logger.info(
        "LLM content 中检测到工具调用 JSON，手动构造 tool_calls | tools=%s | model=%s",
        [tc["name"] for tc in filtered_tool_calls],
        model_name,
    )
    return AIMessage(
        content="",
        tool_calls=filtered_tool_calls,
        response_metadata=response.response_metadata,
        id=response.id,
    )


async def _retry_missed_tool_call(
    *,
    response: AIMessage,
    llm,
    system_text: str,
    messages: list,
    user_msg: str,
    selected_tools: list,
) -> AIMessage:
    """检测并重试应该调用工具但未调用的响应。"""
    if response.tool_calls:
        return response

    should_retry, missed_tools = _detect_missed_tool_call(
        user_msg, response.content or "", selected_tools
    )
    if not (should_retry and selected_tools):
        return response

    logger.warning(
        "检测到 LLM 应调用工具但未调用 | user_msg=%r | selected=%s | 尝试重试",
        user_msg[:80],
        [t.name for t in selected_tools],
    )
    try:
        retry_response = await _invoke_tool_retry(
            llm=llm,
            system_text=system_text,
            messages=messages,
        )
    except Exception as retry_exc:
        logger.warning("重试调用失败 | error=%s", retry_exc)
        return response

    filtered_retry_calls = _extract_retry_tool_calls(
        retry_response=retry_response,
        selected_tools=selected_tools,
    )
    if filtered_retry_calls:
        logger.info(
            "重试成功，LLM 输出了工具调用 | tools=%s",
            [tc["name"] for tc in filtered_retry_calls],
        )
        return _tool_call_response(retry_response, filtered_retry_calls)
    if any(is_write_skill(tool.name) for tool in missed_tools):
        logger.warning("写操作重试后仍未输出工具调用，使用安全兜底回复")
        return _write_retry_fallback(retry_response)
    logger.warning("重试后 LLM 仍未输出工具调用，使用原回复")
    return response


async def _invoke_tool_retry(*, llm, system_text: str, messages: list):
    retry_system = SystemMessage(
        content=system_text
        + "\n\n【重要提醒】用户的问题需要调用工具获取真实数据，请直接输出工具调用 JSON，不要回复文本。"
    )
    return await llm.ainvoke([retry_system] + messages)


def _extract_retry_tool_calls(*, retry_response, selected_tools: list) -> list[dict]:
    retry_calls = getattr(retry_response, "tool_calls", None) or []
    filtered_retry_calls = filter_tool_calls_by_selected(retry_calls, selected_tools)
    if filtered_retry_calls:
        return filtered_retry_calls
    retry_parsed = _extract_tool_calls_from_content(retry_response.content or "")
    if not retry_parsed:
        return []
    return filter_tool_calls_by_selected(retry_parsed, selected_tools)


def _tool_call_response(retry_response, filtered_retry_calls: list[dict]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=filtered_retry_calls,
        response_metadata=retry_response.response_metadata,
        id=retry_response.id,
    )


def _write_retry_fallback(retry_response) -> AIMessage:
    return AIMessage(
        content=(
            "这条操作还没有执行。"
            "系统没有生成可确认的待执行动作。"
            "请重新描述要新增、修改或结算的对象和关键参数，"
            "我会先生成待确认操作，确认后再执行。"
        ),
        response_metadata=retry_response.response_metadata,
        id=retry_response.id,
    )


__all__ = ["_normalize_content_tool_calls", "_retry_missed_tool_call"]
