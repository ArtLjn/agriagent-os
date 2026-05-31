"""LangGraph 图编译模块 — 自定义 StateGraph 实现并行 Skill 执行。"""

import asyncio
import logging
import threading
from datetime import date
from typing import Annotated

import time as _time

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.agent.llm import get_llm
from app.infra.pending_actions import (
    PENDING_MARKER,
    is_write_skill,
    is_pending_tool_message,
    build_confirm_message,
    store_pending,
)
from app.agent.prompt_composer import get_composer
from app.core.date_context import get_request_date
from app.core.database import SessionLocal
from app.core.config import settings
from app.infra.trace_collector import get_collector
from app.infra.trace_context import increment_round
from app.models.farm import Farm
from app.models.user import User
from app.models.user_setting import UserSetting
from app.services.quota_service import check_quota
from app.agent.skills import get_langchain_tools
from app.agent.tool_selector import expand_by_chain, select_tools, LLMIntentClassifier

logger = logging.getLogger(__name__)

_LLM_SEMAPHORE = asyncio.Semaphore(5)

_classifier: LLMIntentClassifier | None = None
_classifier_lock = threading.Lock()


def _get_classifier() -> LLMIntentClassifier | None:
    global _classifier
    if _classifier is not None:
        return _classifier

    api_key = settings.ai_api_key
    base_url = settings.ai_base_url
    model = settings.ai_model

    # 优先从 Manager 获取
    try:
        from app.core.llm_client_manager import get_llm_manager

        manager = get_llm_manager()
        if not manager.fallback_mode:
            info = manager.get_model_info()
            client = manager.get_sync_client()
            api_key = client.api_key
            base_url = client.base_url
            model = info["model"]
    except Exception as e:
        logger.debug("从 Manager 获取 classifier 参数失败 | error=%s", e)

    if api_key:
        with _classifier_lock:
            if _classifier is None:
                _classifier = LLMIntentClassifier(
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                )
    return _classifier


def _get_season(current_date: date | None = None) -> str:
    """根据当前月份返回季节。"""
    if current_date is None:
        current_date = date.today()
    month = current_date.month
    if month in (3, 4, 5):
        return "春季"
    elif month in (6, 7, 8):
        return "夏季"
    elif month in (9, 10, 11):
        return "秋季"
    else:
        return "冬季"


def sliding_window_compact(
    messages: list, keep_rounds: int = 5
) -> list:
    """Sliding window 消息压缩：最近 N 轮完整保留，旧 ToolMessage 截断。

    一轮 = 从 HumanMessage 到下一个 HumanMessage 之前的所有消息。
    """
    if not messages:
        return messages

    round_starts = []
    for i, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            round_starts.append(i)

    if len(round_starts) <= keep_rounds:
        return messages

    compress_up_to = round_starts[-keep_rounds]

    result = list(messages)
    for i, msg in enumerate(result):
        if i >= compress_up_to:
            break
        if isinstance(msg, ToolMessage):
            content = msg.content or ""
            if len(content) > 50:
                tool_name = getattr(msg, "name", "unknown")
                result[i] = ToolMessage(
                    content=f"[已执行 {tool_name}]",
                    tool_call_id=msg.tool_call_id,
                )

    return result


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    farm_id: int


def _should_continue(state: AgentState) -> str:
    """判断是否需要继续调用工具。"""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def _find_last_human_message(messages: list) -> str:
    """从消息列表中找到最后一条 HumanMessage 的内容。"""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content or ""
    return ""


def _extract_tokens_used(response: AIMessage) -> int | None:
    """从 LLM 响应中提取 token 用量。"""
    try:
        usage = response.response_metadata.get("token_usage", {})
        total = usage.get("total_tokens")
        if total is not None:
            return int(total)
    except (AttributeError, TypeError, ValueError):
        pass
    return None


