"""Agent Runtime 节点无状态辅助逻辑。"""

import logging
import time as _time
from dataclasses import replace

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from app.agent.router import RouterDecision, SkillRouter
from app.agent.router.tool_selector import ToolSelectionResult
from app.agent.runtime.direct_routing import can_return_direct_tool_messages
from app.agent.runtime.final_prompt_budget import FinalPromptBudget
from app.agent.runtime.llm_support import _resolve_tool_choice
from app.agent.runtime.planning import (
    DomainValidator,
    attach_validation,
    plan_draft_from_router_decision,
)
from app.agent.runtime.reflection import apply_post_tool_reflection
from app.agent.state import AgentState
from app.context.models import ContextBundle
from app.context.renderer import ContextRenderer
from app.infra.pending_actions import CONTRACT_BLOCKED_MARKER, PENDING_MARKER
from app.infra.trace_context import set_round_index

logger = logging.getLogger(__name__)


def _build_data_source_payload(tool_calls: list[dict] | None) -> dict:
    """构造 final_reply_data_source trace payload。"""
    if tool_calls:
        last_tool = tool_calls[-1]
        tool_name = (
            last_tool.get("name", "unknown")
            if isinstance(last_tool, dict)
            else "unknown"
        )
        return {
            "data_source": f"tool:{tool_name}",
            "has_tool_results": True,
        }
    return {
        "data_source": "context_bundle",
        "has_tool_results": False,
    }


def _tool_messages_for_data_source(messages: list) -> list[dict] | None:
    """从消息历史里提取 final reply 真实依赖的最后一个工具名。"""
    tool_call_names: dict[str, str] = {}
    last_tool_msg: ToolMessage | None = None
    for message in messages:
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls or []:
                tool_call_id = str(tool_call.get("id") or "")
                tool_name = str(tool_call.get("name") or "")
                if tool_call_id and tool_name:
                    tool_call_names[tool_call_id] = tool_name
        elif isinstance(message, ToolMessage):
            last_tool_msg = message
    if last_tool_msg is None:
        return None
    tool_name = getattr(last_tool_msg, "name", None)
    if not tool_name:
        tool_call_id = str(getattr(last_tool_msg, "tool_call_id", "") or "")
        tool_name = tool_call_names.get(tool_call_id)
    return [{"name": tool_name or "unknown"}]


def _record_tool_call_forced_trace(
    *,
    collector,
    user_msg: str,
    selected_names: list[str],
    tool_choice: str,
    force_binding: tuple[str, ...] = (),
) -> None:
    """记录 tool_call_forced trace（LLM bind_tools 前）。失败静默。"""
    try:
        forced = set(force_binding) & set(selected_names)
        now = _time.time()
        collector.record(
            node_type="tool_selection",
            node_name="tool_call_forced",
            input_data={"user_message": user_msg[:200] if user_msg else ""},
            output_data={
                "forced_skills": sorted(forced),
                "tool_choice": tool_choice,
                "selected_tools": list(selected_names),
            },
            start_time=now,
            duration_ms=0,
        )
    except Exception:
        return


def _record_final_reply_data_source_trace(*, collector, messages: list) -> None:
    """记录 final_reply_data_source trace。失败静默。"""
    try:
        last_tool_messages_for_trace = _tool_messages_for_data_source(messages)
        now = _time.time()
        collector.record(
            node_type="response",
            node_name="final_reply_data_source",
            input_data={"has_tool_results": bool(last_tool_messages_for_trace)},
            output_data=_build_data_source_payload(last_tool_messages_for_trace),
            start_time=now,
            duration_ms=0,
        )
    except Exception:
        return


