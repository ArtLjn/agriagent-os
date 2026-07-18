"""Agent Runtime 节点实现。"""

import asyncio
import logging
import re
import time as _time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END

from app.core.llm import get_llm
from app.prompt.cache import get_prompt_cache  # harness-exempt: 迁移期 prompt fallback
from app.prompt.composer import get_composer  # harness-exempt: 迁移期 prompt fallback
from app.agent.runtime.llm_support import (
    _LLM_SEMAPHORE,
    _build_circuit_key,
    _get_farm_context,
    _get_runtime_context_bundle,
    _get_season,
    _record_llm_failure,
    _record_llm_success,
    _warm_tool_caches,
)
from app.agent.runtime.chat_fallbacks import (
    SYSTEM_BASE_SCENE,
    retry_no_tool_json_leak,
    select_system_prompt_scene,
)
from app.agent.runtime.direct_routing import (
    filter_tool_calls_by_selected,
)
from app.agent.runtime.messages import (
    _detect_missed_tool_call,
    _extract_tokens_used,
    _extract_tool_calls_from_content,
    _find_last_human_message,
    extract_token_usage,
    sliding_window_compact,
)
from app.agent.runtime import node_helpers as _node_helpers
from app.agent.runtime.support import QUOTA_REJECT_MESSAGES, check_quota
from app.agent.runtime.tool_executor import _parallel_tool_node
from app.agent.router import RouterDecision
from app.skills import get_langchain_tools
from app.agent.state import AgentState
from app.agent.router.tool_selector import expand_by_chain as _expand_by_chain
from app.agent.router.tool_selector import select_tools as _select_tools
from app.core.config import settings
from app.core.date_context import get_request_date
from app.context.models import ContextBundle
from app.infra.pending_actions import is_pending_tool_message
from app.infra.trace_collector import get_collector
from app.infra.trace_context import increment_round

logger = logging.getLogger(__name__)
expand_by_chain = _expand_by_chain
select_tools = _select_tools

_WORK_ORDER_CLARIFICATION_RE = re.compile(
    r"(?:创建|生成|安排|记录).{0,12}(?:农事)?作业单|创建农事作业单"
)


def _should_continue(state: AgentState) -> str:
    """判断是否需要继续调用工具。"""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def _is_operation_work_order_clarification(messages: list) -> bool:
    """判断当前输入是否是在补充上一轮作业单追问。"""
    seen_current_human = False
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            if not seen_current_human:
                seen_current_human = True
                continue
            return False
        if seen_current_human and isinstance(msg, AIMessage):
            content = str(msg.content or "")
            return bool(_WORK_ORDER_CLARIFICATION_RE.search(content))
    return False


def _append_tool_name_once(names: list[str], tool_name: str, tools: list) -> list[str]:
    """在工具存在时追加候选工具，保持顺序且不重复。"""
    if tool_name in names:
        return names
    available = {tool.name for tool in tools}
    if tool_name not in available:
        return names
    return [*names, tool_name]


def _get_classifier():
    """兼容旧 graph 入口导出的 classifier 工厂。"""
    return None


def _quota_rejection_response(user_id: int | None) -> dict | None:
    """检查 token quota，返回拒绝响应或继续执行。"""
    quota = check_quota(user_id)
    quota_allowed = quota if isinstance(quota, bool) else quota.allowed
    exceeded_period = None if isinstance(quota, bool) else quota.exceeded_period
    if quota_allowed:
        return None

    action = settings.token_quota.over_quota_action
    if action == "reject":
        logger.warning(
            "Token 配额超限，拒绝调用（reject 模式）| period=%s",
            exceeded_period,
        )
        content = QUOTA_REJECT_MESSAGES.get(
            exceeded_period,
            "用量已达上限，请稍后再试。",
        )
        return {"messages": [AIMessage(content=content)]}
    if action == "warn":
        logger.warning(
            "Token 配额超限，继续调用（warn 模式）| period=%s",
            exceeded_period,
        )
    return None


def _bind_llm_for_tools(
    raw_llm,
    selected_tools: list,
    *,
    log_no_tools: bool = True,
    tool_choice: str = "auto",
):
    """按配置绑定可用工具。"""
    if selected_tools:
        kwargs: dict = {}
        if settings.ai.parallel_tool_calls:
            kwargs["parallel_tool_calls"] = True
        if tool_choice == "required":
            kwargs["tool_choice"] = "required"
        return raw_llm.bind_tools(selected_tools, **kwargs)
    if log_no_tools:
        logger.info("无匹配工具，LLM 直接回复（闲聊模式）")
    return raw_llm


