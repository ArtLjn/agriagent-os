"""Agent Runtime 节点实现。"""

import asyncio
import logging
import time as _time

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END

from app.agent.llm import get_llm
from app.agent.prompt_cache import get_prompt_cache
from app.agent.prompt_composer import get_composer
from app.agent.runtime.llm_support import (
    _LLM_SEMAPHORE,
    _build_circuit_key,
    _get_classifier,
    _get_farm_context,
    _get_season,
    _record_llm_failure,
    _record_llm_success,
    _warm_tool_caches,
)
from app.agent.runtime.messages import (
    _detect_missed_tool_call,
    _extract_tokens_used,
    _extract_tool_calls_from_content,
    _find_last_human_message,
    sliding_window_compact,
)
from app.agent.runtime.tool_executor import _parallel_tool_node
from app.agent.skills import get_langchain_tools
from app.agent.state import AgentState
from app.agent.tool_selector import expand_by_chain, select_tools
from app.core.config import settings
from app.core.date_context import get_request_date
from app.infra.pending_actions import PENDING_MARKER, is_pending_tool_message
from app.infra.trace_collector import get_collector
from app.infra.trace_context import increment_round
from app.services.quota_service import check_quota

logger = logging.getLogger(__name__)


def _should_continue(state: AgentState) -> str:
    """判断是否需要继续调用工具。"""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


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

    farm_id = state.get("farm_id", 1)

    # 获取农场上下文（位置、坐标、称呼、种植信息）
    farm_ctx = await _get_farm_context(farm_id)
    display_name = farm_ctx["display_name"]
    farm_location = farm_ctx["farm_location"]

    tools = get_langchain_tools(farm_id=farm_id)
    has_tool_results = bool(tool_msgs)

    intent = state.get("intent", "agent")
    model_role = "lightweight" if intent == "query" else "generation"
    raw_llm = get_llm(role=model_role)
    logger.info("模型路由 | intent=%s | role=%s", intent, model_role)
    _circuit_key = _build_circuit_key(raw_llm)
    user_msg = _find_last_human_message(messages)
    selected_names = select_tools(
        user_msg,
        tools,
        intent_classifier=_get_classifier(),
        # user_location=farm_location,
    )
    if has_tool_results:
        selected_names_set = expand_by_chain(set(selected_names))
        selected_tools = [t for t in tools if t.name in selected_names_set]
    else:
        selected_tools = [t for t in tools if t.name in selected_names]
    if selected_tools:
        parallel = (
            {"parallel_tool_calls": True} if settings.ai.parallel_tool_calls else {}
        )
        llm = raw_llm.bind_tools(selected_tools, **parallel)
    else:
        llm = raw_llm
        logger.info("无匹配工具，LLM 直接回复（闲聊模式）")
    _round_idx = increment_round()
    collector = get_collector()

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

    # 记录 prompt_render trace
    collector.record(
        node_type="prompt_render",
        node_name="system_prompt",
        input_data={"template": "system_base", "variables_count": 2},
        output_data=system_text[:2000],
    )

    system = SystemMessage(content=system_text)
    messages = sliding_window_compact(state["messages"])
    input_summary = _find_last_human_message(state["messages"])[:200]

    # Token 配额检查
    if not check_quota(farm_id=farm_id):
        action = settings.token_quota.over_quota_action
        if action == "reject":
            logger.warning("Token 配额超限，拒绝调用（reject 模式）")
            return {"messages": [AIMessage(content="今日用量已达上限，明天再来吧。")]}
        elif action == "warn":
            logger.warning("Token 配额超限，继续调用（warn 模式）")

    # 并行缓存预热（与 LLM 调用并行执行）
    selected_names_for_preload = (
        [t.name for t in selected_tools] if selected_tools else []
    )
    preload_task = asyncio.create_task(
        _warm_tool_caches(selected_names_for_preload, farm_id, farm_ctx)
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
            logger.info(
                "LLM content 中检测到工具调用 JSON，手动构造 tool_calls | tools=%s | model=%s",
                [tc["name"] for tc in parsed_tool_calls],
                model_name,
            )
            # 重建 AIMessage，保留原 metadata，注入 tool_calls
            response = AIMessage(
                content="",
                tool_calls=parsed_tool_calls,
                response_metadata=response.response_metadata,
                id=response.id,
            )

    # 检测"应该调用工具但未调用"的情况：用户消息匹配工具关键词，但 LLM 返回了纯文本
    if not response.tool_calls and response.content:
        should_retry, _ = _detect_missed_tool_call(
            user_msg, response.content, selected_tools
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
                retry_parsed = _extract_tool_calls_from_content(
                    retry_response.content or ""
                )
                if retry_parsed:
                    logger.info(
                        "重试成功，LLM 输出了工具调用 | tools=%s",
                        [tc["name"] for tc in retry_parsed],
                    )
                    response = AIMessage(
                        content="",
                        tool_calls=retry_parsed,
                        response_metadata=retry_response.response_metadata,
                        id=retry_response.id,
                    )
                else:
                    logger.warning("重试后 LLM 仍未输出工具调用，使用原回复")
            except Exception as retry_exc:
                logger.warning("重试调用失败 | error=%s", retry_exc)

    # 提取 token 用量
    tokens = _extract_tokens_used(response)
    token_usage = None
    if tokens is not None:
        usage_meta = response.response_metadata.get("token_usage", {})
        token_usage = {
            "prompt_tokens": usage_meta.get("prompt_tokens", 0),
            "completion_tokens": usage_meta.get("completion_tokens", 0),
            "total_tokens": tokens,
        }

    # LLM 工具选择日志
    if response.tool_calls:
        tool_names = [tc["name"] for tc in response.tool_calls]
        logger.info("LLM 工具选择 | tool_calls=%s | model=%s", tool_names, model_name)
        output_summary = f"tool_calls: {tool_names}"
    else:
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

    return {"messages": [response]}


__all__ = [
    "_llm_node",
    "_parallel_tool_node",
    "_should_continue",
]