def _route_tools(
    user_msg: str,
    tools: list,
    *,
    select_tools_func,
    default_select_tools_func,
) -> RouterDecision:
    """使用 SkillRouter，兼容测试/旧入口 patch select_tools 的场景。"""
    if select_tools_func is not default_select_tools_func:
        selection = select_tools_func(user_msg, tools)
        if isinstance(selection, ToolSelectionResult):
            return RouterDecision(
                selected_tools=list(selection.tools),
                tool_choice=_resolve_tool_choice(selection),
                force_binding=tuple(sorted(selection.force_binding)),
            )
        return RouterDecision(selected_tools=list(selection))
    decision = SkillRouter().route(user_msg, tools)
    return replace(
        decision,
        selected_tools=list(decision.selected_tools),
        tool_choice="auto",
        force_binding=(),
    )


def _direct_tool_message_response(
    state: AgentState,
    pending_msgs: list[ToolMessage],
    normal_msgs: list[ToolMessage],
) -> dict | None:
    """处理无需再次进入 LLM 的 ToolMessage 结果。"""
    trace_round_index = state.get("trace_round_index")
    set_round_index(trace_round_index)
    if pending_msgs and normal_msgs:
        summaries = [str(m.content or "")[:200] for m in normal_msgs if m.content]
        confirm_parts = [_strip_direct_tool_marker(m.content) for m in pending_msgs]
        combined = "\n\n".join(summaries) + "\n\n" + "\n\n".join(confirm_parts)
        logger.info(
            "混合 ToolMessage | pending=%d normal=%d | 跳过 LLM 合并回复",
            len(pending_msgs),
            len(normal_msgs),
        )
        return {
            "messages": [AIMessage(content=combined)],
            "trace_round_index": trace_round_index,
        }
    if pending_msgs:
        confirm = _strip_direct_tool_marker(pending_msgs[-1].content)
        logger.info("检测到 pending ToolMessage，跳过 LLM 直接确认 | text=%s", confirm)
        return {
            "messages": [AIMessage(content=confirm)],
            "trace_round_index": trace_round_index,
        }
    if normal_msgs and can_return_direct_tool_messages(normal_msgs):
        content = "\n\n".join(str(msg.content or "") for msg in normal_msgs).strip()
        logger.info(
            "检测到确定性直达 ToolMessage，跳过 LLM 直接返回 | count=%d",
            len(normal_msgs),
        )
        return {
            "messages": [AIMessage(content=content)],
            "trace_round_index": trace_round_index,
        }
    return None


def _strip_direct_tool_marker(content: str) -> str:
    return (
        str(content or "")
        .replace(PENDING_MARKER, "")
        .replace(CONTRACT_BLOCKED_MARKER, "")
        .strip()
    )


def _resolve_router_decision(
    *,
    prepared_router_decision,
    normal_msgs: list[ToolMessage],
    user_msg: str,
    tools: list,
    route_tools_func,
) -> RouterDecision:
    """确定本轮路由决策，保留工具结果后不重绑工具的行为。"""
    if prepared_router_decision is not None:
        return prepared_router_decision
    if normal_msgs:
        return RouterDecision(
            selected_tools=[],
            fallback="final_answer_no_tools",
            reason="已有工具结果，final answer 默认不重新绑定工具",
        )
    return route_tools_func(user_msg, tools)


def _record_router_plan_trace(
    *,
    collector,
    router_decision: RouterDecision,
    user_msg: str,
    farm_id: int,
    session_id: str | None,
) -> dict:
    """记录 skill router trace，并返回 plan draft payload。"""
    plan_draft = plan_draft_from_router_decision(
        raw_user_input=user_msg,
        decision=router_decision,
        farm_id=farm_id,
        session_id=session_id,
    )
    plan_validation = DomainValidator().validate(plan_draft)
    plan_draft = attach_validation(plan_draft, plan_validation)
    plan_draft_payload = plan_draft.to_trace_payload()
    router_trace_payload = router_decision.to_trace_payload()
    router_trace_payload["plan_draft"] = plan_draft_payload
    collector.record(
        node_type="skill_router",
        node_name="skill_router",
        input_data={"message": user_msg[:500]},
        output_data=router_trace_payload,
        token_usage={
            "schema_token_estimate": router_decision.schema_token_estimate,
            "usage_source": "router_estimate",
        },
    )
    return plan_draft_payload


