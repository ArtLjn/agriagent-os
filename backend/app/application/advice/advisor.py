"""建议 Agent 封装，提供每日建议和用户问答接口。"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy.orm import Session

from app.agent.executor.pending_actions import handle_pending_action
from app.agent.guardrails import check_input, filter_output
from app.agent.router.intent import IntentType, classify_intent, get_greeting_reply
from app.shared.llm import get_llm
from app.application.chat.helpers import record_agent_response
from app.agent.runtime.final_prompt_budget import FinalPromptBudget
from app.agent.runtime.loop import (
    AgentLoopMaxStepsExceeded,
    run_agent_loop,
    stream_agent_loop,
)
from app.context.pack import ContextPackService
from app.infra.trace_context import clear_trace, init_trace, set_round_index
from app.shared.logging import log_event
from app.domains.conversation.models import Conversation
from app.domains.farm.models import Farm
from app.domains.conversation.service import (
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
    context_pack_messages = _build_history_messages_from_context_pack(
        db=db,
        conversation_id=conversation_id,
        current_user_input=current_user_input,
    )
    if context_pack_messages is not None:
        return context_pack_messages
    records = get_recent_messages(db, conversation_id, limit=limit)
    messages = _records_to_history_messages(records)
    if (
        current_user_input is not None
        and messages
        and isinstance(messages[-1], HumanMessage)
        and messages[-1].content == current_user_input
    ):
        messages = _drop_current_user_input(messages, current_user_input)
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
    context_pack_messages = await _async_build_history_messages_from_context_pack(
        db=db,
        conversation_id=conversation_id,
        current_user_input=current_user_input,
    )
    if context_pack_messages is not None:
        return context_pack_messages
    records = await async_get_recent_messages(db, conversation_id, limit=limit)
    messages = _records_to_history_messages(records)
    if (
        current_user_input is not None
        and messages
        and isinstance(messages[-1], HumanMessage)
        and messages[-1].content == current_user_input
    ):
        messages = _drop_current_user_input(messages, current_user_input)
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


def _build_history_messages_from_context_pack(
    *,
    db: Session,
    conversation_id: int,
    current_user_input: str | None,
) -> list[HumanMessage | AIMessage] | None:
    try:
        return asyncio.run(
            _async_build_history_messages_from_context_pack(
                db=db,
                conversation_id=conversation_id,
                current_user_input=current_user_input,
            )
        )
    except RuntimeError:
        return None


async def _async_build_history_messages_from_context_pack(
    *,
    db: Session,
    conversation_id: int,
    current_user_input: str | None,
) -> list[HumanMessage | AIMessage] | None:
    try:
        conversation = db.get(Conversation, conversation_id)
        if not isinstance(conversation, Conversation):
            return None
        pack = await ContextPackService().build(
            db=db,
            farm_id=conversation.farm_id,
            session_id=conversation.session_id,
            user_id=conversation.user_id,
        )
        if not pack.recent_messages and pack.summary is None:
            return None
        messages = _records_to_history_messages(pack.recent_messages)
        return _drop_current_user_input(messages, current_user_input)
    except Exception:
        return None


def _drop_current_user_input(
    messages: list[HumanMessage | AIMessage],
    current_user_input: str | None,
) -> list[HumanMessage | AIMessage]:
    if current_user_input is None:
        return messages
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if isinstance(message, HumanMessage) and message.content == current_user_input:
            return messages[:index] + messages[index + 1 :]
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
    """每日建议结构化生成使用短 prompt，避免进入聊天 loop 追加上下文。"""
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
    """流式调用建议 Agent，逐 token 返回最终 AI 回复。

    链路位置: ``stream_chat.py::_stream_query_or_advisor_reply`` 的下游，
    是 Agent 的真正入口。本函数负责把"用户消息"加工成"最终回复"::

        ① 安全检查       输入被拦截时直接 yield 提示，return
        ② trace 初始化   本轮 agent_turn 开始计时
        ③ 短路分支（命中即 return，不进 Agent）:
            - 问候语
            - 不支持能力
            - pending_action 命中（与 stream_chat 层的检查是双保险）
        ④ 构建 history + 当前消息，调 stream_agent_loop 进入 ReAct 循环

    关于 yield 的语义: 本函数是 "最终回复" 的流式分段（每段 3 字符、
    20ms 间隔），不是 LLM 原生的 token 流。前端的打字机效果由此产生。
    """
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
    started_at = time.perf_counter()
    log_event(
        logger,
        logging.INFO,
        "agent_turn_started",
        request_id=request_id,
        session_id=session_id,
        status="started",
        data={
            "farm_id": farm_id,
            "conversation_id": conversation_id,
            "message_len": len(user_input),
            "call_type": call_type,
        },
    )

    # 意图路由：问候语直接回复，跳过 ReAct loop
    intent = classify_intent(user_input)
    farm_uid = _resolve_farm_uid(db, farm_id)

    step = 0
    decided_tools: list[str] = []
    observed_tool_results = 0
    final_reply_len = 0
    try:
        # ③-a 问候语短路：直接给固定文案，跳过 Agent
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

        # ③-b 不支持能力短路：明示告诉用户这条路做不到
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

        # ③-c pending 短路：与 stream_chat 层的双保险（这里带 farm_uid）
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

        # ④ 进入 ReAct Agent：拼历史消息 + 当前消息作为初始 state
        history = await _async_build_history_messages(
            db, conversation_id, current_user_input=user_input
        )
        messages = history + [HumanMessage(content=user_input)]

        # stream_agent_loop 每次 yield 形如 {"llm": update} / {"tools": update}
        # 这里只关心 update.messages 里新增的消息类型，做日志和最终回复提取
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
                        observed_tool_results += 1
                        log_event(
                            logger,
                            logging.DEBUG,
                            "agent_tool_result_observed",
                            request_id=request_id,
                            session_id=session_id,
                            status="success",
                            data={
                                "step": step,
                                "node": node,
                                "result_len": len(str(msg.content)),
                                "result_preview": str(msg.content)[:150],
                            },
                        )
                    elif isinstance(msg, AIMessage):
                        if msg.tool_calls:
                            # LLM 决定调工具：记录每个 tool_call 决策，下一轮工具节点会执行
                            for tc in msg.tool_calls:
                                tool_name = str(tc.get("name") or "")
                                if tool_name:
                                    decided_tools.append(tool_name)
                                args = tc.get("args") or {}
                                log_event(
                                    logger,
                                    logging.INFO,
                                    "agent_tool_call_decided",
                                    request_id=request_id,
                                    session_id=session_id,
                                    status="success",
                                    data={
                                        "step": step,
                                        "tool": tool_name,
                                        "arg_keys": list(args)
                                        if isinstance(args, dict)
                                        else [],
                                    },
                                )
                        elif msg.content:
                            # LLM 不再调工具且带正文 = 最终回复；
                            # 切片 + sleep 制造前端打字机效果
                            final_reply_len = len(msg.content)
                            log_event(
                                logger,
                                logging.DEBUG,
                                "agent_final_reply_generated",
                                request_id=request_id,
                                session_id=session_id,
                                status="success",
                                data={
                                    "step": step,
                                    "reply_len": final_reply_len,
                                },
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
        log_event(
            logger,
            logging.ERROR,
            "agent_turn_failed",
            request_id=request_id,
            session_id=session_id,
            status="failed",
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            data={"farm_id": farm_id, "steps": step},
            error={"code": "AGENT_LOOP_MAX_STEPS_EXCEEDED"},
        )
        yield "Agent 处理步数超出限制，请简化您的问题后重试。"
        return
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            "agent_turn_failed",
            request_id=request_id,
            session_id=session_id,
            status="failed",
            duration_ms=int((time.perf_counter() - started_at) * 1000),
            data={"farm_id": farm_id, "steps": step},
            error={"code": e.__class__.__name__},
        )
        yield "抱歉，AI 服务暂时不可用，请稍后重试。"
        return
    finally:
        clear_trace()

    log_event(
        logger,
        logging.INFO,
        "agent_turn_summary",
        request_id=request_id,
        session_id=session_id,
        status="success",
        duration_ms=int((time.perf_counter() - started_at) * 1000),
        data={
            "farm_id": farm_id,
            "conversation_id": conversation_id,
            "steps": step,
            "llm_tool_calls": len(decided_tools),
            "decided_tools": decided_tools,
            "tool_results": observed_tool_results,
            "reply_len": final_reply_len,
        },
    )


__all__ = ["build_advisor_agent", "invoke_advisor", "stream_advisor"]
