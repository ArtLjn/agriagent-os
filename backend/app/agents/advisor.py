"""建议 Agent 封装，提供每日建议和用户问答接口。"""

import logging
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.graph import compile_advisor_graph

logger = logging.getLogger(__name__)

_ADVISOR_GRAPH = None


def _get_advisor_graph():
    """获取全局 Advisor 图实例（单例）。"""
    global _ADVISOR_GRAPH
    if _ADVISOR_GRAPH is None:
        _ADVISOR_GRAPH = compile_advisor_graph()
    return _ADVISOR_GRAPH


def build_advisor_agent():
    """构建并返回建议 Agent 图（主要用于测试）。"""
    return compile_advisor_graph()


async def invoke_advisor(user_input: str) -> str:
    """调用建议 Agent 回答用户问题。"""
    logger.info("Agent 收到请求: %s", user_input[:200])
    graph = _get_advisor_graph()
    result = await graph.ainvoke({"messages": [HumanMessage(content=user_input)]})
    reply = result["messages"][-1].content
    logger.info("Agent 回复完成，长度 %d 字符", len(reply))
    return reply


async def stream_advisor(user_input: str) -> AsyncGenerator[str, None]:
    """流式调用建议 Agent，逐 token 返回最终 AI 回复。"""
    logger.info("Agent 流式请求: %s", user_input[:200])
    graph = _get_advisor_graph()
    step = 0
    async for event in graph.astream({"messages": [HumanMessage(content=user_input)]}):
        for node, state in event.items():
            step += 1
            for msg in state.get("messages", []):
                if isinstance(msg, ToolMessage):
                    logger.info("[step %d] 工具 %s 返回: %s", step, node, str(msg.content)[:150])
                elif isinstance(msg, AIMessage):
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            logger.info("[step %d] LLM 决定调用工具: %s(%s)", step, tc["name"], tc["args"])
                    elif msg.content:
                        logger.info("[step %d] LLM 最终回复，长度 %d", step, len(msg.content))
                        yield msg.content
    logger.info("Agent 流式完成，共 %d 步", step)


__all__ = ["build_advisor_agent", "invoke_advisor", "stream_advisor"]
