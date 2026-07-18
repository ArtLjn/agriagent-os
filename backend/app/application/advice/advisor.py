"""建议 Agent 封装，提供每日建议和用户问答接口。"""

import asyncio
import logging
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy.orm import Session

from app.agent.executor.pending_actions import handle_pending_action
from app.agent.guardrails import check_input, filter_output
from app.agent.router.intent import IntentType, classify_intent, get_greeting_reply
from app.core.llm import get_llm
from app.application.chat.helpers import record_agent_response
from app.agent.runtime.final_prompt_budget import FinalPromptBudget
from app.agent.runtime.loop import (
    AgentLoopMaxStepsExceeded,
    run_agent_loop,
    stream_agent_loop,
)
from app.infra.trace_context import clear_trace, init_trace, set_round_index
from app.models.farm import Farm
from app.services.conversation_service import (
    async_get_recent_messages,
    get_recent_messages,
)

logger = logging.getLogger(__name__)

_UNSUPPORTED_DELETE_COST_PATTERNS = (
    "清理所有账单",
    "删除所有账单",
    "清空账单",
    "清除账单",
    "删除账单",
)


def build_advisor_agent():
    """构建并返回建议 Agent 运行入口（主要用于测试）。"""
    return run_agent_loop


def _build_history_messages(
    db: Session | None,
    conversation_id: int | None,
    limit: int = 20,
    current_user_input: str | None = None,
    recent_message_limit: int = 10,
) -> list[HumanMessage | AIMessage]:
    """从数据库加载最近 N 条消息，转为 LangChain message 列表。"""
    if db is None or conversation_id is None:
        return []
    records = get_recent_messages(db, conversation_id, limit=limit)
    messages = _records_to_history_messages(records)
    if (
        current_user_input is not None
        and messages
        and isinstance(messages[-1], HumanMessage)
        and messages[-1].content == current_user_input
    ):
        messages = messages[:-1]
    messages = _summarize_history_messages(messages, recent_message_limit)
    return messages


async def _async_build_history_messages(
    db: Session | None,
    conversation_id: int | None,
    limit: int = 20,
    current_user_input: str | None = None,
    recent_message_limit: int = 10,
) -> list[HumanMessage | AIMessage]:
    """async 请求链路构建历史消息。"""
    if db is None or conversation_id is None:
        return []
    records = await async_get_recent_messages(db, conversation_id, limit=limit)
    messages = _records_to_history_messages(records)
    if (
        current_user_input is not None
        and messages
        and isinstance(messages[-1], HumanMessage)
        and messages[-1].content == current_user_input
    ):
        messages = messages[:-1]
    return _summarize_history_messages(messages, recent_message_limit)


def _records_to_history_messages(
    records,
) -> list[HumanMessage | AIMessage]:
    messages: list[HumanMessage | AIMessage] = []
    for rec in records:
        if rec.role == "user":
            messages.append(HumanMessage(content=rec.content))
        elif rec.role == "assistant":
            messages.append(AIMessage(content=rec.content))
    return messages


def _summarize_history_messages(
    messages: list[HumanMessage | AIMessage],
    recent_message_limit: int,
) -> list[HumanMessage | AIMessage]:
    if len(messages) <= recent_message_limit:
        return messages
    return FinalPromptBudget(
        recent_messages=recent_message_limit,
    ).summarize_old_messages(messages)


def _resolve_farm_uid(db: Session | None, farm_id: int) -> str | None:
    """从可信内部 farm_id 解析外部 UUID。"""
    if db is None:
        return None
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    return farm.uid if farm else None


def _unsupported_capability_reply(user_input: str) -> str | None:
    """拦截当前没有 Skill 支撑的高风险能力，避免模型承诺幻觉。"""
    normalized = "".join(user_input.split())
    if any(pattern in normalized for pattern in _UNSUPPORTED_DELETE_COST_PATTERNS):
        return "暂不支持通过对话删除账单或清理所有账单。你可以先查询账单明细，再到成本列表里手动删除需要移除的记录。"
    return None


