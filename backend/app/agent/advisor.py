"""建议 Agent 封装，提供每日建议和用户问答接口。"""

import logging
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from sqlalchemy.orm import Session

from app.agent.graph import compile_advisor_graph
from app.agent.guardrails import check_input, filter_output
from app.agent.skills import get_skill_manager, build_skill_context
from app.infra.pending_actions import (
    get_pending,
    remove_pending,
    detect_user_intent,
)
from app.infra.trace_context import clear_trace, init_trace
from app.services.conversation_service import get_recent_messages

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


def _build_history_messages(
    db: Session | None, conversation_id: int | None, limit: int = 20
) -> list[HumanMessage | AIMessage]:
    """从数据库加载最近 N 条消息，转为 LangChain message 列表。"""
    if db is None or conversation_id is None:
        return []
    records = get_recent_messages(db, conversation_id, limit=limit)
    messages: list[HumanMessage | AIMessage] = []
    for rec in records:
        if rec.role == "user":
            messages.append(HumanMessage(content=rec.content))
        elif rec.role == "assistant":
            messages.append(AIMessage(content=rec.content))
    return messages


async def invoke_advisor(
    user_input: str,
    farm_id: int,
    db: Session | None = None,
    conversation_id: int | None = None,
    session_id: str = "",
    request_id: str = "",
) -> str:
    """调用建议 Agent 回答用户问题。"""
    ok, reason = check_input(user_input)
    if not ok:
        logger.warning("Agent 输入被拦截 | farm_id=%s, reason=%s", farm_id, reason)
        return f"输入内容包含不安全信息，已被拦截。原因：{reason}"

    init_trace(farm_id=farm_id, session_id=session_id, request_id=request_id)
    logger.info("Agent 收到请求 | farm_id=%s: %s", farm_id, user_input[:200])

    pending = get_pending(farm_id)
    if pending:
        intent = detect_user_intent(user_input)
        if intent == "confirm":
            logger.info(
                "用户确认执行 pending action | farm_id=%s | skill=%s",
                farm_id,
                pending.skill_name,
            )
            try:
                manager = get_skill_manager()
                ctx = build_skill_context(farm_id)
                result = await manager.execute(pending.skill_name, pending.params, ctx)
                reply = result.reply
            except Exception as e:
                logger.error("pending action 执行失败 | farm_id=%s | error=%s", farm_id, e)
                reply = "操作执行失败，请重试。"
            finally:
                remove_pending(farm_id)
            return filter_output(reply)
        if intent == "cancel":
            logger.info("用户取消 pending action | farm_id=%s", farm_id)
            remove_pending(farm_id)
            return "好的，已取消。"
        logger.info(
            "用户修改 pending action | farm_id=%s | intent=modify",
            farm_id,
        )
        remove_pending(farm_id)

    graph = _get_advisor_graph()

    # 构建历史消息 + 当前消息
    history = _build_history_messages(db, conversation_id)
    messages = history + [HumanMessage(content=user_input)]

    try:
        result = await graph.ainvoke(
            {"messages": messages, "farm_id": farm_id},
            config={
                "recursion_limit": 15,
                "run_name": "advisor_invoke",
                "metadata": {"farm_id": farm_id, "request_type": "chat"},
            },
        )
    except GraphRecursionError:
        logger.error("Agent 步数超限 | farm_id=%s", farm_id)
        return "Agent 处理步数超出限制，请简化您的问题后重试。"
    finally:
        clear_trace()

    reply = result["messages"][-1].content
    filtered = filter_output(reply)
    logger.info("Agent 回复完成 | farm_id=%s, 长度 %d 字符", farm_id, len(filtered))
    return filtered


async def stream_advisor(
    user_input: str,
    farm_id: int,
    db: Session | None = None,
    conversation_id: int | None = None,
    session_id: str = "",
    request_id: str = "",
) -> AsyncGenerator[str, None]:
    """流式调用建议 Agent，逐 token 返回最终 AI 回复。"""
    ok, reason = check_input(user_input)
    if not ok:
        logger.warning("Agent 输入被拦截 | farm_id=%s, reason=%s", farm_id, reason)
        yield f"输入内容包含不安全信息，已被拦截。原因：{reason}"
        return

    init_trace(farm_id=farm_id, session_id=session_id, request_id=request_id)
    logger.info("Agent 流式请求 | farm_id=%s: %s", farm_id, user_input[:200])

    pending = get_pending(farm_id)
    if pending:
        intent = detect_user_intent(user_input)
        if intent == "confirm":
            logger.info(
                "用户确认执行 pending action | farm_id=%s | skill=%s",
                farm_id,
                pending.skill_name,
            )
            try:
                manager = get_skill_manager()
                ctx = build_skill_context(farm_id)
                result = await manager.execute(pending.skill_name, pending.params, ctx)
                reply = result.reply
            except Exception as e:
                logger.error("pending action 执行失败 | farm_id=%s | error=%s", farm_id, e)
                reply = "操作执行失败，请重试。"
            finally:
                remove_pending(farm_id)
            yield filter_output(reply)
            return
        if intent == "cancel":
            logger.info("用户取消 pending action | farm_id=%s", farm_id)
            remove_pending(farm_id)
            yield "好的，已取消。"
            return
        logger.info(
            "用户修改 pending action | farm_id=%s | intent=modify",
            farm_id,
        )
        remove_pending(farm_id)

    graph = _get_advisor_graph()

    # 构建历史消息 + 当前消息
    history = _build_history_messages(db, conversation_id)
    messages = history + [HumanMessage(content=user_input)]

    step = 0
    try:
        async for event in graph.astream(
            {"messages": messages, "farm_id": farm_id},
            config={
                "recursion_limit": 15,
                "run_name": "advisor_stream",
                "metadata": {"farm_id": farm_id, "request_type": "stream_chat"},
            },
        ):
            for node, state in event.items():
                step += 1
                for msg in state.get("messages", []):
                    if isinstance(msg, ToolMessage):
                        logger.info(
                            "[step %d] 工具 %s 返回: %s",
                            step,
                            node,
                            str(msg.content)[:150],
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
                                "[step %d] LLM 最终回复，长度 %d",
                                step,
                                len(msg.content),
                            )
                            yield filter_output(msg.content)
    except GraphRecursionError:
        logger.error("Agent 流式步数超限 | farm_id=%s", farm_id)
        yield "Agent 处理步数超出限制，请简化您的问题后重试。"
        return
    finally:
        clear_trace()

    logger.info("Agent 流式完成，共 %d 步", step)


__all__ = ["build_advisor_agent", "invoke_advisor", "stream_advisor"]
