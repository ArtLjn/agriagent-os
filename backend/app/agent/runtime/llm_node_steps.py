"""Agent Runtime LLM 节点后半流程步骤。"""

import asyncio

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from app.agent.reflector import ReflectionDecision
from app.agent.reflector.checks import check_tool_result_discarded_reply
from app.agent.runtime import node_helpers as _node_helpers
from app.agent.runtime.llm_invocation import _invoke_llm_with_retry
from app.agent.runtime.llm_response_repair import (
    _normalize_content_tool_calls,
    _retry_missed_tool_call,
)
from app.agent.runtime.llm_support import _warm_tool_caches
from app.agent.runtime.messages import _extract_tokens_used, extract_token_usage


async def _invoke_and_repair_response(
    *,
    farm_id: int,
    user_msg: str,
    route_context: dict,
    llm_context: dict,
    prompt_context: dict,
    get_llm_func,
    bind_llm_func,
    max_retries: int,
    intent: str,
) -> tuple[AIMessage, dict]:
    preload_task = _start_tool_cache_warmup(
        farm_id, route_context, prompt_context, llm_context
    )
    response, llm, invoke_meta = await _invoke_llm_for_node(
        route_context=route_context,
        llm_context=llm_context,
        prompt_context=prompt_context,
        get_llm_func=get_llm_func,
        bind_llm_func=bind_llm_func,
        max_retries=max_retries,
    )
    await _wait_for_preload(preload_task)
    response = await _repair_llm_response(
        response=response,
        llm=llm,
        required_retry_llm_factory=_required_retry_llm_factory(
            llm_context=llm_context,
            bind_llm_func=bind_llm_func,
        ),
        prompt_context=prompt_context,
        user_msg=user_msg,
        selected_tools=llm_context["selected_tools"],
        model_name=invoke_meta["model_name"],
    )
    response = await _retry_discarded_tool_result_reply(
        response=response,
        llm=llm,
        prompt_context=prompt_context,
        route_context=route_context,
        farm_id=farm_id,
        intent=intent,
        user_msg=user_msg,
        model_name=invoke_meta["model_name"],
    )
    return response, invoke_meta


def _start_tool_cache_warmup(
    farm_id: int,
    route_context: dict,
    prompt_context: dict,
    llm_context: dict,
):
    return asyncio.create_task(
        _warm_tool_caches(
            llm_context["selected_tool_names"],
            farm_id,
            prompt_context["farm_ctx"],
            context_dependencies=route_context["router_decision"].context_dependencies,
        )
    )


def _required_retry_llm_factory(*, llm_context: dict, bind_llm_func):
    selected_tools = llm_context["selected_tools"]
    if not selected_tools or llm_context["tool_choice"] == "required":
        return None

    def _factory():
        return bind_llm_func(
            llm_context["raw_llm"],
            selected_tools,
            tool_choice="required",
        )

    return _factory


async def _invoke_llm_for_node(
    *,
    route_context: dict,
    llm_context: dict,
    prompt_context: dict,
    get_llm_func,
    bind_llm_func,
    max_retries: int,
) -> tuple[AIMessage, object, dict]:
    (
        response,
        _raw_llm,
        llm,
        circuit_key,
        duration_ms,
        model_name,
    ) = await _invoke_llm_with_retry(
        model_role=llm_context["model_role"],
        raw_llm=llm_context["raw_llm"],
        llm=llm_context["llm"],
        selected_tools=llm_context["selected_tools"],
        system=prompt_context["system"],
        messages=prompt_context["messages"],
        collector=route_context["collector"],
        input_summary=prompt_context["input_summary"],
        get_llm_func=get_llm_func,
        bind_llm_func=bind_llm_func,
        max_retries=max_retries,
        tool_choice=llm_context["tool_choice"],
    )
    return (
        response,
        llm,
        {
            "circuit_key": circuit_key,
            "duration_ms": duration_ms,
            "model_name": model_name,
        },
    )


async def _wait_for_preload(preload_task) -> None:
    """短暂等待缓存预热完成，保持原有非阻塞语义。"""
    try:
        await asyncio.wait_for(preload_task, timeout=0.1)
    except (asyncio.TimeoutError, Exception):
        pass


async def _repair_llm_response(
    *,
    response: AIMessage,
    llm,
    required_retry_llm_factory,
    prompt_context: dict,
    user_msg: str,
    selected_tools: list,
    model_name: str,
) -> AIMessage:
    response = await _normalize_content_tool_calls(
        response=response,
        llm=llm,
        system_text=prompt_context["system_text"],
        messages=prompt_context["messages"],
        model_name=model_name,
        selected_tools=selected_tools,
    )
    return await _retry_missed_tool_call(
        response=response,
        llm=llm,
        system_text=prompt_context["system_text"],
        messages=prompt_context["messages"],
        user_msg=user_msg,
        selected_tools=selected_tools,
        required_retry_llm_factory=required_retry_llm_factory,
    )


