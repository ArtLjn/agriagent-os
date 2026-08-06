"""ReAct loop — agent's core decision cycle.

Pipeline (vertical slice + capability pin):
    user_input
        ↓
    [skill_loader.load_all]             → unified skill registry (mcp + local)
        ↓
    [context.build_initial_messages]    → system + history + new user msg
        ↓
    [LLM chat with tools]               → assistant msg + tool_calls (or final)
        ↓
    [hitl.gate]   ──── if write* ───→   [await user approval]
        ↓                                       ↓
    [skill.execute(args, ctx)]         (rejected: end turn)
        ↓
    [context.append tool result]
        ↓
    loop back to LLM chat (max N steps)

Turn is the single source of truth — every node reads & mutates it.
Each node emits SSE events to the AsyncGenerator consumer (main.py).

Skill 分类：
  - kind=mcp   → execute 内部用 ctx.business_client.call_tool(...)
  - kind=local → execute 内部直接计算或调第三方 API

两种 skill 共享同一套 LLM tools schema 和 ReAct 循环。

流式策略：
  - tool_calls 步骤：仍用同步 chat()，因为需要完整的 tool_calls 结构
  - 最终回答步骤（无 tool_calls）：用 chat_stream() 逐 token 推送
"""
from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable

from agent.core import context, hitl, memory
from agent.core.turn import Turn
from agent.infra import sse
from agent.infra.llm import chat_stream, MODEL
from agent.infra.logging import log_event
from agent.infra.mcp_client import BusinessClient
from agent.infra.trace import trace_llm_call, trace_tool_call
from agent.skills import loader as skill_loader
from agent.skills.context import SkillContext

logger = logging.getLogger(__name__)

ApprovalWaiter = Callable[[str], Awaitable[tuple[bool, str]]]


