"""LangGraph 图编译模块 — 自定义 StateGraph 实现并行 Skill 执行。"""

import asyncio
import logging
from typing import Annotated, Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from app.core.llm import get_llm
from app.skills import get_langchain_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一位经验丰富的农业技术顾问，擅长西瓜、豆角等作物的种植管理。"
    "你具备以下能力：查询天气预报和灾害预警、查看种植周期和当前阶段、"
    "了解近期农事记录、统计成本收支。请根据用户的问题，主动调用合适的工具"
    "获取信息，然后给出具体、可操作的建议。回答要简洁明了，适合农民理解。"
    "使用中文回答。"
)


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _should_continue(state: AgentState) -> str:
    """判断是否需要继续调用工具。"""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


def _llm_node(state: AgentState) -> dict:
    """LLM 推理节点。"""
    tools = get_langchain_tools()
    llm = get_llm().bind_tools(tools)
    system = HumanMessage(content=SYSTEM_PROMPT)
    response = llm.invoke([system] + state["messages"])
    return {"messages": [response]}


async def _parallel_tool_node(state: AgentState) -> dict:
    """并行执行多个 tool_calls 的节点。"""
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": []}

    tool_map = {t.name: t for t in get_langchain_tools()}

    async def _call_one(tc: dict) -> ToolMessage:
        name = tc["name"]
        args = tc["args"]
        tool_call_id = tc["id"]
        logger.info("Skill 调用 %s(%s)", name, args)
        try:
            tool = tool_map.get(name)
            if not tool:
                return ToolMessage(content=f"未知工具: {name}", tool_call_id=tool_call_id)
            result = await tool.ainvoke(args)
            summary = str(result)[:120].replace("\n", " ")
            logger.info("Skill 返回 %s -> %s", name, summary)
            return ToolMessage(content=str(result), tool_call_id=tool_call_id)
        except Exception as e:
            logger.error("Skill 失败 %s: %s", name, e)
            return ToolMessage(content=f"工具调用失败: {e}", tool_call_id=tool_call_id)

    if len(last.tool_calls) == 1:
        results = [await _call_one(last.tool_calls[0])]
    else:
        logger.info("并行执行 %d 个 Skill", len(last.tool_calls))
        results = await asyncio.gather(*[_call_one(tc) for tc in last.tool_calls])

    return {"messages": results}


def compile_advisor_graph():
    """编译建议 Agent 的 StateGraph（支持并行 Skill 执行）。"""
    graph = StateGraph(AgentState)
    graph.add_node("llm", _llm_node)
    graph.add_node("tools", _parallel_tool_node)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")
    return graph.compile()


__all__ = ["compile_advisor_graph"]
