"""Agent Runtime 节点实现。"""

import logging
import re

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END

from app.core.llm import get_llm
from app.agent.runtime.llm_node_steps import (
    _invoke_and_repair_response,
    _record_response_and_result,
)
from app.agent.runtime.llm_prompt import _compose_system_text, _prepare_context_bundle
from app.agent.runtime.messages import (
    _find_last_human_message,
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


async def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点 — 使用模板渲染 system prompt，带上下文压缩。"""
    messages = state["messages"]
    direct_tool_response, tool_msgs, normal_msgs = _direct_tool_response(
        state, messages
    )
    if direct_tool_response is not None:
        return direct_tool_response

    farm_id, rejection_response = _farm_id_or_rejection(state)
    if rejection_response is not None:
        return rejection_response

    (
        intent,
        user_msg,
        route_context,
        llm_context,
        prompt_context,
    ) = await _prepare_node_contexts(
        state=state,
        messages=messages,
        tool_msgs=tool_msgs,
        normal_msgs=normal_msgs,
        farm_id=farm_id,
    )
    response, invoke_meta = await _invoke_and_repair_response(
        farm_id=farm_id,
        user_msg=user_msg,
        route_context=route_context,
        llm_context=llm_context,
        prompt_context=prompt_context,
        get_llm_func=get_llm,
        bind_llm_func=_bind_llm_for_tools,
        max_retries=settings.ai.failover_max_retries,
    )
    return _record_response_and_result(
        response=response,
        invoke_meta=invoke_meta,
        route_context=route_context,
        llm_context=llm_context,
        prompt_context=prompt_context,
        normal_msgs=normal_msgs,
        farm_id=farm_id,
        intent=intent,
        user_msg=user_msg,
    )


def _direct_tool_response(
    state: AgentState, messages: list
) -> tuple[dict | None, list, list]:
    tool_msgs, pending_msgs, normal_msgs = _split_tool_messages(messages)
    direct_response = _node_helpers._direct_tool_message_response(
        state,
        pending_msgs,
        normal_msgs,
    )
    return direct_response, tool_msgs, normal_msgs


def _farm_id_or_rejection(state: AgentState) -> tuple[int | None, dict | None]:
    farm_id = state.get("farm_id", 1)
    if not isinstance(farm_id, int) or farm_id <= 0:
        return None, {
            "messages": [AIMessage(content="缺少可信农场上下文，无法继续处理。")]
        }
    quota_response = _quota_rejection_response(state.get("user_id"))
    if quota_response is not None:
        return farm_id, quota_response
    return farm_id, None


async def _prepare_node_contexts(
    *,
    state: AgentState,
    messages: list,
    tool_msgs: list,
    normal_msgs: list[ToolMessage],
    farm_id: int,
) -> tuple:
    tools = get_langchain_tools(farm_id=farm_id, farm_uid=state.get("farm_uid"))
    has_tool_results = bool(tool_msgs)
    intent = state.get("intent", "agent")
    user_msg = _find_last_human_message(messages)
    route_context = _prepare_route_context(
        state=state,
        messages=messages,
        normal_msgs=normal_msgs,
        tools=tools,
        farm_id=farm_id,
        user_msg=user_msg,
        has_tool_results=has_tool_results,
    )
    llm_context = _prepare_llm_binding(
        intent=intent,
        tools=tools,
        selected_names=route_context["selected_names"],
        router_decision=route_context["router_decision"],
        should_record_router_trace=route_context["should_record_router_trace"],
        collector=route_context["collector"],
        user_msg=user_msg,
    )
    prompt_context = await _prepare_llm_prompt(
        state=state,
        farm_id=farm_id,
        intent=intent,
        has_tool_results=has_tool_results,
        route_context=route_context,
        llm_context=llm_context,
    )
    return intent, user_msg, route_context, llm_context, prompt_context


def _split_tool_messages(messages: list) -> tuple[list, list, list]:
    tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
    pending_msgs = [m for m in tool_msgs if is_pending_tool_message(m)]
    normal_msgs = [m for m in tool_msgs if not is_pending_tool_message(m)]
    return tool_msgs, pending_msgs, normal_msgs


def _prepare_route_context(
    *,
    state: AgentState,
    messages: list,
    normal_msgs: list[ToolMessage],
    tools: list,
    farm_id: int,
    user_msg: str,
    has_tool_results: bool,
) -> dict:
    router_decision = _resolve_router_decision(
        state=state,
        normal_msgs=normal_msgs,
        user_msg=user_msg,
        tools=tools,
    )
    trace_round_index = increment_round()
    collector = get_collector()
    session_id = state.get("session_id")
    plan_draft_payload, should_record_router_trace = _resolve_plan_trace(
        state=state,
        collector=collector,
        router_decision=router_decision,
        user_msg=user_msg,
        farm_id=farm_id,
        session_id=session_id,
        has_tool_results=has_tool_results,
    )
    selected_names = _node_helpers._resolve_selected_names(
        router_decision=router_decision,
        messages=messages,
        tools=tools,
        prepared_selected_tool_names=state.get("selected_tool_names"),
        has_tool_results=has_tool_results,
        is_operation_work_order_clarification_func=(
            _is_operation_work_order_clarification
        ),
        append_tool_name_once_func=_append_tool_name_once,
    )
    return {
        "router_decision": router_decision,
        "trace_round_index": trace_round_index,
        "collector": collector,
        "session_id": session_id,
        "plan_draft_payload": plan_draft_payload,
        "should_record_router_trace": should_record_router_trace,
        "selected_names": selected_names,
    }


def _resolve_router_decision(
    *,
    state: AgentState,
    normal_msgs: list[ToolMessage],
    user_msg: str,
    tools: list,
) -> RouterDecision:
    return _node_helpers._resolve_router_decision(
        prepared_router_decision=state.get("router_decision"),
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


def _resolve_plan_trace(
    *,
    state: AgentState,
    collector,
    router_decision: RouterDecision,
    user_msg: str,
    farm_id: int,
    session_id: str | None,
    has_tool_results: bool,
) -> tuple[dict | None, bool]:
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
    return plan_draft_payload, should_record_router_trace


def _prepare_llm_binding(
    *,
    intent: str,
    tools: list,
    selected_names: list[str],
    router_decision: RouterDecision,
    should_record_router_trace: bool,
    collector,
    user_msg: str,
) -> dict:
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
    return {
        "model_role": model_role,
        "raw_llm": raw_llm,
        "llm": llm,
        "selected_tools": selected_tools,
        "selected_tool_names": [t.name for t in selected_tools],
        "tool_choice": tool_choice,
    }


async def _prepare_llm_prompt(
    *,
    state: AgentState,
    farm_id: int,
    intent: str,
    has_tool_results: bool,
    route_context: dict,
    llm_context: dict,
) -> dict:
    context_bundle, farm_ctx = await _prepare_context_bundle(
        prepared_context_bundle=state.get("context_bundle"),
        farm_id=farm_id,
        intent=intent,
        selected_tool_names=llm_context["selected_tool_names"],
        router_decision=route_context["router_decision"],
        user_id=state.get("user_id"),
        session_id=route_context["session_id"],
    )
    system_text, prompt_scene = _compose_system_text(
        prepared_system_prompt=state.get("system_prompt"),
        farm_id=farm_id,
        farm_ctx=farm_ctx,
        selected_tool_names=llm_context["selected_tool_names"],
        has_tool_results=has_tool_results,
        router_decision=route_context["router_decision"],
    )
    system_text = _node_helpers._append_runtime_context(system_text, context_bundle)

    system, messages, input_summary = _node_helpers._record_prompt_budget(
        collector=route_context["collector"],
        system_text=system_text,
        prompt_scene=prompt_scene,
        context_bundle=context_bundle,
        state=state,
        compact_messages_func=sliding_window_compact,
        find_last_human_message_func=_find_last_human_message,
    )
    return {
        "context_bundle": context_bundle,
        "farm_ctx": farm_ctx,
        "system_text": system_text,
        "system": system,
        "messages": messages,
        "input_summary": input_summary,
    }


__all__ = [
    "_llm_node",
    "_parallel_tool_node",
    "_should_continue",
]
