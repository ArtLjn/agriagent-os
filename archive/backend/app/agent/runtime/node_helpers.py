"""Agent Runtime 节点无状态辅助逻辑。"""

import logging
import time as _time
from dataclasses import replace
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage

from app.agent.router import RouterDecision, SkillRouter
from app.agent.router.tool_selector import ToolSelectionResult
from app.agent.runtime.direct_routing import can_return_direct_tool_messages
from app.agent.runtime.exception_logging import log_silent_exception
from app.agent.runtime.final_prompt_budget import FinalPromptBudget
from app.agent.runtime.llm_support import _resolve_tool_choice
from app.agent.runtime.planning import (
    DomainValidator,
    attach_validation,
    plan_draft_from_router_decision,
)
from app.agent.runtime.reflection import apply_post_tool_reflection
from app.agent.state import AgentState
from app.context.pipeline import (
    is_tool_result_compressed,
    safe_preview,
    safe_trace_value,
)
from app.context.core.models import ContextBundle
from app.context.core.registry import block_spec
from app.context.pipeline import ContextRenderer
from app.infra.pending_actions import CONTRACT_BLOCKED_MARKER, PENDING_MARKER
from app.infra.trace_diagnostics import skill_router_trace_payload
from app.infra.trace_context import set_round_index
from app.shared.config import settings

logger = logging.getLogger(__name__)


def _elapsed_trace_ms(started_at: float) -> int:
    """返回用于 trace 展示的毫秒耗时，避免亚毫秒步骤显示为 0ms。"""
    return max(1, int((_time.perf_counter() - started_at) * 1000))


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
        started_at = _time.perf_counter()
        wall_started_at = _time.time()
        forced = set(force_binding) & set(selected_names)
        collector.record(
            node_type="tool_selection",
            node_name="tool_call_forced",
            input_data={"user_message": user_msg[:200] if user_msg else ""},
            output_data={
                "forced_skills": sorted(forced),
                "tool_choice": tool_choice,
                "selected_tools": list(selected_names),
                "bind_tools": list(selected_names),
                "reason": _tool_selection_reason(tool_choice, forced),
            },
            start_time=wall_started_at,
            duration_ms=_elapsed_trace_ms(started_at),
        )
    except Exception as exc:
        log_silent_exception(
            logger,
            level=logging.DEBUG,
            function="_record_tool_call_forced_trace",
            agent_event="node_helpers.record_tool_call_forced_trace",
            exc=exc,
        )
        return


def _tool_selection_reason(tool_choice: str, forced: set[str]) -> str:
    if forced:
        return "存在强制绑定工具，LLM 必须调用工具"
    if tool_choice == "none":
        return "工具结果已返回，最终回复阶段不再绑定工具"
    return "读工具允许 LLM auto 选择，不强制 tool_call"


def _record_final_reply_data_source_trace(
    *,
    collector,
    messages: list,
    tool_results: list | None = None,
) -> None:
    """记录 final_reply_data_source trace。失败静默。"""
    try:
        started_at = _time.perf_counter()
        wall_started_at = _time.time()
        last_tool_messages_for_trace = _tool_results_for_data_source(
            tool_results
        ) or _tool_messages_for_data_source(messages)
        collector.record(
            node_type="response",
            node_name="final_reply_data_source",
            input_data={"has_tool_results": bool(last_tool_messages_for_trace)},
            output_data=_build_data_source_payload(last_tool_messages_for_trace),
            start_time=wall_started_at,
            duration_ms=_elapsed_trace_ms(started_at),
        )
    except Exception as exc:
        log_silent_exception(
            logger,
            level=logging.DEBUG,
            function="_record_final_reply_data_source_trace",
            agent_event="node_helpers.record_final_reply_data_source_trace",
            exc=exc,
        )
        return


def _tool_results_for_data_source(tool_results: list | None) -> list[dict] | None:
    """从 FinalResponseRequest.tool_results 提取 final reply 真实依赖的工具名。"""
    if not tool_results:
        return None
    last_tool_result = tool_results[-1]
    tool_name = str(getattr(last_tool_result, "tool_name", "") or "unknown")
    return [{"name": tool_name}]


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
        summaries = [
            str(m.content or "")[:200]
            for m in normal_msgs
            if m.content and not _is_pending_plan_placeholder(m.content)
        ]
        confirm_parts = [_strip_direct_tool_marker(m.content) for m in pending_msgs]
        combined = "\n\n".join([*summaries, *confirm_parts]).strip()
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