async def _prepare_context_bundle(
    *,
    prepared_context_bundle,
    farm_id: int,
    intent: str,
    selected_tool_names: list[str],
    router_decision: RouterDecision,
    user_id: int | None,
    session_id: str | None,
):
    """准备 runtime context bundle 和 farm context。"""
    if prepared_context_bundle is not None:
        if not isinstance(prepared_context_bundle, ContextBundle):
            raise TypeError("prepared context_bundle must be ContextBundle")
        context_bundle = prepared_context_bundle
        farm_ctx = await _get_farm_context(farm_id)
    else:
        context_bundle, farm_ctx = await _get_runtime_context_bundle(
            farm_id=farm_id,
            intent=intent,
            selected_tool_names=selected_tool_names,
            context_dependencies=router_decision.context_dependencies,
            user_id=user_id,
            session_id=session_id,
        )
    if not context_bundle.blocks and farm_ctx.get("display_name") == "农友":
        farm_ctx = await _get_farm_context(farm_id)
    return context_bundle, farm_ctx


def _compose_system_text(
    *,
    prepared_system_prompt: str | None,
    farm_id: int,
    farm_ctx: dict,
    selected_tool_names: list[str],
    has_tool_results: bool,
    router_decision: RouterDecision,
) -> tuple[str, str]:
    """渲染 system prompt，保持原有缓存 key 与 scene 选择。"""
    if prepared_system_prompt:
        return prepared_system_prompt, "prepared"

    current_date = get_request_date()
    date_str = str(current_date)
    current_season = _get_season(current_date)
    prompt_scene = select_system_prompt_scene(
        selected_tool_names=selected_tool_names,
        has_tool_results=has_tool_results,
        router_decision=router_decision,
    )
    assistant_role = farm_ctx.get("assistant_role", "warm")
    prompt_variables = {
        "display_name": farm_ctx["display_name"],
        "farm_location": farm_ctx["farm_location"],
        "farm_coords": farm_ctx["farm_coords"],
        "current_season": current_season,
        "active_crops": farm_ctx["active_crops"],
        "assistant_role": assistant_role,
        "assistant_role_prompt": farm_ctx.get("assistant_role_prompt", ""),
    }
    if prompt_scene == SYSTEM_BASE_SCENE:
        prompt_cache = get_prompt_cache()
        cache_date_key = f"{date_str}:{assistant_role}"
        cached_prompt = prompt_cache.get(farm_id=farm_id, date_str=cache_date_key)
        if cached_prompt is not None:
            return cached_prompt, prompt_scene
        system_text = get_composer().compose(
            prompt_scene,
            variables=prompt_variables,
            current_date=current_date,
        )
        prompt_cache.set(farm_id=farm_id, date_str=cache_date_key, value=system_text)
        return system_text, prompt_scene

    system_text = get_composer().compose(
        prompt_scene,
        variables=prompt_variables,
        current_date=current_date,
    )
    return system_text, prompt_scene


async def _invoke_llm_with_retry(
    *,
    model_role: str,
    raw_llm,
    llm,
    selected_tools: list,
    system: SystemMessage,
    messages: list,
    collector,
    input_summary: str,
    tool_choice: str = "auto",
):
    """执行 LLM 调用和请求内重试。"""
    start = _time.perf_counter()
    max_retries = settings.ai.failover_max_retries
    response = None
    circuit_key = _build_circuit_key(raw_llm)

    async with _LLM_SEMAPHORE:
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    raw_llm = get_llm(role=model_role)
                    circuit_key = _build_circuit_key(raw_llm)
                    llm = _bind_llm_for_tools(
                        raw_llm,
                        selected_tools,
                        log_no_tools=False,
                        tool_choice=tool_choice,
                    )
                response = await llm.ainvoke([system] + messages)
                _record_llm_success(circuit_key)
                break
            except Exception as exc:
                duration_ms = int((_time.perf_counter() - start) * 1000)
                model_name = getattr(raw_llm, "model_name", "unknown")
                _record_llm_failure(circuit_key, exc)

                from app.core.llm_client_manager import ErrorLevel, classify_error

                error_level = classify_error(exc)
                if error_level == ErrorLevel.MODEL:
                    logger.warning(
                        "LLM 不可恢复错误，跳过重试 | key=%s | model=%s | level=%s",
                        circuit_key,
                        model_name,
                        error_level.value,
                    )
                    collector.record(
                        node_type="llm_call",
                        node_name=model_name,
                        input_data=input_summary,
                        duration_ms=duration_ms,
                        error_message=str(exc),
                    )
                    raise

                logger.warning(
                    "LLM 重试 | attempt=%d/%d | key=%s | model=%s | latency_ms=%d | error=%s",
                    attempt + 1,
                    max_retries,
                    circuit_key,
                    model_name,
                    duration_ms,
                    str(exc)[:120],
                )
                if attempt == max_retries - 1:
                    collector.record(
                        node_type="llm_call",
                        node_name=model_name,
                        input_data=input_summary,
                        duration_ms=duration_ms,
                        error_message=str(exc),
                    )
                    raise

    duration_ms = int((_time.perf_counter() - start) * 1000)
    model_name = getattr(raw_llm, "model_name", "unknown")
    return response, raw_llm, llm, circuit_key, duration_ms, model_name