async def _retry_discarded_tool_result_reply(
    *,
    response: AIMessage,
    llm,
    prompt_context: dict,
    route_context: dict,
    farm_id: int,
    intent: str,
    user_msg: str,
    model_name: str,
) -> AIMessage:
    tool_messages = _tool_messages(prompt_context["messages"])
    if not tool_messages:
        return response

    reflection = check_tool_result_discarded_reply(
        tool_messages=tool_messages,
        final_text=str(response.content or ""),
    )
    if reflection.decision != ReflectionDecision.RETRY_GENERATION:
        return response

    _record_tool_result_regeneration_trace(
        collector=route_context["collector"],
        reflection=reflection,
        farm_id=farm_id,
        session_id=route_context["session_id"],
        intent=intent,
        user_msg=user_msg,
        response=response,
    )
    retry_system = SystemMessage(
        content=_retry_system_text(prompt_context["system_text"])
    )
    try:
        retry_response = await llm.ainvoke([retry_system] + prompt_context["messages"])
    except Exception:
        return response
    return await _normalize_content_tool_calls(
        response=retry_response,
        llm=llm,
        system_text=retry_system.content,
        messages=prompt_context["messages"],
        model_name=model_name,
        selected_tools=[],
    )


def _tool_messages(messages: list) -> list[ToolMessage]:
    return [message for message in messages if isinstance(message, ToolMessage)]


def _tool_result_regeneration_suffix() -> str:
    return (
        "\n\n【反思反馈】当前轮已有工具结果，但上一版最终回复没有基于工具结果回答，"
        "反而淡化或丢弃了工具结果。请基于消息中的工具结果和用户原问题重新生成最终回复；"
        "不要再说“不需要调用工具”；不要输出工具名、JSON 或新的工具调用。"
    )


def _retry_system_text(system_text) -> str:
    return str(system_text or "") + _tool_result_regeneration_suffix()


def _record_tool_result_regeneration_trace(
    *,
    collector,
    reflection,
    farm_id: int,
    session_id: str | None,
    intent: str,
    user_msg: str,
    response: AIMessage,
) -> None:
    try:
        collector.record(
            node_type="reflection_check",
            node_name="post_tool_result_regeneration",
            input_data={
                "farm_id": farm_id,
                "session_id": session_id,
                "intent": intent,
                "user_message": user_msg[:500],
                "response_preview": str(response.content or "")[:200],
            },
            output_data=reflection.to_trace_payload(),
        )
    except Exception:
        return


def _record_response_and_result(
    *,
    response: AIMessage,
    invoke_meta: dict,
    route_context: dict,
    llm_context: dict,
    prompt_context: dict,
    normal_msgs: list[ToolMessage],
    farm_id: int,
    intent: str,
    user_msg: str,
) -> dict:
    response, _token_usage = _node_helpers._record_llm_response(
        response=response,
        collector=route_context["collector"],
        model_role=llm_context["model_role"],
        circuit_key=invoke_meta["circuit_key"],
        model_name=invoke_meta["model_name"],
        duration_ms=invoke_meta["duration_ms"],
        selected_tools=llm_context["selected_tools"],
        selected_tool_names=llm_context["selected_tool_names"],
        normal_msgs=normal_msgs,
        farm_id=farm_id,
        session_id=route_context["session_id"],
        intent=intent,
        user_msg=user_msg,
        plan_draft_payload=route_context["plan_draft_payload"],
        input_summary=prompt_context["input_summary"],
        extract_token_usage_func=extract_token_usage,
        extract_tokens_used_func=_extract_tokens_used,
        tool_choice=llm_context["tool_choice"],
        message_count=len(prompt_context["messages"]),
    )
    _node_helpers._record_final_reply_data_source_trace(
        collector=route_context["collector"],
        messages=prompt_context["messages"],
    )
    return {
        "messages": [response],
        "router_decision": route_context["router_decision"],
        "plan_draft": route_context["plan_draft_payload"],
        "context_bundle": prompt_context["context_bundle"],
        "selected_tool_names": llm_context["selected_tool_names"],
        "trace_round_index": route_context["trace_round_index"],
    }


__all__ = ["_invoke_and_repair_response", "_record_response_and_result"]