def _build_circuit_key(llm_instance) -> str:
    """从 LLM 实例构建 cooldown key（provider_name/model_id）。"""
    model_id = getattr(llm_instance, "model_name", "") or getattr(llm_instance, "model", "")
    base_url = ""
    try:
        base_url = getattr(llm_instance, "base_url", "") or llm_instance.openai_api_base
    except Exception:
        pass

    # 从 Manager chain 中匹配 provider name
    try:
        from app.core.llm_client_manager import get_llm_manager
        manager = get_llm_manager()
        if not manager.fallback_mode:
            for provider, model in manager.chain:
                if model.id == model_id and base_url and provider.base_url in base_url:
                    return f"{provider.name}/{model.id}"
    except Exception:
        pass
    return model_id or "unknown"


def _record_llm_failure(circuit_key: str, exc: Exception) -> None:
    """LLM 调用失败，记录到 Manager cooldown。"""
    try:
        from app.core.llm_client_manager import get_llm_manager, classify_error
        manager = get_llm_manager()
        if not manager.fallback_mode:
            manager.record_failure(circuit_key)
            level = classify_error(exc)
            logger.warning(
                "LLM 故障记录 | key=%s | level=%s | error=%s",
                circuit_key, level.value, str(exc)[:120],
            )
    except Exception as e:
        logger.debug("记录 LLM 故障失败 | error=%s", e)


def _record_llm_success(circuit_key: str) -> None:
    """LLM 调用成功，清除 cooldown。"""
    try:
        from app.core.llm_client_manager import get_llm_manager
        manager = get_llm_manager()
        if not manager.fallback_mode:
            manager.record_success(circuit_key)
    except Exception:
        pass