def _existing_plan_draft_payload(state: AgentState) -> dict | None:
    """读取上一轮 LLM 已生成的 plan_draft trace payload。"""
    payload = state.get("plan_draft")
    return payload if isinstance(payload, dict) else None


def _resolve_selected_names(
    *,
    router_decision: RouterDecision,
    messages: list,
    tools: list,
    prepared_selected_tool_names,
    has_tool_results: bool,
    is_operation_work_order_clarification_func,
    append_tool_name_once_func,
) -> list[str]:
    """汇总最终可绑定工具名。"""
    selected_names = list(router_decision.selected_tools)
    if is_operation_work_order_clarification_func(messages):
        selected_names = append_tool_name_once_func(
            selected_names,
            "create_operation_work_order",
            tools,
        )
    if prepared_selected_tool_names is not None:
        selected_names = list(prepared_selected_tool_names)
    if has_tool_results:
        selected_names = []
    return _enabled_selected_tool_names(selected_names, tools)


def _enabled_selected_tool_names(selected_names: list[str], tools: list) -> list[str]:
    """按 Router allowlist 过滤实际可绑定工具，disabled 工具不进入 LLM。"""
    tool_by_name = {tool.name: tool for tool in tools}
    enabled_names: list[str] = []
    for name in selected_names:
        tool = tool_by_name.get(name)
        if tool is None:
            continue
        metadata = getattr(tool, "skill_metadata", None)
        if getattr(metadata, "enabled", True) is False:
            logger.warning("跳过 disabled Skill 绑定 | name=%s", name)
            continue
        if name not in enabled_names:
            enabled_names.append(name)
    return enabled_names


def _append_runtime_context(system_text: str, context_bundle: ContextBundle) -> str:
    runtime_context_text = ContextRenderer().render_prompt_text(context_bundle)
    if not runtime_context_text:
        return system_text
    return (
        f"{system_text}\n\n<runtime_context>\n"
        f"{runtime_context_text}\n"
        f"</runtime_context>"
    )


def _record_prompt_budget(
    *,
    collector,
    system_text: str,
    prompt_scene: str,
    context_bundle: ContextBundle,
    state: AgentState,
    compact_messages_func,
    find_last_human_message_func,
) -> tuple[SystemMessage, list, str]:
    """记录 prompt 渲染与预算 trace，返回 LLM 输入。"""
    collector.record(
        node_type="prompt_render",
        node_name="system_prompt",
        input_data={
            "template": prompt_scene,
            "variables_count": 5,
            "context_blocks": [block.key for block in context_bundle.blocks],
        },
        output_data=system_text[:2000],
    )
    system = SystemMessage(content=system_text)
    messages = compact_messages_func(state["messages"])
    messages, final_budget = FinalPromptBudget().apply(system_text, messages)
    input_summary = find_last_human_message_func(state["messages"])[:200]
    collector.record(
        node_type="prompt_budget",
        node_name="final_prompt",
        input_data={
            "system_prompt": True,
            "context_blocks": [block.key for block in context_bundle.blocks],
            "messages": len(messages),
        },
        output_data=final_budget.summary(),
        token_usage={"prompt_tokens": final_budget.total_tokens},
    )
    if final_budget.over_budget:
        logger.warning(
            "最终 prompt 仍超预算 | total=%d max=%d actions=%s",
            final_budget.total_tokens,
            final_budget.max_tokens,
            final_budget.actions,
        )
    return system, messages, input_summary