def _is_pending_plan_placeholder(content: str) -> bool:
    return str(content or "").strip() == "已纳入待确认计划。"


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
    routing_augmented_input: str | None = None,
    farm_id: int,
    session_id: str | None,
    duration_ms: int | None = None,
) -> dict:
    """记录 skill router trace，并返回 plan draft payload。"""
    plan_draft = plan_draft_from_router_decision(
        raw_user_input=user_msg,
        routing_augmented_input=routing_augmented_input,
        decision=router_decision,
        farm_id=farm_id,
        session_id=session_id,
    )
    plan_validation = DomainValidator().validate(plan_draft)
    plan_draft = attach_validation(plan_draft, plan_validation)
    plan_draft_payload = plan_draft.to_trace_payload()
    router_trace_payload = skill_router_trace_payload(
        router_decision,
        plan_draft_payload=plan_draft_payload,
    )
    collector.record(
        node_type="skill_router",
        node_name="skill_router",
        input_data={
            "message": user_msg[:500],
            "routing_augmented": bool(routing_augmented_input),
        },
        output_data=router_trace_payload,
        token_usage={
            "schema_token_estimate": router_decision.schema_token_estimate,
            "usage_source": "router_estimate",
        },
        duration_ms=duration_ms,
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


def _trace_safe_value(value: Any) -> Any:
    """把 LangChain 消息字段转换成可稳定写入 trace 的基础 JSON 值。"""
    return safe_trace_value(value)


def _message_role_for_trace(message: BaseMessage) -> str:
    message_type = str(getattr(message, "type", "") or "").lower()
    return {
        "human": "user",
        "ai": "assistant",
        "system": "system",
        "tool": "tool",
    }.get(message_type, message_type or message.__class__.__name__)


def _message_trace_payload(message: BaseMessage, index: int) -> dict[str, Any]:
    content = getattr(message, "content", "")
    compressed = is_tool_result_compressed(content) or str(content or "").startswith(
        "早期对话摘要"
    )
    payload: dict[str, Any] = {
        "index": index,
        "role": _message_role_for_trace(message),
        "type": str(getattr(message, "type", "") or message.__class__.__name__),
        "content": safe_preview(str(content or ""), max_chars=1000),
        "content_preview": safe_preview(str(content or ""), max_chars=240),
        "tool_calls": [],
        "tool_call_id": None,
        "compressed": compressed,
    }
    name = getattr(message, "name", None)
    if name:
        payload["name"] = safe_preview(str(name), max_chars=120)
    additional_kwargs = getattr(message, "additional_kwargs", None)
    if additional_kwargs:
        payload["additional_kwargs"] = _trace_safe_value(additional_kwargs)
    if isinstance(message, AIMessage):
        tool_calls = getattr(message, "tool_calls", None)
        invalid_tool_calls = getattr(message, "invalid_tool_calls", None)
        if tool_calls:
            payload["tool_calls"] = _trace_safe_value(tool_calls)
        if invalid_tool_calls:
            payload["invalid_tool_calls"] = _trace_safe_value(invalid_tool_calls)
    if isinstance(message, ToolMessage):
        payload["tool_call_id"] = str(message.tool_call_id or "")
        status = getattr(message, "status", None)
        if status:
            payload["status"] = safe_preview(str(status), max_chars=80)
    return payload


def _runtime_context_sections_payload(context_bundle: ContextBundle) -> list[dict]:
    """构造最终入模 runtime context 的安全分区快照。"""
    document = ContextRenderer().render_document(context_bundle)
    sections: list[dict] = []
    for section in document.sections:
        if not section.blocks:
            continue
        sections.append(
            {
                "name": section.name,
                "token_estimate": section.token_estimate,
                "blocks": [
                    _runtime_context_block_payload(block, dropped=False)
                    for block in section.blocks
                ],
            }
        )
    return sections


def _runtime_context_block_payload(block, *, dropped: bool) -> dict[str, Any]:
    spec = block_spec(block.key)
    compressed = bool(block.is_compressed)
    decision = "dropped" if dropped else "compressed" if compressed else "selected"
    original_tokens = block.metadata.get("original_tokens")
    payload: dict[str, Any] = {
        "key": safe_preview(block.key, max_chars=120),
        "category": str(spec.category.value if spec else "unknown"),
        "source": safe_preview(block.source, max_chars=120),
        "decision": decision,
        "compressed": compressed,
        "dropped": dropped,
        "priority": block.priority,
        "required": block.required,
        "token_estimate": block.token_estimate or 0,
        "content_preview": safe_preview(block.content, max_chars=240),
        "content": safe_preview(block.content, max_chars=1000),
        "reason": safe_preview(block.reason, max_chars=160),
    }
    if original_tokens is not None:
        payload["original_tokens"] = original_tokens
    return payload


def _compression_payload(
    *, context_bundle: ContextBundle, message_payloads: list[dict], final_budget
) -> dict[str, Any]:
    tool_result_count = sum(
        1
        for message in message_payloads
        if message.get("role") == "tool" and message.get("compressed") is True
    )
    return {
        "context_compressed_count": len(context_bundle.compressed_blocks),
        "context_dropped_count": len(context_bundle.dropped_blocks),
        "message_compressed_count": sum(
            1 for message in message_payloads if message.get("compressed") is True
        ),
        "tool_result_compressed_count": tool_result_count,
        "events": safe_trace_value(
            getattr(final_budget, "compression_events", []),
            max_chars=500,
        ),
    }


def _record_final_llm_context_trace(
    *,
    collector,
    system_text: str,
    messages: list[BaseMessage],
    context_bundle: ContextBundle,
    final_budget,
) -> None:
    """记录预算压缩后真正送入 LLM 的上下文快照。失败静默。"""
    try:
        started_at = _time.perf_counter()
        wall_started_at = _time.time()
        context_blocks = _context_block_keys(context_bundle)
        message_payloads = [
            _message_trace_payload(message, index)
            for index, message in enumerate(messages)
        ]
        budget_summary = safe_trace_value(final_budget.summary(), max_chars=1000)
        collector.record(
            node_type="prompt_budget",
            node_name="final_llm_context",
            input_data={
                "system_prompt": True,
                "context_blocks": context_blocks,
                "message_count": len(messages),
            },
            output_data={
                "schema_version": 2,
                "system_prompt": safe_preview(system_text, max_chars=4000),
                "runtime_context": {
                    "sections": _runtime_context_sections_payload(context_bundle),
                    "context_pack": safe_trace_value(
                        context_bundle.metadata.get("context_pack"),
                        max_chars=1000,
                    ),
                },
                "messages": message_payloads,
                "context_blocks": context_blocks,
                "budget": budget_summary,
                "compression": _compression_payload(
                    context_bundle=context_bundle,
                    message_payloads=message_payloads,
                    final_budget=final_budget,
                ),
            },
            token_usage={"prompt_tokens": final_budget.total_tokens},
            start_time=wall_started_at,
            duration_ms=_elapsed_trace_ms(started_at),
        )
    except Exception as exc:
        log_silent_exception(
            logger,
            level=logging.WARNING,
            function="_record_final_llm_context_trace",
            agent_event="node_helpers.record_final_llm_context_trace",
            exc=exc,
        )
        return


def _context_block_keys(context_bundle: ContextBundle) -> list[str]:
    return [block.key for block in context_bundle.blocks]


def _record_system_prompt_trace(
    *,
    collector,
    system_text: str,
    prompt_scene: str,
    context_blocks: list[str],
    duration_ms: int | None = None,
) -> None:
    collector.record(
        node_type="prompt_render",
        node_name="system_prompt",
        input_data={
            "template": prompt_scene,
            "variables_count": 5,
            "context_blocks": context_blocks,
        },
        output_data=safe_preview(system_text, max_chars=2000),
        duration_ms=duration_ms,
    )


def _record_final_prompt_budget_trace(
    *,
    collector,
    context_blocks: list[str],
    message_count: int,
    final_budget,
    duration_ms: int | None = None,
) -> None:
    collector.record(
        node_type="prompt_budget",
        node_name="final_prompt",
        input_data={
            "system_prompt": True,
            "context_blocks": context_blocks,
            "messages": message_count,
        },
        output_data=final_budget.summary(),
        token_usage={"prompt_tokens": final_budget.total_tokens},
        duration_ms=duration_ms,
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
    system_prompt_duration_ms: int | None = None,
) -> tuple[SystemMessage, list, str]:
    """记录 prompt 渲染与预算 trace，返回 LLM 输入。"""
    context_blocks = _context_block_keys(context_bundle)
    _record_system_prompt_trace(
        collector=collector,
        system_text=system_text,
        prompt_scene=prompt_scene,
        context_blocks=context_blocks,
        duration_ms=system_prompt_duration_ms,
    )
    system = SystemMessage(content=system_text)
    final_prompt_started_at = _time.perf_counter()
    messages = compact_messages_func(state["messages"])
    messages, final_budget = FinalPromptBudget().apply(system_text, messages)
    final_prompt_duration_ms = _elapsed_trace_ms(final_prompt_started_at)
    input_summary = find_last_human_message_func(state["messages"])[:200]
    _record_final_prompt_budget_trace(
        collector=collector,
        context_blocks=context_blocks,
        message_count=len(messages),
        final_budget=final_budget,
        duration_ms=final_prompt_duration_ms,
    )
    _record_final_llm_context_trace(
        collector=collector,
        system_text=system_text,
        messages=messages,
        context_bundle=context_bundle,
        final_budget=final_budget,
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
    extract_tokens_used_func, tool_choice: str = "auto", message_count: int = 0,
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
        input_data=_llm_trace_input(
            input_summary=input_summary,
            circuit_key=circuit_key,
            model_name=model_name,
            model_role=model_role,
            selected_tool_names=selected_tool_names,
            tool_choice=tool_choice,
            message_count=message_count,
        ),
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


def _tool_call_output_summary(response: AIMessage, model_name: str) -> dict:
    tool_names = [tc["name"] for tc in response.tool_calls]
    logger.info("LLM 工具选择 | tool_calls=%s | model=%s", tool_names, model_name)
    return {
        "finish_reason": "tool_calls",
        "tool_calls": [_tool_call_trace_payload(tc) for tc in response.tool_calls],
        "reply_preview": None,
        "reply_len": 0,
    }


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
) -> tuple[AIMessage, dict]:
    response = _ensure_non_empty_response(response, model_name, selected_tool_names)
    if not _should_skip_post_tool_reflection(response):
        response = apply_post_tool_reflection(
            response=response,
            tool_messages=normal_msgs,
            selected_tool_names=selected_tool_names,
            farm_id=farm_id,
            session_id=session_id,
            intent=intent,
            user_message=user_msg,
            plan_draft=plan_draft_payload,
            fact_sources=_fact_sources_from_plan_draft_payload(plan_draft_payload),
        )
    content = response.content or ""
    logger.info("LLM 直接回复 | reply_len=%d | model=%s", len(content), model_name)
    return response, {
        "finish_reason": "stop",
        "tool_calls": [],
        "reply_preview": safe_preview(str(content), max_chars=1000),
        "reply_len": len(str(content)),
    }


def _is_output_guard_fail_closed(response: AIMessage) -> bool:
    output_guard = (response.response_metadata or {}).get("output_guard")
    if not isinstance(output_guard, dict):
        return False
    return output_guard.get("action") == "fail_closed"


def _should_skip_post_tool_reflection(response: AIMessage) -> bool:
    if _is_output_guard_fail_closed(response):
        return True
    final_response = (response.response_metadata or {}).get("final_response")
    if not isinstance(final_response, dict):
        return False
    return final_response.get("boundary") == "final_response"


def _fact_sources_from_plan_draft_payload(plan_draft_payload: dict) -> dict:
    for key in ("fact_sources", "facts"):
        value = plan_draft_payload.get(key)
        if isinstance(value, dict) and value:
            return value
    planning_context = plan_draft_payload.get("planning_context") or plan_draft_payload.get(
        "context"
    )
    if isinstance(planning_context, dict):
        for key in ("fact_sources", "facts"):
            value = planning_context.get(key)
            if isinstance(value, dict) and value:
                return value
        slots = planning_context.get("slots")
        if isinstance(slots, dict):
            nested_slots = slots.get("slots")
            if isinstance(nested_slots, dict) and nested_slots:
                return nested_slots
    return {}


def _llm_trace_input(
    *,
    input_summary: str,
    circuit_key: str,
    model_name: str,
    model_role: str,
    selected_tool_names: list[str],
    tool_choice: str,
    message_count: int,
) -> dict:
    provider = circuit_key.split("/", 1)[0] if "/" in circuit_key else "unknown"
    return {
        "input_summary": input_summary,
        "provider": provider,
        "model": model_name,
        "role": model_role,
        "selected_tools": list(selected_tool_names),
        "tool_choice": tool_choice,
        "message_count": message_count,
        "timeout_seconds": _llm_timeout_seconds_for_trace(),
    }


def _tool_call_trace_payload(tool_call: dict) -> dict:
    args = tool_call.get("args") if isinstance(tool_call, dict) else None
    return {
        "id": str(tool_call.get("id") or "") if isinstance(tool_call, dict) else "",
        "name": str(tool_call.get("name") or "") if isinstance(tool_call, dict) else "",
        "args_summary": safe_trace_value(args or {}, max_chars=500),
    }


def _llm_timeout_seconds_for_trace() -> float:
    cb = settings.circuit_breaker_config
    return max(1.0, cb.retry_backoff_base * (2**cb.retry_max) * 2)


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
    "_record_final_llm_context_trace",
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
