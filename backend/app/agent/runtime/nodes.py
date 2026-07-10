"""Agent Runtime 节点实现。"""

import asyncio
import logging
import re
import time as _time
from dataclasses import replace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END

from app.agent.llm import get_llm
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
    _resolve_tool_choice,
    _warm_tool_caches,
)
from app.agent.runtime.chat_fallbacks import (
    SYSTEM_BASE_SCENE,
    retry_no_tool_json_leak,
    select_system_prompt_scene,
)
from app.agent.runtime.final_prompt_budget import FinalPromptBudget
from app.agent.runtime.direct_routing import (
    can_return_direct_tool_messages,
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
from app.agent.runtime.quota import QUOTA_REJECT_MESSAGES, check_quota
from app.agent.runtime.reflection import apply_post_tool_reflection
from app.agent.runtime.tool_executor import _parallel_tool_node
from app.agent.planning import (
    DomainValidator,
    attach_validation,
    plan_draft_from_router_decision,
)
from app.agent.router import RouterDecision, SkillRouter
from app.agent.router.catalog import SkillCatalog
from app.agent.skills import get_langchain_tools
from app.agent.state import AgentState
from app.agent.tool_selector import expand_by_chain as _expand_by_chain
from app.agent.tool_selector import select_tools as _select_tools
from app.agent.tool_selector import ToolSelectionResult
from app.core.config import settings
from app.core.date_context import get_request_date
from app.context.models import ContextBundle
from app.infra.pending_actions import PENDING_MARKER, is_pending_tool_message
from app.infra.trace_collector import get_collector
from app.infra.trace_context import increment_round, set_round_index

logger = logging.getLogger(__name__)
expand_by_chain = _expand_by_chain
select_tools = _select_tools

_WORK_ORDER_CLARIFICATION_RE = re.compile(
    r"(?:创建|生成|安排|记录).{0,12}(?:农事)?作业单|创建农事作业单"
)


def _build_data_source_payload(tool_calls: list[dict] | None) -> dict:
    """构造 final_reply_data_source trace payload。

    判定 data_source：
    - 有 tool_calls → tool:<最后一个 tool 的 name>
    - 无 tool_calls → context_bundle（回复来自 ContextBundle 或 LLM 自身知识）
    """
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
    """记录 tool_call_forced trace（LLM bind_tools 前）。失败静默。

    `force_binding` 来自 _route_tools 派生的 RouterDecision（基于真实工具列表计算），
    不在此处重新计算，避免传入空工具导致 force_binding 永远为空。
    """
    try:
        forced = set(force_binding) & set(selected_names)
        _now = _time.time()
        collector.record(
            node_type="tool_selection",
            node_name="tool_call_forced",
            input_data={"user_message": user_msg[:200] if user_msg else ""},
            output_data={
                "forced_skills": sorted(forced),
                "tool_choice": tool_choice,
                "selected_tools": list(selected_names),
            },
            start_time=_now,
            duration_ms=0,
        )
    except Exception:
        return


def _record_final_reply_data_source_trace(
    *,
    collector,
    messages: list,
) -> None:
    """记录 final_reply_data_source trace。失败静默。"""
    try:
        last_tool_messages_for_trace = _tool_messages_for_data_source(messages)
        _now = _time.time()
        collector.record(
            node_type="response",
            node_name="final_reply_data_source",
            input_data={"has_tool_results": bool(last_tool_messages_for_trace)},
            output_data=_build_data_source_payload(last_tool_messages_for_trace),
            start_time=_now,
            duration_ms=0,
        )
    except Exception:
        return


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


def _enabled_read_tool_names(tools: list) -> list[str]:
    """返回可交给主模型选择的只读工具名。"""
    return [
        candidate.name
        for candidate in SkillCatalog.from_tools(tools).enabled()
        if candidate.risk == "read"
    ]


def _is_model_choice_read_decision(decision: RouterDecision) -> bool:
    """判断是否为可交给主模型自行选工具的普通读决策。"""
    if not decision.frames:
        return False
    return all(
        frame.risk == "read" and not frame.requires_confirmation
        for frame in decision.frames
    )


def _get_classifier():
    """兼容旧 graph 入口导出的 classifier 工厂。"""
    return None


def _route_tools(user_msg: str, tools: list) -> RouterDecision:
    """使用 SkillRouter，兼容测试/旧入口 patch select_tools 的场景。"""
    if select_tools is not _select_tools:
        # 旧入口/测试可能 patch select_tools 返回 list（无 force_binding）
        selection = select_tools(user_msg, tools)
        if isinstance(selection, ToolSelectionResult):
            return RouterDecision(
                selected_tools=list(selection.tools),
                tool_choice=_resolve_tool_choice(selection),
                force_binding=tuple(sorted(selection.force_binding)),
            )
        return RouterDecision(selected_tools=list(selection))
    decision = SkillRouter().route(user_msg, tools)
    selected_tools = list(decision.selected_tools)
    if _is_model_choice_read_decision(decision):
        selected_tools = _enabled_read_tool_names(tools)
    return replace(
        decision,
        selected_tools=selected_tools,
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
        summaries = []
        for m in normal_msgs:
            content = str(m.content or "")
            if content:
                summaries.append(content[:200])
        confirm_parts = []
        for m in pending_msgs:
            confirm = m.content.replace(PENDING_MARKER, "").strip()
            confirm_parts.append(confirm)
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
        confirm = pending_msgs[-1].content.replace(PENDING_MARKER, "").strip()
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


def _resolve_router_decision(
    *,
    prepared_router_decision,
    normal_msgs: list[ToolMessage],
    user_msg: str,
    tools: list,
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
    return _route_tools(user_msg, tools)


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
) -> list[str]:
    """汇总最终可绑定工具名。"""
    selected_names = list(router_decision.selected_tools)
    if _is_operation_work_order_clarification(messages):
        selected_names = _append_tool_name_once(
            selected_names,
            "create_operation_work_order",
            tools,
        )
    if prepared_selected_tool_names is not None:
        selected_names = list(prepared_selected_tool_names)
    if has_tool_results:
        selected_names = []
    return selected_names


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


def _append_runtime_context(system_text: str, context_bundle: ContextBundle) -> str:
    runtime_context_text = context_bundle.render_text()
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
    messages = sliding_window_compact(state["messages"])
    messages, final_budget = FinalPromptBudget().apply(system_text, messages)
    input_summary = _find_last_human_message(state["messages"])[:200]
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


def _record_llm_response(
    *,
    response: AIMessage,
    collector,
    model_role: str,
    circuit_key: str,
    model_name: str,
    duration_ms: int,
    selected_tools: list,
    selected_tool_names: list[str],
    normal_msgs: list[ToolMessage],
    farm_id: int,
    session_id: str | None,
    intent: str,
    user_msg: str,
    plan_draft_payload: dict,
    input_summary: str,
) -> tuple[AIMessage, dict | None]:
    """整理最终响应、记录 LLM trace，并返回 token usage。"""
    token_usage = extract_token_usage(response)
    tokens = (
        token_usage["total_tokens"] if token_usage else _extract_tokens_used(response)
    )

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

    if response.tool_calls:
        tool_names = [tc["name"] for tc in response.tool_calls]
        logger.info("LLM 工具选择 | tool_calls=%s | model=%s", tool_names, model_name)
        output_summary = f"tool_calls: {tool_names}"
    else:
        content = response.content or ""
        if not str(content).strip():
            content = "这次没有生成有效回复，请换个说法再试一次。"
            response = AIMessage(
                content=content,
                response_metadata=response.response_metadata,
                id=response.id,
            )
            logger.warning(
                "LLM 返回空内容，已使用兜底回复 | model=%s | selected_tools=%s",
                model_name,
                selected_tool_names,
            )
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
        output_summary = content[:200]

    collector.record(
        node_type="llm_call",
        node_name=model_name,
        input_data=input_summary,
        output_data=output_summary,
        duration_ms=duration_ms,
        token_usage=token_usage,
    )
    return response, token_usage


async def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点 — 使用模板渲染 system prompt，带上下文压缩。"""
    messages = state["messages"]

    tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
    pending_msgs = [m for m in tool_msgs if is_pending_tool_message(m)]
    normal_msgs = [m for m in tool_msgs if not is_pending_tool_message(m)]

    direct_tool_response = _direct_tool_message_response(
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
    router_decision = _resolve_router_decision(
        prepared_router_decision=prepared_router_decision,
        normal_msgs=normal_msgs,
        user_msg=user_msg,
        tools=tools,
    )

    trace_round_index = increment_round()
    collector = get_collector()
    session_id = state.get("session_id")
    plan_draft_payload = _existing_plan_draft_payload(state)
    should_record_router_trace = not has_tool_results
    if plan_draft_payload is None or should_record_router_trace:
        plan_draft_payload = _record_router_plan_trace(
            collector=collector,
            router_decision=router_decision,
            user_msg=user_msg,
            farm_id=farm_id,
            session_id=session_id,
        )

    selected_names = _resolve_selected_names(
        router_decision=router_decision,
        messages=messages,
        tools=tools,
        prepared_selected_tool_names=prepared_selected_tool_names,
        has_tool_results=has_tool_results,
    )

    model_role = "lightweight" if intent == "query" else "generation"
    raw_llm = get_llm(role=model_role)
    logger.info("模型路由 | intent=%s | role=%s", intent, model_role)
    selected_tools = [t for t in tools if t.name in selected_names]
    tool_choice = router_decision.tool_choice
    if should_record_router_trace:
        _record_tool_call_forced_trace(
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
    system_text = _append_runtime_context(system_text, context_bundle)

    system, messages, input_summary = _record_prompt_budget(
        collector=collector,
        system_text=system_text,
        prompt_scene=prompt_scene,
        context_bundle=context_bundle,
        state=state,
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
    response, _token_usage = _record_llm_response(
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
    )

    _record_final_reply_data_source_trace(
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
