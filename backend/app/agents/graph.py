"""LangGraph 图编译模块 — 自定义 StateGraph 实现并行 Skill 执行。"""

import asyncio
import logging
from typing import Annotated

import time as _time

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.core.llm import get_llm
from app.core.pending_actions import is_write_skill, store_pending
from app.core.prompt_registry import get_registry
from app.core.prompt_renderer import render_prompt
from app.core.date_context import get_request_date
from app.core.database import SessionLocal
from app.core.trace_collector import get_collector
from app.core.trace_context import increment_round
from app.models.farm import Farm
from app.services import farm_context_service
from app.skills import get_langchain_tools

logger = logging.getLogger(__name__)

_KEEP_RECENT = 3


def micro_compact(messages: list) -> list:
    """压缩历史消息中旧的 tool result，只保留最近 N 个完整内容。"""
    tool_results = [
        (i, msg) for i, msg in enumerate(messages) if isinstance(msg, ToolMessage)
    ]
    if len(tool_results) <= _KEEP_RECENT:
        return messages

    result = list(messages)
    for _idx, (i, msg) in enumerate(tool_results[:-_KEEP_RECENT]):
        content = msg.content or ""
        if len(content) > 100:
            tool_name = getattr(msg, "name", "unknown")
            result[i] = ToolMessage(
                content=f"[已执行 {tool_name}]", tool_call_id=msg.tool_call_id
            )
    return result


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


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


def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点 — 使用模板渲染 system prompt，带上下文压缩。"""
    tools = get_langchain_tools()
    raw_llm = get_llm()
    llm = raw_llm.bind_tools(tools)
    model_name = getattr(raw_llm, "model_name", "unknown")
    _round_idx = increment_round()  # 副作用：轮次 +1
    collector = get_collector()

    # 获取农场上下文摘要和用户称呼
    db = SessionLocal()
    try:
        farm_context_summary = farm_context_service.build_summary(db, farm_id=1)
        farm = db.query(Farm).filter(Farm.id == 1).first()
        display_name = farm.display_name if farm and farm.display_name else "农友"
    except Exception:
        logger.warning("获取农场上下文失败，使用默认值", exc_info=True)
        farm_context_summary = ""
        display_name = "农友"
    finally:
        db.close()

    current_date = get_request_date()
    system_text = render_prompt(
        "system_base",
        variables={
            "farm_context_summary": farm_context_summary,
            "display_name": display_name,
        },
        registry=get_registry(),
        current_date=current_date,
    )

    # 记录 prompt_render trace
    collector.record(
        node_type="prompt_render",
        node_name="system_prompt",
        input_data={"template": "system_base", "variables_count": 2},
        output_data=system_text[:2000],
    )

    system = HumanMessage(content=system_text)
    messages = micro_compact(state["messages"])
    input_summary = _find_last_human_message(state["messages"])[:200]

    # LLM 调用 + 计时
    start = _time.perf_counter()
    try:
        response = llm.invoke([system] + messages)
    except Exception as exc:
        duration_ms = int((_time.perf_counter() - start) * 1000)
        collector.record(
            node_type="llm_call",
            node_name=model_name,
            input_data=input_summary,
            duration_ms=duration_ms,
            error_message=str(exc),
        )
        raise

    duration_ms = int((_time.perf_counter() - start) * 1000)

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
        logger.info(
            "LLM 工具选择 | tool_calls=%s | model=%s", tool_names, model_name
        )
        output_summary = f"tool_calls: {tool_names}"
    else:
        content = response.content or ""
        logger.info(
            "LLM 直接回复 | reply_len=%d | model=%s", len(content), model_name
        )
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
            params_str = ", ".join(f"{k}={v}" for k, v in args.items())
            return ToolMessage(
                content=(
                    f"已记录操作意图：{name}({params_str})。"
                    f"请向用户确认参数后执行。"
                    f"确认消息示例：记一笔：{args.get('category', '')} "
                    f"{args.get('amount', '')}元。确认？"
                ),
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
                name, duration_ms, summary,
            )
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                output_data=str(result)[:200],
                duration_ms=duration_ms,
            )
            return ToolMessage(content=str(result), tool_call_id=tool_call_id)
        except Exception as e:
            duration_ms = int((_time.perf_counter() - start) * 1000)
            logger.error(
                "Skill 失败 | name=%s | error=%s", name, e,
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
        results = await asyncio.gather(*[_call_one(tc) for tc in last.tool_calls])

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