async def run_turn(
    turn: Turn,
    approval_waiter: ApprovalWaiter,
) -> AsyncGenerator[dict, None]:
    """Execute one user turn. Yields SSE events as they happen."""
    turn.memory_snapshot = memory.snapshot(turn.conversation_id)

    yield sse.meta(turn.turn_id, turn.conversation_id, turn.user_input)

    skills = skill_loader.load_all()
    tools_schema = skill_loader.to_openai_tools(skills)
    skill_index = {s.name: s for s in skills}
    logger.info(
        "loaded %d skills: %s",
        len(skills),
        [f"{s.name}({s.kind},{s.risk_level})" for s in skills],
    )

    turn.messages = context.build_initial_messages(
        turn.user_input, turn.memory_snapshot
    )

    try:
        async with BusinessClient() as business:
            skill_ctx = SkillContext(business_client=business, turn=turn)

            while turn.status == "running" and turn.step_count < turn.max_steps:
                turn.step_count += 1

                # ── 流式 LLM 调用 ───────────────────────────────
                _llm_start = time.time()
                full_content = ""
                tool_calls_result: list[dict] = []
                has_tool_calls = False

                try:
                    async for token in chat_stream(turn.messages, tools=tools_schema):
                        if token["type"] == "text":
                            full_content += token["delta"]
                        elif token["type"] == "tool_call":
                            has_tool_calls = True
                        elif token["type"] == "done":
                            tool_calls_result = token.get("tool_calls", [])
                        elif token["type"] == "error":
                            raise RuntimeError(token["message"])

                    # 记录 LLM trace（MongoDB）+ 结构化日志（log_event）
                    _llm_ms = int((time.time() - _llm_start) * 1000)
                    trace_llm_call(
                        model=MODEL,
                        messages=turn.messages,
                        response={
                            "content_length": len(full_content),
                            "tool_calls_count": len(tool_calls_result),
                        },
                        duration_ms=_llm_ms,
                    )
                    log_event(
                        logger, logging.INFO, "llm_call",
                        status="success",
                        duration_ms=_llm_ms,
                        data={"model": MODEL, "tool_calls": len(tool_calls_result)},
                    )
                except Exception as exc:
                    turn.status = "failed"
                    turn.error = f"llm_stream_failed: {exc}"
                    ev = sse.error_event(str(exc), "llm_call_failed")
                    turn.emit("error", ev["data"])
                    yield ev
                    break

                # 有 tool_calls → 文本是思考过程，发给 thought 事件
                if tool_calls_result and full_content:
                    ev = sse.thought(full_content)
                    turn.emit("thought", ev["data"])
                    yield ev

                # 无 tool_calls → 流式输出最终回答
                if not tool_calls_result:
                    turn.final_answer = full_content
                    turn.status = "completed"
                    yield sse.final_answer_start()
                    yield sse.final_answer(full_content)
                    break

                # 有 tool_calls → 走工具调用流程
                assistant_msg = context.assistant_message_with_tool_calls(
                    full_content, tool_calls_result
                )
                turn.messages.append(assistant_msg)

                for tc in tool_calls_result:
                    tool_name = tc["name"]
                    args = tc["arguments"]
                    tool_call_id = tc["id"]

                    skill = skill_index.get(tool_name)
                    if skill is None:
                        err_msg = f"未知工具: {tool_name}"
                        result = {"error": err_msg}
                        ev = sse.observation(tool_name, None, error=err_msg)
                        turn.emit("observation", ev["data"])
                        yield ev
                        turn.messages.append(
                            context.tool_result_message(
                                tool_call_id, tool_name, result
                            )
                        )
                        continue

                    risk = skill.dynamic_risk_level(args)
                    if hitl.needs_approval(risk):
                        turn = hitl.gate(
                            turn,
                            tool_name=tool_name,
                            tool_description=skill.description,
                            arguments=args,
                            tool_call_id=tool_call_id,
                            rationale=full_content,
                        )
                        ev = sse.approval_required(
                            tool_name=tool_name,
                            arguments=args,
                            rationale=full_content,
                            risk_level=risk,
                            turn_id=turn.turn_id,
                        )
                        turn.emit("approval_required", ev["data"])
                        yield ev

                        decision, reason = await approval_waiter(turn.turn_id)
                        turn = hitl.approve(turn, decision, reason)

                        ev = sse.approval_result(
                            "approved" if decision else "rejected", reason
                        )
                        turn.emit("approval_result", ev["data"])
                        yield ev

                        if not decision:
                            turn.final_answer = (
                                f"已取消该操作：{reason or '用户拒绝执行'}"
                            )
                            yield sse.final_answer(turn.final_answer)
                            break

                    if turn.status == "rejected":
                        break

                    ev = sse.action(tool_name, args, rationale=full_content)
                    # 先 emit 占位事件，skill 可能兜底替换参数后回写
                    turn.emit("action", ev["data"])

                    try:
                        _tool_start = time.time()
                        result_obj = await skill.execute(args, skill_ctx)
                        _tool_ms = int((time.time() - _tool_start) * 1000)
                        # skill 兜底可能回写了 action 事件的 arguments
                        # 从 turn.events 取最新 action data 发给客户端
                        action_data = _find_latest_action_data(turn, tool_name) or ev["data"]
                        yield sse.action(
                            action_data["tool_name"],
                            action_data.get("arguments", args),
                            rationale=action_data.get("rationale", ""),
                        )
                        if result_obj.error:
                            result = {"error": result_obj.error}
                            ev = sse.observation(
                                tool_name, None, error=result_obj.error
                            )
                            trace_tool_call(tool_name, args, None, duration_ms=_tool_ms, error=result_obj.error)
                        else:
                            result = result_obj.data
                            ev = sse.observation(tool_name, result)
                            trace_tool_call(tool_name, args, result, duration_ms=_tool_ms)
                        turn.emit("observation", ev["data"])
                        yield ev
                    except Exception as exc:
                        logger.exception("skill execution failed: %s", tool_name)
                        result = {"error": str(exc)}
                        ev = sse.observation(tool_name, None, error=str(exc))
                        turn.emit("observation", ev["data"])
                        yield ev
                        trace_tool_call(tool_name, args, None, error=str(exc))

                    tool_msg = context.tool_result_message(
                        tool_call_id, tool_name, result
                    )
                    turn.messages.append(tool_msg)

                if turn.status == "rejected":
                    break

            if turn.status == "running":
                turn.status = "failed"
                turn.error = "max_steps_reached"
                ev = sse.error_event(
                    "达到最大步数限制，请缩小问题范围或重试", "max_steps"
                )
                turn.emit("error", ev["data"])
                yield ev

    except Exception as exc:
        logger.exception("run_turn pipeline crashed")
        turn.status = "failed"
        turn.error = str(exc)
        ev = sse.error_event(str(exc), "pipeline_crash")
        turn.emit("error", ev["data"])
        yield ev

    _persist_memory(turn)

    yield sse.done(turn.status, turn.turn_id)


def _persist_memory(turn: Turn) -> None:
    non_system = [m for m in turn.messages if m.get("role") != "system"]
    memory.save_messages(turn.conversation_id, non_system)


def _find_latest_action_data(turn: Turn, tool_name: str) -> dict | None:
    """从 turn.events 反向找最近的 action 事件 data。

    skill 兜底可能通过 _patch_action_args 回写了 arguments，
    这里取最新值用于发给客户端。
    """
    for event in reversed(turn.events):
        if event.get("type") != "action":
            continue
        data = event.get("data") or {}
        if data.get("tool_name") == tool_name:
            return data
    return None