async def invoke_advisor(
    user_input: str,
    farm_id: int,
    db: Session | None = None,
    conversation_id: int | None = None,
    session_id: str = "",
    request_id: str = "",
    user_id: str | None = None,
    call_type: str = "chat",
) -> str:
    """调用建议 Agent 回答用户问题。"""
    ok, reason = check_input(user_input)
    if not ok:
        logger.warning("Agent 输入被拦截 | farm_id=%s, reason=%s", farm_id, reason)
        return f"输入内容包含不安全信息，已被拦截。原因：{reason}"

    init_trace(
        farm_id=farm_id,
        session_id=session_id,
        request_id=request_id,
        user_id=user_id,
        call_type=call_type,
    )
    logger.info("Agent 收到请求 | farm_id=%s: %s", farm_id, user_input[:200])

    # 意图路由：问候语直接回复，跳过 ReAct loop
    intent = classify_intent(user_input)
    farm_uid = _resolve_farm_uid(db, farm_id)

    try:
        if intent == IntentType.GREETING:
            reply = filter_output(get_greeting_reply(user_input))
            record_agent_response(
                node_name="greeting_reply",
                user_input=user_input,
                reply=reply,
                reason="greeting_shortcut",
            )
            return reply

        unsupported_reply = _unsupported_capability_reply(user_input)
        if unsupported_reply:
            record_agent_response(
                node_name="unsupported_capability_reply",
                user_input=user_input,
                reply=unsupported_reply,
                reason="unsupported_capability",
            )
            return unsupported_reply

        if call_type == "daily_advice":
            reply = await _invoke_direct_daily_advice_llm(user_input)
            record_agent_response(
                node_name="daily_advice_reply",
                user_input=user_input,
                reply=reply,
                reason="direct_daily_advice",
            )
            return reply

        pending_decision = await handle_pending_action(
            farm_id=farm_id,
            message=user_input,
            farm_uid=farm_uid,
            session_id=session_id,
        )
        if pending_decision.handled:
            reply = filter_output(pending_decision.reply)
            record_agent_response(
                node_name="pending_action_reply",
                user_input=user_input,
                reply=reply,
                reason="pending_action_handled",
            )
            return reply

        # 构建历史消息 + 当前消息
        history = await _async_build_history_messages(
            db, conversation_id, current_user_input=user_input
        )
        messages = history + [HumanMessage(content=user_input)]

        result = await run_agent_loop(
            {
                "messages": messages,
                "farm_id": farm_id,
                "farm_uid": farm_uid,
                "intent": intent.value,
                "user_id": user_id,
                "session_id": session_id,
            },
            max_steps=15,
        )
        reply = result["messages"][-1].content
        filtered = filter_output(reply)
        set_round_index(result.get("trace_round_index"))
        record_agent_response(
            node_name="final_reply",
            user_input=user_input,
            reply=filtered,
            reason="react_loop_final_response",
        )
        logger.info("Agent 回复完成 | farm_id=%s, 长度 %d 字符", farm_id, len(filtered))
        return filtered
    except AgentLoopMaxStepsExceeded:
        logger.error("Agent 步数超限 | farm_id=%s", farm_id)
        return "Agent 处理步数超出限制，请简化您的问题后重试。"
    finally:
        clear_trace()


async def _invoke_direct_daily_advice_llm(prompt: str) -> str:
    """每日建议结构化生成使用短 prompt，避免进入聊天图追加上下文。"""
    llm = get_llm(role="generation")
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    content = getattr(response, "content", response)
    return filter_output(str(content or ""))


async def stream_advisor(
    user_input: str,
    farm_id: int,
    db: Session | None = None,
    conversation_id: int | None = None,
    session_id: str = "",
    request_id: str = "",
    user_id: str | None = None,
    call_type: str = "stream_chat",
) -> AsyncGenerator[str, None]:
    """流式调用建议 Agent，逐 token 返回最终 AI 回复。"""
    ok, reason = check_input(user_input)
    if not ok:
        logger.warning("Agent 输入被拦截 | farm_id=%s, reason=%s", farm_id, reason)
        yield f"输入内容包含不安全信息，已被拦截。原因：{reason}"
        return

    init_trace(
        farm_id=farm_id,
        session_id=session_id,
        request_id=request_id,
        user_id=user_id,
        call_type=call_type,
    )
    logger.info("Agent 流式请求 | farm_id=%s: %s", farm_id, user_input[:200])

    # 意图路由：问候语直接回复，跳过 ReAct loop
    intent = classify_intent(user_input)
    farm_uid = _resolve_farm_uid(db, farm_id)

    step = 0
    try:
        if intent == IntentType.GREETING:
            reply = filter_output(get_greeting_reply(user_input))
            record_agent_response(
                node_name="greeting_reply",
                user_input=user_input,
                reply=reply,
                reason="greeting_shortcut",
            )
            yield reply
            return

        unsupported_reply = _unsupported_capability_reply(user_input)
        if unsupported_reply:
            record_agent_response(
                node_name="unsupported_capability_reply",
                user_input=user_input,
                reply=unsupported_reply,
                reason="unsupported_capability",
            )
            yield unsupported_reply
            return

        pending_decision = await handle_pending_action(
            farm_id=farm_id,
            message=user_input,
            farm_uid=farm_uid,
            session_id=session_id,
        )
        if pending_decision.handled:
            reply = filter_output(pending_decision.reply)
            record_agent_response(
                node_name="pending_action_reply",
                user_input=user_input,
                reply=reply,
                reason="pending_action_handled",
            )
            yield reply
            return

        # 构建历史消息 + 当前消息
        history = await _async_build_history_messages(
            db, conversation_id, current_user_input=user_input
        )
        messages = history + [HumanMessage(content=user_input)]

        async for event in stream_agent_loop(
            {
                "messages": messages,
                "farm_id": farm_id,
                "farm_uid": farm_uid,
                "intent": intent.value,
                "user_id": user_id,
                "session_id": session_id,
            },
            max_steps=15,
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
                            filtered = filter_output(msg.content)
                            set_round_index(state.get("trace_round_index"))
                            record_agent_response(
                                node_name="final_reply",
                                user_input=user_input,
                                reply=filtered,
                                reason="react_loop_final_response",
                            )
                            chunk_size = 3
                            delay = 0.02
                            for i in range(0, len(filtered), chunk_size):
                                yield filtered[i : i + chunk_size]
                                await asyncio.sleep(delay)
    except AgentLoopMaxStepsExceeded:
        logger.error("Agent 流式步数超限 | farm_id=%s", farm_id)
        yield "Agent 处理步数超出限制，请简化您的问题后重试。"
        return
    except Exception as e:
        logger.error("Agent 流式异常 | farm_id=%s | error=%s", farm_id, e)
        yield "抱歉，AI 服务暂时不可用，请稍后重试。"
        return
    finally:
        clear_trace()

    logger.info("Agent 流式完成，共 %d 步", step)


__all__ = ["build_advisor_agent", "invoke_advisor", "stream_advisor"]