async def _wait_for_preload(preload_task) -> None:
    """短暂等待缓存预热完成，保持原有非阻塞语义。"""
    try:
        await asyncio.wait_for(preload_task, timeout=0.1)
    except (asyncio.TimeoutError, Exception):
        pass


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
    retry_system = SystemMessage(
        content=system_text
        + "\n\n【重要提醒】用户的问题需要调用工具获取真实数据，请直接输出工具调用 JSON，不要回复文本。"
    )
    retry_messages = [retry_system] + messages
    try:
        retry_response = await llm.ainvoke(retry_messages)
        retry_calls = getattr(retry_response, "tool_calls", None) or []
        filtered_retry_calls = filter_tool_calls_by_selected(
            retry_calls, selected_tools
        )
        retry_parsed = None
        if not filtered_retry_calls:
            retry_parsed = _extract_tool_calls_from_content(
                retry_response.content or ""
            )
        if retry_parsed:
            filtered_retry_calls = filter_tool_calls_by_selected(
                retry_parsed,
                selected_tools,
            )

        if filtered_retry_calls:
            logger.info(
                "重试成功，LLM 输出了工具调用 | tools=%s",
                [tc["name"] for tc in filtered_retry_calls],
            )
            return AIMessage(
                content="",
                tool_calls=filtered_retry_calls,
                response_metadata=retry_response.response_metadata,
                id=retry_response.id,
            )

        from app.infra.pending_actions import is_write_skill

        if any(is_write_skill(tool.name) for tool in missed_tools):
            logger.warning("写操作重试后仍未输出工具调用，使用安全兜底回复")
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
        logger.warning("重试后 LLM 仍未输出工具调用，使用原回复")
    except Exception as retry_exc:
        logger.warning("重试调用失败 | error=%s", retry_exc)
    return response


