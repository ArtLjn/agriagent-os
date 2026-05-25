"""建议 Agent 封装，提供每日建议和用户问答接口。"""

import logging
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from app.agents.graph import compile_advisor_graph
from app.core.guardrails import check_input, filter_output

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


async def invoke_advisor(user_input: str, farm_id: int = 1) -> str:
    """调用建议 Agent 回答用户问题。"""
    ok, reason = check_input(user_input)
    if not ok:
        logger.warning("Agent 输入被拦截 | farm_id=%s, reason=%s", farm_id, reason)
        return f"输入内容包含不安全信息，已被拦截。原因：{reason}"

    logger.info("Agent 收到请求 | farm_id=%s: %s", farm_id, user_input[:200])
    graph = _get_advisor_graph()
    try:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=user_input)], "farm_id": farm_id}
        )
    except GraphRecursionError:
        logger.error("Agent 步数超限 | farm_id=%s", farm_id)
        return "Agent 处理步数超出限制，请简化您的问题后重试。"

    reply = result["messages"][-1].content
    filtered = filter_output(reply)
    logger.info("Agent 回复完成 | farm_id=%s, 长度 %d 字符", farm_id, len(filtered))
    return filtered


async def stream_advisor(
    user_input: str, farm_id: int = 1
) -> AsyncGenerator[str, None]:
    """流式调用建议 Agent，逐 token 返回最终 AI 回复。"""
    ok, reason = check_input(user_input)
    if not ok:
        logger.warning("Agent 输入被拦截 | farm_id=%s, reason=%s", farm_id, reason)
        yield f"输入内容包含不安全信息，已被拦截。原因：{reason}"
        return

    logger.info("Agent 流式请求 | farm_id=%s: %s", farm_id, user_input[:200])
    graph = _get_advisor_graph()
    step = 0
    try:
        async for event in graph.astream(
            {"messages": [HumanMessage(content=user_input)], "farm_id": farm_id}
        ):
            for node, state in event.items():
                step += 1
                for msg in state.get("messages", []):
                    if isinstance(msg, ToolMessage):
                        logger.info(
                            "[step %d] 工具 %s 返回: %s", step, node, str(msg.content)[:150]
                        )
                    elif isinstance(msg, AIMessage):
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                logger.info(
                                    "[step %d] LLM 决定调用工具: %s(%s)",
                                    step,
                                    tc["name"],
                                    tc["args"],
                                )
                        elif msg.content:
                            logger.info(
                                "[step %d] LLM 最终回复，长度 %d", step, len(msg.content)
                            )
                            yield filter_output(msg.content)
    except GraphRecursionError:
        logger.error("Agent 流式步数超限 | farm_id=%s", farm_id)
        yield "Agent 处理步数超出限制，请简化您的问题后重试。"

    logger.info("Agent 流式完成，共 %d 步", step)


__all__ = ["build_advisor_agent", "invoke_advisor", "stream_advisor"]