async def _get_farm_context(farm_id: int) -> tuple[str, str]:
    """异步获取农场位置和用户称呼，避免阻塞事件循环。"""

    def _query() -> tuple[str, str]:
        db = SessionLocal()
        try:
            farm = db.query(Farm).filter(Farm.id == farm_id).first()
            display_name = "农友"
            user_city = ""
            if farm and farm.user_id:
                user = db.query(User).filter(User.id == farm.user_id).first()
                if user:
                    display_name = user.nickname
                user_setting = (
                    db.query(UserSetting)
                    .filter(UserSetting.user_id == farm.user_id)
                    .first()
                )
                if user_setting and user_setting.default_city:
                    user_city = user_setting.default_city
            farm_location = user_city or (farm.location if farm and farm.location else "")
            return farm_location, display_name
        except Exception:
            logger.warning("获取用户信息失败，使用默认值", exc_info=True)
            return "", "农友"
        finally:
            db.close()

    return await asyncio.to_thread(_query)


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

    # 获取用户称呼和农场位置（提前到 select_tools 之前，用于地名检测）
    farm_location = await _get_farm_context(farm_id)
    display_name = farm_location[1]
    farm_location = farm_location[0]

    tools = get_langchain_tools()
    raw_llm = get_llm()
    # 获取当前 provider/model 的 cooldown key
    _circuit_key = _build_circuit_key(raw_llm)
    user_msg = _find_last_human_message(messages)
    selected_names = select_tools(
        user_msg, tools, intent_classifier=_get_classifier(),
        user_location=farm_location,
    )
    has_tool_results = bool(tool_msgs)
    if has_tool_results:
        selected_names_set = expand_by_chain(set(selected_names))
        selected_tools = [t for t in tools if t.name in selected_names_set]
    else:
        selected_tools = [t for t in tools if t.name in selected_names]
    if selected_tools:
        parallel = {"parallel_tool_calls": True} if settings.ai.parallel_tool_calls else {}
        llm = raw_llm.bind_tools(selected_tools, **parallel)
    else:
        llm = raw_llm
        logger.info("无匹配工具，LLM 直接回复（闲聊模式）")
    model_name = getattr(raw_llm, "model_name", "unknown")
    _round_idx = increment_round()
    collector = get_collector()

    current_date = get_request_date()
    current_season = _get_season(current_date)
    system_text = get_composer().compose(
        "system_base",
        variables={
            "display_name": display_name,
            "farm_location": farm_location,
            "current_season": current_season,
        },
        current_date=current_date,
    )

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

    # LLM 调用 + 计时
    start = _time.perf_counter()
    async with _LLM_SEMAPHORE:
        try:
            response = await llm.ainvoke([system] + messages)
        except Exception as exc:
            duration_ms = int((_time.perf_counter() - start) * 1000)
            collector.record(
                node_type="llm_call",
                node_name=model_name,
                input_data=input_summary,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
            _record_llm_failure(_circuit_key, exc)
            raise

    duration_ms = int((_time.perf_counter() - start) * 1000)
    _record_llm_success(_circuit_key)

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


async def _parallel_tool_node(state: AgentState) -> dict:
    """并行执行多个 tool_calls 的节点。写操作 Skill 拦截为 pending action。"""
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": []}

    tool_map = {t.name: t for t in get_langchain_tools()}
    farm_id = state.get("farm_id", 1)
    collector = get_collector()

    async def _call_one(tc: dict) -> ToolMessage:
        name = tc["name"]
        args = tc["args"]
        tool_call_id = tc["id"]
        logger.info("Skill 调用 %s(%s)", name, args)
        start = _time.perf_counter()

        # 写操作 Skill 拦截：存储 pending action，不直接执行
        if is_write_skill(name):
            action_id = store_pending(farm_id, name, args)
            logger.info(
                "写操作 Skill 已拦截 | farm=%s action_id=%s skill=%s",
                farm_id,
                action_id,
                name,
            )
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                output_data="已拦截为 pending action",
                duration_ms=0,
            )
            confirm_text = build_confirm_message(name, args)
            return ToolMessage(
                content=f"{PENDING_MARKER} {confirm_text}",
                tool_call_id=tool_call_id,
            )

        try:
            tool = tool_map.get(name)
            if not tool:
                return ToolMessage(
                    content=f"未知工具: {name}", tool_call_id=tool_call_id
                )
            result = await tool.ainvoke(args)
            duration_ms = int((_time.perf_counter() - start) * 1000)
            summary = str(result)[:120].replace("\n", " ")
            logger.info(
                "Skill 完成 | name=%s | duration_ms=%d | result=%s",
                name,
                duration_ms,
                summary,
            )
            # 提取结构化 trace 数据（来自 _SkillResultWrapper）
            trace_output = getattr(result, "trace_data", None)
            if not trace_output:
                trace_output = {
                    "status": "success",
                    "reply_preview": str(result)[:500],
                }
            else:
                trace_output["reply_preview"] = str(result)[:500]
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                output_data=trace_output,
                duration_ms=duration_ms,
            )
            return ToolMessage(content=str(result), tool_call_id=tool_call_id)
        except Exception as e:
            duration_ms = int((_time.perf_counter() - start) * 1000)
            logger.error(
                "Skill 失败 | name=%s | error=%s",
                name,
                e,
            )
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                duration_ms=duration_ms,
                error_message=str(e),
            )
            return ToolMessage(content=f"工具调用失败: {e}", tool_call_id=tool_call_id)

    if len(last.tool_calls) == 1:
        results = [await _call_one(last.tool_calls[0])]
    else:
        logger.info("并行执行 %d 个 Skill", len(last.tool_calls))
        batch_start = _time.perf_counter()
        results = await asyncio.gather(*[_call_one(tc) for tc in last.tool_calls])
        batch_duration = int((_time.perf_counter() - batch_start) * 1000)
        collector.record(
            node_type="parallel_batch",
            node_name=f"parallel_{len(results)}_skills",
            output_data={
                "parallel_count": len(results),
                "skills": [{"name": tc["name"]} for tc in last.tool_calls],
            },
            duration_ms=batch_duration,
        )

    return {"messages": results}


def compile_advisor_graph():
    """编译建议 Agent 的 StateGraph（支持并行 Skill 执行，最大 15 步）。"""
    graph = StateGraph(AgentState)
    graph.add_node("llm", _llm_node)
    graph.add_node("tools", _parallel_tool_node)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")
    return graph.compile()


__all__ = ["compile_advisor_graph"]
