"""Agent Runtime 节点实现。"""

import asyncio
import logging
import re
import time as _time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END

from app.agent.llm import get_llm
from app.agent.prompt_cache import get_prompt_cache
from app.agent.prompt_composer import get_composer
from app.agent.runtime.llm_support import (
    _LLM_SEMAPHORE,
    _build_circuit_key,
    _get_farm_context,
    _get_runtime_context_bundle,
    _get_season,
    _get_classifier as _runtime_get_classifier,
    _record_llm_failure,
    _record_llm_success,
    _warm_tool_caches,
)
from app.agent.runtime.final_prompt_budget import FinalPromptBudget
from app.agent.runtime.direct_routing import (
    can_direct_route,
    can_return_direct_tool_messages,
    can_skip_llm_tool_selection,
    direct_query_tool_args,
    direct_query_tool_names,
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
from app.agent.runtime.tool_executor import _parallel_tool_node
from app.agent.router import RouterDecision, SkillRouter
from app.agent.skills import get_langchain_tools
from app.agent.state import AgentState
from app.agent.tool_selector import expand_by_chain as _expand_by_chain
from app.agent.tool_selector import select_tools as _select_tools
from app.core.config import settings
from app.core.date_context import get_request_date
from app.context.models import ContextBundle
from app.infra.pending_actions import PENDING_MARKER, is_pending_tool_message
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
    return _runtime_get_classifier()


def _route_tools(user_msg: str, tools: list) -> RouterDecision:
    """使用 SkillRouter，兼容测试/旧入口 patch select_tools 的场景。"""
    if select_tools is not _select_tools:
        return RouterDecision(selected_tools=list(select_tools(user_msg, tools)))
    return SkillRouter().route(user_msg, tools)


async def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点 — 使用模板渲染 system prompt，带上下文压缩。"""
    messages = state["messages"]

    tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
    pending_msgs = [m for m in tool_msgs if is_pending_tool_message(m)]
    normal_msgs = [m for m in tool_msgs if not is_pending_tool_message(m)]

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
        return {"messages": [AIMessage(content=combined)]}

    if pending_msgs:
        confirm = pending_msgs[-1].content.replace(PENDING_MARKER, "").strip()
        logger.info("检测到 pending ToolMessage，跳过 LLM 直接确认 | text=%s", confirm)
        return {"messages": [AIMessage(content=confirm)]}

    if normal_msgs and can_return_direct_tool_messages(normal_msgs):
        content = "\n\n".join(str(msg.content or "") for msg in normal_msgs).strip()
        logger.info(
            "检测到确定性直达 ToolMessage，跳过 LLM 直接返回 | count=%d",
            len(normal_msgs),
        )
        return {"messages": [AIMessage(content=content)]}

    prepared_system_prompt = state.get("system_prompt")
    prepared_context_bundle = state.get("context_bundle")
    prepared_selected_tool_names = state.get("selected_tool_names")
    prepared_router_decision = state.get("router_decision")

    farm_id = state.get("farm_id", 1)
    if not isinstance(farm_id, int) or farm_id <= 0:
        return {"messages": [AIMessage(content="缺少可信农场上下文，无法继续处理。")]}
    farm_uid = state.get("farm_uid")

    quota = check_quota(state.get("user_id"))
    quota_allowed = quota if isinstance(quota, bool) else quota.allowed
    exceeded_period = None if isinstance(quota, bool) else quota.exceeded_period
    if not quota_allowed:
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

    tools = get_langchain_tools(farm_id=farm_id, farm_uid=farm_uid)
    has_tool_results = bool(tool_msgs)
    intent = state.get("intent", "agent")
    user_msg = _find_last_human_message(messages)
    if prepared_router_decision is not None:
        router_decision = prepared_router_decision
    elif normal_msgs:
        router_decision = RouterDecision(
            selected_tools=[],
            fallback="final_answer_no_tools",
            reason="已有工具结果，final answer 默认不重新绑定工具",
        )
    else:
        router_decision = _route_tools(user_msg, tools)

    increment_round()
    collector = get_collector()
    collector.record(
        node_type="skill_router",
        node_name="skill_router",
        input_data={"message": user_msg[:500]},
        output_data=router_decision.to_trace_payload(),
        token_usage={
            "schema_token_estimate": router_decision.schema_token_estimate,
            "usage_source": "router_estimate",
        },
    )

    selected_names = list(router_decision.selected_tools)
    if _is_operation_work_order_clarification(messages):
        selected_names = _append_tool_name_once(
            selected_names,
            "create_operation_work_order",
            tools,
        )
    if prepared_selected_tool_names is not None:
        selected_names = list(prepared_selected_tool_names)
    direct_names = direct_query_tool_names(user_msg, selected_names)
    if (
        intent == "query"
        and not has_tool_results
        and direct_names
        and can_skip_llm_tool_selection(
            user_msg=user_msg,
            tools=tools,
            selected_names=selected_names,
            direct_names=direct_names,
        )
        and can_direct_route(user_msg, selected_names, direct_names)
    ):
        tool_calls = [
            {
                "name": name,
                "args": direct_query_tool_args(user_msg, name),
                "id": f"direct_{name}",
                "type": "tool_call",
            }
            for name in direct_names
        ]
        logger.info(
            "确定性工具直达 | input=%r | tool_calls=%s | skipped_llm=true",
            user_msg[:80],
            direct_names,
        )
        return {"messages": [AIMessage(content="", tool_calls=tool_calls)]}

    model_role = "lightweight" if intent == "query" else "generation"
    raw_llm = get_llm(role=model_role)
    logger.info("模型路由 | intent=%s | role=%s", intent, model_role)
    _circuit_key = _build_circuit_key(raw_llm)
    selected_tools = [t for t in tools if t.name in selected_names]
    if selected_tools:
        parallel = (
            {"parallel_tool_calls": True} if settings.ai.parallel_tool_calls else {}
        )
        llm = raw_llm.bind_tools(selected_tools, **parallel)
    else:
        llm = raw_llm
        logger.info("无匹配工具，LLM 直接回复（闲聊模式）")

    selected_tool_names = [t.name for t in selected_tools] if selected_tools else []
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
            user_id=state.get("user_id"),
            session_id=state.get("session_id"),
        )
    if not context_bundle.blocks and farm_ctx.get("display_name") == "农友":
        farm_ctx = await _get_farm_context(farm_id)
    display_name = farm_ctx["display_name"]
    farm_location = farm_ctx["farm_location"]

    if prepared_system_prompt:
        system_text = prepared_system_prompt
    else:
        current_date = get_request_date()
        date_str = str(current_date)
        prompt_cache = get_prompt_cache()
        cached_prompt = prompt_cache.get(farm_id=farm_id, date_str=date_str)
        if cached_prompt is not None:
            system_text = cached_prompt
        else:
            current_season = _get_season(current_date)
            system_text = get_composer().compose(
                "system_base",
                variables={
                    "display_name": display_name,
                    "farm_location": farm_location,
                    "farm_coords": farm_ctx["farm_coords"],
                    "current_season": current_season,
                    "active_crops": farm_ctx["active_crops"],
                },
                current_date=current_date,
            )
            prompt_cache.set(farm_id=farm_id, date_str=date_str, value=system_text)

    runtime_context_text = context_bundle.render_text()
    if runtime_context_text:
        system_text = (
            f"{system_text}\n\n<runtime_context>\n"
            f"{runtime_context_text}\n"
            f"</runtime_context>"
        )

    # 记录 prompt_render trace
    collector.record(
        node_type="prompt_render",
        node_name="system_prompt",
        input_data={
            "template": "system_base",
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

    # 并行缓存预热（与 LLM 调用并行执行）
    preload_task = asyncio.create_task(
        _warm_tool_caches(
            selected_tool_names,
            farm_id,
            farm_ctx,
            context_dependencies=router_decision.context_dependencies,
        )
    )

    # LLM 调用 + 计时 + 请求内重试
    start = _time.perf_counter()
    max_retries = settings.ai.failover_max_retries
    response = None

    async with _LLM_SEMAPHORE:
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    raw_llm = get_llm(role=model_role)
                    _circuit_key = _build_circuit_key(raw_llm)
                    if selected_tools:
                        parallel = (
                            {"parallel_tool_calls": True}
                            if settings.ai.parallel_tool_calls
                            else {}
                        )
                        llm = raw_llm.bind_tools(selected_tools, **parallel)
                    else:
                        llm = raw_llm
                response = await llm.ainvoke([system] + messages)
                _record_llm_success(_circuit_key)
                break
            except Exception as exc:
                duration_ms = int((_time.perf_counter() - start) * 1000)
                model_name = getattr(raw_llm, "model_name", "unknown")
                _record_llm_failure(_circuit_key, exc)

                # 非可恢复错误（400 schema 错误等）不重试，直接抛出
                from app.core.llm_client_manager import classify_error, ErrorLevel

                error_level = classify_error(exc)
                if error_level == ErrorLevel.MODEL:
                    logger.warning(
                        "LLM 不可恢复错误，跳过重试 | key=%s | model=%s | level=%s",
                        _circuit_key,
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
                    _circuit_key,
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

    # 等待预热完成（不阻塞，已并行运行）
    try:
        await asyncio.wait_for(preload_task, timeout=0.1)
    except (asyncio.TimeoutError, Exception):
        pass

    # 兼容层：部分 provider（如 nvidia llama-3.1）不支持 bind_tools，
    # LLM 会把工具调用 JSON 直接写进 content 而不是通过 tool_calls API。
    # 这里检测并手动解析，确保 graph 能正确路由到 tools 节点。
    if not response.tool_calls:
        parsed_tool_calls = _extract_tool_calls_from_content(response.content or "")
        if parsed_tool_calls:
            filtered_tool_calls = filter_tool_calls_by_selected(
                parsed_tool_calls,
                selected_tools,
            )
            if filtered_tool_calls:
                logger.info(
                    "LLM content 中检测到工具调用 JSON，手动构造 tool_calls | tools=%s | model=%s",
                    [tc["name"] for tc in filtered_tool_calls],
                    model_name,
                )
                # 重建 AIMessage，保留原 metadata，注入 tool_calls
                response = AIMessage(
                    content="",
                    tool_calls=filtered_tool_calls,
                    response_metadata=response.response_metadata,
                    id=response.id,
                )

    # 检测"应该调用工具但未调用"的情况：写意图空回复也必须 fail closed。
    if not response.tool_calls:
        should_retry, missed_tools = _detect_missed_tool_call(
            user_msg, response.content or "", selected_tools
        )
        if should_retry and selected_tools:
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
                    retry_calls,
                    selected_tools,
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
                    response = AIMessage(
                        content="",
                        tool_calls=filtered_retry_calls,
                        response_metadata=retry_response.response_metadata,
                        id=retry_response.id,
                    )
                else:
                    from app.infra.pending_actions import is_write_skill

                    if any(is_write_skill(tool.name) for tool in missed_tools):
                        logger.warning("写操作重试后仍未输出工具调用，使用安全兜底回复")
                        response = AIMessage(
                            content=(
                                "这条操作还没有执行。"
                                "系统没有生成可确认的待执行动作。"
                                "请重新描述要新增、修改或结算的对象和关键参数，"
                                "我会先生成待确认操作，确认后再执行。"
                            ),
                            response_metadata=retry_response.response_metadata,
                            id=retry_response.id,
                        )
                    else:
                        logger.warning("重试后 LLM 仍未输出工具调用，使用原回复")
            except Exception as retry_exc:
                logger.warning("重试调用失败 | error=%s", retry_exc)

    # 提取真实 provider token usage，缺失时不参与 TokenDailyStats 入账。
    token_usage = extract_token_usage(response)
    tokens = (
        token_usage["total_tokens"] if token_usage else _extract_tokens_used(response)
    )

    logger.info(
        "LLM 调用完成 | role=%s | key=%s | model=%s | latency_ms=%d | "
        "selected_tools=%d | tool_calls=%d | tokens=%s",
        model_role,
        _circuit_key,
        model_name,
        duration_ms,
        len(selected_tools),
        len(response.tool_calls or []),
        tokens if tokens is not None else "-",
    )

    # LLM 工具选择日志
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

    return {"messages": [response], "router_decision": router_decision}


__all__ = [
    "_llm_node",
    "_parallel_tool_node",
    "_should_continue",
]