async def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点 — 使用模板渲染 system prompt，带上下文压缩。"""
    messages = state["messages"]

    tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
    pending_msgs = [m for m in tool_msgs if is_pending_tool_message(m)]
    normal_msgs = [m for m in tool_msgs if not is_pending_tool_message(m)]

    direct_tool_response = _node_helpers._direct_tool_message_response(
        state,
        pending_msgs,
        normal_msgs,
    )
    if direct_tool_response is not None:
        return direct_tool_response

    prepared_system_prompt = state.get("system_prompt")
    prepared_context_bundle = state.get("context_bundle")
    prepared_selected_tool_names = state.get("selected_tool_names")
    prepared_router_decision = state.get("router_decision")

    farm_id = state.get("farm_id", 1)
    if not isinstance(farm_id, int) or farm_id <= 0:
        return {"messages": [AIMessage(content="缺少可信农场上下文，无法继续处理。")]}
    farm_uid = state.get("farm_uid")

    quota_response = _quota_rejection_response(state.get("user_id"))
    if quota_response is not None:
        return quota_response

    tools = get_langchain_tools(farm_id=farm_id, farm_uid=farm_uid)
    has_tool_results = bool(tool_msgs)
    intent = state.get("intent", "agent")
    user_msg = _find_last_human_message(messages)
    router_decision = _node_helpers._resolve_router_decision(
        prepared_router_decision=prepared_router_decision,
        normal_msgs=normal_msgs,
        user_msg=user_msg,
        tools=tools,
        route_tools_func=lambda message, runtime_tools: _node_helpers._route_tools(
            message,
            runtime_tools,
            select_tools_func=select_tools,
            default_select_tools_func=_select_tools,
        ),
    )

    trace_round_index = increment_round()
    collector = get_collector()
    session_id = state.get("session_id")
    plan_draft_payload = _node_helpers._existing_plan_draft_payload(state)
    should_record_router_trace = not has_tool_results
    if plan_draft_payload is None or should_record_router_trace:
        plan_draft_payload = _node_helpers._record_router_plan_trace(
            collector=collector,
            router_decision=router_decision,
            user_msg=user_msg,
            farm_id=farm_id,
            session_id=session_id,
        )

    selected_names = _node_helpers._resolve_selected_names(
        router_decision=router_decision,
        messages=messages,
        tools=tools,
        prepared_selected_tool_names=prepared_selected_tool_names,
        has_tool_results=has_tool_results,
        is_operation_work_order_clarification_func=(
            _is_operation_work_order_clarification
        ),
        append_tool_name_once_func=_append_tool_name_once,
    )

    model_role = "lightweight" if intent == "query" else "generation"
    raw_llm = get_llm(role=model_role)
    logger.info("模型路由 | intent=%s | role=%s", intent, model_role)
    selected_tools = [t for t in tools if t.name in selected_names]
    tool_choice = router_decision.tool_choice
    if should_record_router_trace:
        _node_helpers._record_tool_call_forced_trace(
            collector=collector,
            user_msg=user_msg,
            selected_names=selected_names,
            tool_choice=tool_choice,
            force_binding=router_decision.force_binding,
        )
    llm = _bind_llm_for_tools(raw_llm, selected_tools, tool_choice=tool_choice)

    selected_tool_names = [t.name for t in selected_tools] if selected_tools else []
    context_bundle, farm_ctx = await _prepare_context_bundle(
        prepared_context_bundle=prepared_context_bundle,
        farm_id=farm_id,
        intent=intent,
        selected_tool_names=selected_tool_names,
        router_decision=router_decision,
        user_id=state.get("user_id"),
        session_id=session_id,
    )
    system_text, prompt_scene = _compose_system_text(
        prepared_system_prompt=prepared_system_prompt,
        farm_id=farm_id,
        farm_ctx=farm_ctx,
        selected_tool_names=selected_tool_names,
        has_tool_results=has_tool_results,
        router_decision=router_decision,
    )
    system_text = _node_helpers._append_runtime_context(system_text, context_bundle)

    system, messages, input_summary = _node_helpers._record_prompt_budget(
        collector=collector,
        system_text=system_text,
        prompt_scene=prompt_scene,
        context_bundle=context_bundle,
        state=state,
        compact_messages_func=sliding_window_compact,
        find_last_human_message_func=_find_last_human_message,
    )

    # 并行缓存预热（与 LLM 调用并行执行）
    preload_task = asyncio.create_task(
        _warm_tool_caches(
            selected_tool_names,
            farm_id,
            farm_ctx,
            context_dependencies=router_decision.context_dependencies,
        )
    )

    (
        response,
        raw_llm,
        llm,
        circuit_key,
        duration_ms,
        model_name,
    ) = await _invoke_llm_with_retry(
        model_role=model_role,
        raw_llm=raw_llm,
        llm=llm,
        selected_tools=selected_tools,
        system=system,
        messages=messages,
        collector=collector,
        input_summary=input_summary,
        tool_choice=tool_choice,
    )

    await _wait_for_preload(preload_task)
    response = await _normalize_content_tool_calls(
        response=response,
        llm=llm,
        system_text=system_text,
        messages=messages,
        model_name=model_name,
        selected_tools=selected_tools,
    )
    response = await _retry_missed_tool_call(
        response=response,
        llm=llm,
        system_text=system_text,
        messages=messages,
        user_msg=user_msg,
        selected_tools=selected_tools,
    )
    response, _token_usage = _node_helpers._record_llm_response(
        response=response,
        collector=collector,
        model_role=model_role,
        circuit_key=circuit_key,
        model_name=model_name,
        duration_ms=duration_ms,
        selected_tools=selected_tools,
        selected_tool_names=selected_tool_names,
        normal_msgs=normal_msgs,
        farm_id=farm_id,
        session_id=session_id,
        intent=intent,
        user_msg=user_msg,
        plan_draft_payload=plan_draft_payload,
        input_summary=input_summary,
        extract_token_usage_func=extract_token_usage,
        extract_tokens_used_func=_extract_tokens_used,
    )

    _node_helpers._record_final_reply_data_source_trace(
        collector=collector,
        messages=messages,
    )

    return {
        "messages": [response],
        "router_decision": router_decision,
        "plan_draft": plan_draft_payload,
        "context_bundle": context_bundle,
        "selected_tool_names": selected_tool_names,
        "trace_round_index": trace_round_index,
    }


__all__ = [
    "_llm_node",
    "_parallel_tool_node",
    "_should_continue",
]
