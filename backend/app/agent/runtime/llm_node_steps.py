"""Agent Runtime LLM 节点后半流程步骤。"""

import asyncio

from langchain_core.messages import AIMessage, ToolMessage

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
) -> tuple[AIMessage, dict]:
    preload_task = asyncio.create_task(
        _warm_tool_caches(
            llm_context["selected_tool_names"],
            farm_id,
            prompt_context["farm_ctx"],
            context_dependencies=route_context["router_decision"].context_dependencies,
        )
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
        prompt_context=prompt_context,
        user_msg=user_msg,
        selected_tools=llm_context["selected_tools"],
        model_name=invoke_meta["model_name"],
    )
    return response, invoke_meta


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
    )


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