# fmt: off
def _record_llm_response(
    *, response: AIMessage, collector, model_role: str, circuit_key: str,
    model_name: str, duration_ms: int, selected_tools: list,
    selected_tool_names: list[str], normal_msgs: list[ToolMessage],
    farm_id: int, session_id: str | None, intent: str, user_msg: str,
    plan_draft_payload: dict, input_summary: str, extract_token_usage_func,
    extract_tokens_used_func,
) -> tuple[AIMessage, dict | None]:
# fmt: on
    """整理最终响应、记录 LLM trace，并返回 token usage。"""
    token_usage = extract_token_usage_func(response)
    tokens = _response_token_count(response, token_usage, extract_tokens_used_func)
    _log_llm_response(
        model_role,
        circuit_key,
        model_name,
        duration_ms,
        selected_tools,
        response,
        tokens,
    )
    if response.tool_calls:
        output_summary = _tool_call_output_summary(response, model_name)
    else:
        response, output_summary = _direct_response_summary(
            response=response,
            selected_tool_names=selected_tool_names,
            normal_msgs=normal_msgs,
            farm_id=farm_id,
            session_id=session_id,
            intent=intent,
            user_msg=user_msg,
            plan_draft_payload=plan_draft_payload,
            model_name=model_name,
        )
    collector.record(
        node_type="llm_call",
        node_name=model_name,
        input_data=input_summary,
        output_data=output_summary,
        duration_ms=duration_ms,
        token_usage=token_usage,
    )
    return response, token_usage


def _response_token_count(response: AIMessage, token_usage: dict | None, fallback_func):
    if token_usage:
        return token_usage["total_tokens"]
    return fallback_func(response)


def _log_llm_response(
    model_role: str,
    circuit_key: str,
    model_name: str,
    duration_ms: int,
    selected_tools: list,
    response: AIMessage,
    tokens,
) -> None:
    logger.info(
        "LLM 调用完成 | role=%s | key=%s | model=%s | latency_ms=%d | "
        "selected_tools=%d | tool_calls=%d | tokens=%s",
        model_role,
        circuit_key,
        model_name,
        duration_ms,
        len(selected_tools),
        len(response.tool_calls or []),
        tokens if tokens is not None else "-",
    )


def _tool_call_output_summary(response: AIMessage, model_name: str) -> str:
    tool_names = [tc["name"] for tc in response.tool_calls]
    logger.info("LLM 工具选择 | tool_calls=%s | model=%s", tool_names, model_name)
    return f"tool_calls: {tool_names}"


def _direct_response_summary(
    *,
    response: AIMessage,
    selected_tool_names: list[str],
    normal_msgs: list[ToolMessage],
    farm_id: int,
    session_id: str | None,
    intent: str,
    user_msg: str,
    plan_draft_payload: dict,
    model_name: str,
) -> tuple[AIMessage, str]:
    response = _ensure_non_empty_response(response, model_name, selected_tool_names)
    response = apply_post_tool_reflection(
        response=response,
        tool_messages=normal_msgs,
        selected_tool_names=selected_tool_names,
        farm_id=farm_id,
        session_id=session_id,
        intent=intent,
        user_message=user_msg,
        plan_draft=plan_draft_payload,
    )
    content = response.content or ""
    logger.info("LLM 直接回复 | reply_len=%d | model=%s", len(content), model_name)
    return response, content[:200]


def _ensure_non_empty_response(
    response: AIMessage,
    model_name: str,
    selected_tool_names: list[str],
) -> AIMessage:
    content = response.content or ""
    if str(content).strip():
        return response
    logger.warning(
        "LLM 返回空内容，已使用兜底回复 | model=%s | selected_tools=%s",
        model_name,
        selected_tool_names,
    )
    return AIMessage(
        content="这次没有生成有效回复，请换个说法再试一次。",
        response_metadata=response.response_metadata,
        id=response.id,
    )


__all__ = [
    "_append_runtime_context",
    "_build_data_source_payload",
    "_direct_tool_message_response",
    "_enabled_selected_tool_names",
    "_existing_plan_draft_payload",
    "_record_final_reply_data_source_trace",
    "_record_llm_response",
    "_record_prompt_budget",
    "_record_router_plan_trace",
    "_record_tool_call_forced_trace",
    "_resolve_router_decision",
    "_resolve_selected_names",
    "_route_tools",
    "_tool_messages_for_data_source",
]
