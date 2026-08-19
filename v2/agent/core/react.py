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

import asyncio
import json as _json
import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field

from agent.auth import create_delegation_token
from agent.config import settings
from agent.core import context, hitl, memory, planner, summarizer, tokenizer, verify
from agent.core.turn import StopReason, Turn, TurnPhase
from agent.infra import sse
from agent.infra.error_policy import LlmStreamError, classify_exception
from agent.infra.llm import MODEL, chat_stream
from agent.infra.logging import log_event
from agent.infra.mcp_client import BusinessClient, McpCallError
from agent.infra.trace import (
    get_trace,
    increment_step,
    trace_commit_state,
    trace_llm_call,
    trace_tool_call,
)
from agent.skills import loader as skill_loader
from agent.skills.base import Skill, SkillResult
from agent.skills.context import SkillContext
from agent.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

ApprovalWaiter = Callable[[str], Awaitable[tuple[bool, str]]]
SkillLookup = dict[str, Skill] | SkillRegistry
HEARTBEAT_INTERVAL_SECONDS = 5.0


# ── 数据容器 ──────────────────────────────────────────────


@dataclass
class _SkillExecState:
    """skill 执行结果容器，由 _run_skill_call 填充。"""

    result_obj: SkillResult | None = None
    result: dict | None = None
    finalize_after_success: bool = False
    error: str | None = None


@dataclass
class _PreparedCall:
    """skill 调用参数校验结果，由 _prepare_skill_call 填充。"""

    args: dict = field(default_factory=dict)
    proceed: bool = True


@dataclass
class _LlmResult:
    """LLM 调用结果。"""

    full_content: str = ""
    tool_calls: list[dict] = field(default_factory=list)


# ── 主入口 ────────────────────────────────────────────────


async def run_turn(
    turn: Turn,
    approval_waiter: ApprovalWaiter,
) -> AsyncGenerator[dict, None]:
    """Execute one user turn. Yields SSE events as they happen."""
    turn.set_phase(TurnPhase.SETUP)
    yield sse.meta(
        turn.turn_id,
        turn.conversation_id,
        turn.user_input,
        request_id=(get_trace().request_id if get_trace() else ""),
    )

    try:
        _registry, tools_schema, skill_registry, tracker, plan_box = (
            _setup_turn_runtime(turn)
        )
        turn.set_phase(TurnPhase.REASONING)

        async for ev in _try_compress_context(turn):
            yield ev
    except Exception as exc:
        logger.exception("run_turn setup failed")
        ev = _pipeline_error_event(turn, exc)
        yield ev
        _persist_memory(turn)
        yield sse.done(turn.status, turn.turn_id)
        return

    try:
        identity_headers = {
            "Authorization": f"Bearer {turn.agent_token}",
            "X-Delegation-Token": create_delegation_token(
                {
                    "user_id": turn.user_id,
                    "farm_uid": turn.farm_uid,
                    "role": turn.role,
                    "token_id": turn.token_id,
                    "scope": turn.scope,
                },
                conversation_id=turn.conversation_id,
                turn_id=turn.turn_id,
            ),
            "X-Farm-Uid": turn.farm_uid,
            "X-User-Id": turn.user_id,
            "X-Farm-Id": str(turn.farm_id),
        }
        async with BusinessClient(headers=identity_headers) as business:
            skill_ctx = SkillContext(
                business_client=business,
                turn=turn,
                user_id=turn.user_id,
                farm_id=turn.farm_id,
                farm_uid=turn.farm_uid,
                agent_token=turn.agent_token,
            )

            while turn.status == "running" and (
                turn.step_count < turn.max_steps or turn.finalization_pending
            ):
                turn.set_phase(TurnPhase.REASONING)
                turn.step_count += 1
                increment_step()

                async for ev in _run_single_reasoning_step(
                    turn=turn,
                    tools_schema=tools_schema,
                    tracker=tracker,
                    plan_box=plan_box,
                    skill_index=skill_registry,
                    skill_ctx=skill_ctx,
                    approval_waiter=approval_waiter,
                ):
                    yield ev

                # 写入成功后清空 tools，下一轮只允许生成最终答复
                if turn.finalization_pending:
                    tools_schema = []

                if turn.status != "running":
                    break

            if turn.status == "running":
                turn.set_phase(TurnPhase.FINALIZING)
                finalizer = (
                    _finalize_requested_error(turn)
                    if turn.finalization_request is not None
                    else _finalize_turn(turn)
                )
                async for ev in finalizer:
                    yield ev

    except Exception as exc:
        logger.exception("run_turn pipeline crashed")
        ev = _pipeline_error_event(turn, exc)
        yield ev

    _persist_memory(turn)
    yield sse.done(turn.status, turn.turn_id)


def _pipeline_error_event(turn: Turn, exc: Exception) -> dict:
    """将初始化或运行时异常转换为统一的 pipeline 错误事件。"""
    error_info = turn.record_error(
        "pipeline_crash",
        str(exc),
        phase=turn.phase,
        stop_reason=StopReason.PIPELINE_CRASH,
    )
    event = sse.error_event(
        error_info["message"],
        error_info["code"],
        phase=error_info["phase"],
        retryable=error_info["retryable"],
        attempt=error_info["attempt"],
    )
    turn.emit("error", event["data"])
    return event


# ── 阶段 1: Setup ─────────────────────────────────────────


def _setup_turn_runtime(
    turn: Turn,
) -> tuple[SkillRegistry, list[dict], SkillRegistry, verify.CallTracker, dict]:
    """加载 skills、构建 tools schema、初始化 tracker。"""
    memory_key = turn.memory_key or turn.conversation_id
    turn.memory_snapshot = memory.snapshot(memory_key)
    # 兼容旧调用方对 load_all 的注入，再在 Runtime 边界统一构建 Registry。
    registry = SkillRegistry.from_skills(skill_loader.load_all())
    tools_schema = registry.exposed_tools()
    # 注入 make_plan 工具，让 LLM 可以一次性规划多步任务
    tools_schema.append(planner.MAKE_PLAN_TOOL_SCHEMA)
    logger.info(
        "loaded %d skills: %s",
        len(registry.all()),
        [f"{s.name}({s.kind},{s.risk_level})" for s in registry.all()],
    )
    turn.messages = context.build_initial_messages(
        turn.user_input, turn.memory_snapshot
    )
    return registry, tools_schema, registry, verify.CallTracker(), {"plan": None}


async def _try_compress_context(turn: Turn) -> AsyncGenerator[dict, None]:
    """检查 token 用量，超阈值触发压缩。"""
    memory_key = turn.memory_key or turn.conversation_id
    usage = tokenizer.compute_usage(turn.messages)
    yield sse.context_usage(usage.used, usage.total, usage.percent, usage.level, step=0)
    if tokenizer.must_compress(usage):
        yield sse.context_compressing("hard", usage.percent)
        summary = await summarizer.maybe_summarize_async(memory_key, force=True)
        if summary:
            turn.memory_snapshot = memory.snapshot(memory_key)
            turn.messages = context.build_initial_messages(
                turn.user_input, turn.memory_snapshot
            )
            new_usage = tokenizer.compute_usage(turn.messages)
            yield sse.context_compressed(new_usage.percent, summary[:200])
    elif tokenizer.should_compress(usage):
        # soft 阈值：异步压缩，不阻塞当前 turn
        asyncio.create_task(summarizer.maybe_summarize_async(memory_key, force=False))


# ── 阶段 3: while 主循环单步 ──────────────────────────────


async def _run_single_reasoning_step(
    *,
    turn: Turn,
    tools_schema: list[dict],
    tracker: verify.CallTracker,
    plan_box: dict,
    skill_index: dict[str, Skill] | SkillRegistry,
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
) -> AsyncGenerator[dict, None]:
    """一次 while 迭代：doom 检测 → LLM → 工具分发。"""
    turn.set_phase(TurnPhase.REASONING)
    # ── Doom Loop 检测（参考 _example/tools/safety.py）──
    doom_msg = verify.detect_doom_loop(tracker.calls)
    if doom_msg:
        logger.warning("DOOM_LOOP: %s", doom_msg)
        async for ev in _emit_doom_loop_terminal(turn, doom_msg):
            yield ev
        return

    # ── 上下文使用情况（每步都报）──
    step_usage = tokenizer.compute_usage(turn.messages)
    yield sse.context_usage(
        step_usage.used,
        step_usage.total,
        step_usage.percent,
        step_usage.level,
        step=turn.step_count,
    )

    # ── System Reminder（对抗长会话指令衰减）──
    llm_messages = context.append_reminder(turn.messages, turn.step_count)

    # ── 流式 LLM 调用 ──
    try:
        llm_result: _LlmResult | None = None
        async for stream_item in _call_llm_stream(llm_messages, tools_schema):
            if isinstance(stream_item, _LlmResult):
                llm_result = stream_item
                continue
            turn.emit(stream_item["type"], stream_item["data"])
            yield stream_item
        if llm_result is None:
            raise RuntimeError("llm_stream_empty")
    except Exception as exc:  # noqa: BLE001
        async for ev in _handle_llm_error(turn, exc):
            yield ev
        return

    # ── 写入已提交但收尾轮仍请求工具 ──
    if turn.finalization_pending and llm_result.tool_calls:
        async for ev in _finalize_committed_with_fallback(
            turn, "写入已成功，但收尾模型仍请求调用工具；已阻止重复写入。"
        ):
            yield ev
        return

    # ── 有 tool_calls → 文本是思考过程 ──
    if llm_result.tool_calls and llm_result.full_content:
        ev = sse.thought(llm_result.full_content)
        turn.emit("thought", ev["data"])
        yield ev

    # ── 无 tool_calls → 流式输出最终回答 ──
    if not llm_result.tool_calls:
        async for ev in _emit_final_answer(
            turn, llm_result.full_content, plan_box["plan"], tracker
        ):
            yield ev
        return

    # ── 有 tool_calls → 走工具调用流程 ──
    assistant_msg = context.assistant_message_with_tool_calls(
        llm_result.full_content, llm_result.tool_calls
    )
    turn.messages.append(assistant_msg)

    async for ev in _dispatch_tool_calls(
        tool_calls=llm_result.tool_calls,
        rationale=llm_result.full_content,
        skill_index=skill_index,
        skill_ctx=skill_ctx,
        approval_waiter=approval_waiter,
        turn=turn,
        tracker=tracker,
        plan_box=plan_box,
    ):
        yield ev


async def _emit_final_answer(
    turn: Turn,
    content: str,
    plan,
    tracker: verify.CallTracker,
) -> AsyncGenerator[dict, None]:
    """无 tool_calls 时输出最终回答 + pre-completion checklist。"""
    turn.set_phase(TurnPhase.FINALIZING)
    issues = verify.pre_completion_checklist(plan, tracker)
    if issues:
        ev = sse.verification_warning(issues, step=turn.step_count)
        turn.emit("verification_warning", ev["data"])
        yield ev

    turn.final_answer = content
    if turn.committed_result is not None:
        trace_commit_state(turn.committed_result, reply_generated=True)
    turn.finalization_pending = False
    turn.status = "completed"
    turn.stop_reason = StopReason.MODEL_COMPLETED
    turn.set_phase(TurnPhase.TERMINAL)
    yield sse.final_answer_start()
    if content:
        yield sse.final_answer_delta(content)
    yield sse.final_answer(content)


# ── LLM 调用 ──────────────────────────────────────────────


async def _call_llm_stream(
    llm_messages: list[dict], tools_schema: list[dict]
) -> AsyncGenerator[dict | _LlmResult, None]:
    """流式 LLM 调用，同时转发增量和等待心跳。"""
    _llm_start = time.time()
    full_content = ""
    tool_calls: list[dict] = []

    stream = chat_stream(llm_messages, tools=tools_schema)
    next_token = asyncio.create_task(stream.__anext__())
    try:
        while True:
            done, _ = await asyncio.wait(
                {next_token}, timeout=HEARTBEAT_INTERVAL_SECONDS
            )
            if not done:
                yield sse.heartbeat("llm")
                continue
            try:
                token = next_token.result()
            except StopAsyncIteration:
                break
            next_token = asyncio.create_task(stream.__anext__())
            if token["type"] == "text":
                full_content += token["delta"]
                yield sse.assistant_delta(token["delta"])
            elif token["type"] == "tool_call":
                yield {
                    "type": "tool_call_delta",
                    "data": {
                        "tool_call_id": token.get("id", ""),
                        "name": token.get("name", ""),
                        "index": token.get("index", 0),
                        "arguments_delta": token.get("arguments_delta", ""),
                    },
                }
            elif token["type"] == "done":
                tool_calls = token.get("tool_calls", [])
            elif token["type"] == "retrying":
                yield {"type": "retrying", "data": token.get("data", {})}
            elif token["type"] == "error":
                payload = token.get("data") or {}
                classified = classify_exception(
                    RuntimeError(payload.get("message") or "llm_stream_failed")
                )
                raise LlmStreamError(
                    classified,
                    stream_started=bool(payload.get("stream_started")),
                    attempt=int(payload.get("attempt") or 0),
                )
    finally:
        if not next_token.done():
            next_token.cancel()

    _llm_ms = int((time.time() - _llm_start) * 1000)
    trace_llm_call(
        model=MODEL,
        messages=llm_messages,
        response={
            "content": full_content,
            "content_length": len(full_content),
            "finish_reason": "tool_calls" if tool_calls else "stop",
            "tool_calls_count": len(tool_calls),
            "tool_calls": [
                {
                    "id": call.get("id"),
                    "name": call.get("name"),
                    "arguments": call.get("arguments") or {},
                }
                for call in tool_calls
            ],
        },
        duration_ms=_llm_ms,
    )
    log_event(
        logger,
        logging.INFO,
        "llm_call",
        status="success",
        duration_ms=_llm_ms,
        data={"model": MODEL, "tool_calls": len(tool_calls)},
    )
    yield _LlmResult(full_content=full_content, tool_calls=tool_calls)


def _validate_tool_calls(turn: Turn, tool_calls: list[dict]) -> dict | None:
    """在任何调度前校验调用身份，避免结果无法与 assistant 消息关联。"""
    seen: set[str] = set()
    for call in tool_calls:
        reason = ""
        if not isinstance(call, dict):
            reason = "tool call 必须是对象"
        else:
            call_id = str(call.get("id") or "")
            if not call_id:
                reason = "tool call 缺少 tool_call_id"
            elif call_id in seen:
                reason = f"tool_call_id 重复：{call_id}"
            else:
                seen.add(call_id)
        if not reason:
            continue
        error_info = turn.record_error(
            "invalid_tool_call",
            reason,
            phase=TurnPhase.TOOL_PREPARING,
            stop_reason=StopReason.TOOL_FAILED,
        )
        event = sse.error_event(
            reason,
            error_info["code"],
            phase=error_info["phase"],
            retryable=error_info["retryable"],
            attempt=error_info["attempt"],
        )
        turn.emit("error", event["data"])
        return event
    return None


async def _handle_llm_error(turn: Turn, exc: Exception) -> AsyncGenerator[dict, None]:
    """LLM 调用失败时的错误处理：已提交→结构化降级，否则→failed。"""
    if turn.committed_result is not None:
        async for ev in _finalize_committed_with_fallback(
            turn, f"写入已成功，但最终答复生成失败：{exc}"
        ):
            yield ev
        return

    if isinstance(exc, LlmStreamError):
        classified = exc.classified
        code = "llm_stream_interrupted" if exc.stream_started else classified.code
        message = (
            "模型流式输出中断，已停止重试，请重新发送消息。"
            if exc.stream_started
            else classified.message
        )
        attempt = exc.attempt
    else:
        classified = classify_exception(exc)
        code = "llm_call_failed"
        message = str(exc)
        attempt = 0
    error_info = turn.record_error(
        code,
        message,
        phase=TurnPhase.REASONING,
        retryable=classified.retryable,
        attempt=attempt,
        category=classified.category.value,
        stop_reason=StopReason.LLM_FAILED,
    )
    ev = sse.error_event(
        error_info["message"],
        error_info["code"],
        phase=error_info["phase"],
        retryable=error_info["retryable"],
        attempt=error_info["attempt"],
        category=error_info.get("category", ""),
    )
    turn.emit("error", ev["data"])
    yield ev
    answer = _llm_failure_answer(
        classified.category.value,
        stream_started=isinstance(exc, LlmStreamError) and exc.stream_started,
    )
    turn.final_answer = answer
    yield sse.final_answer_start()
    yield sse.final_answer_delta(answer)
    yield sse.final_answer(answer)


def _llm_failure_answer(category: str, *, stream_started: bool) -> str:
    """将模型故障分类转换为用户可理解的终态答复。"""
    if stream_started:
        return "模型输出中断，本轮未完成，请重新发送消息。"
    return {
        "transient": "模型服务暂时不可用，本轮未完成，请稍后重试。",
        "resource": "本轮上下文或模型资源超出限制，请缩短请求后重试。",
        "permanent": "模型请求被拒绝，本轮未完成，请检查请求内容后重试。",
        "model": "模型未能生成有效结果，本轮未完成，请调整请求后重试。",
    }.get(category, "模型调用失败，本轮未完成，请稍后重试。")


# ── 工具分发 ──────────────────────────────────────────────


async def _dispatch_tool_calls(
    *,
    tool_calls: list[dict],
    rationale: str,
    skill_index: SkillLookup,
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    turn: Turn,
    tracker: verify.CallTracker,
    plan_box: dict,
) -> AsyncGenerator[dict, None]:
    """处理一轮 tool_calls：make_plan / 普通 skill / approval_followup。"""
    invalid_event = _validate_tool_calls(turn, tool_calls)
    if invalid_event is not None:
        yield invalid_event
        return

    if len(tool_calls) > 1 and not any(tc["name"] == "make_plan" for tc in tool_calls):
        parallel_calls = [
            tc
            for tc in tool_calls
            if (skill := skill_index.get(tc["name"])) is not None
            and skill.parallel_safe
        ]
        serial_calls = [tc for tc in tool_calls if tc not in parallel_calls]
    else:
        parallel_calls = []
        serial_calls = list(tool_calls)

    if parallel_calls:
        async for ev in _dispatch_parallel_tool_calls(
            tool_calls=parallel_calls,
            rationale=rationale,
            skill_index=skill_index,
            skill_ctx=skill_ctx,
            approval_waiter=approval_waiter,
            turn=turn,
            tracker=tracker,
            max_parallel_skills=settings.max_parallel_skills,
        ):
            yield ev
        if turn.finalization_request is not None:
            async for ev in _finalize_requested_error(turn):
                yield ev
            return

    for tc in serial_calls:
        tool_call_id = tc["id"]

        # make_plan 特殊工具：转入 planner 处理
        if tc["name"] == "make_plan":
            async for plan_ev, plan_obs in _handle_make_plan(
                tc["arguments"],
                rationale,
                skill_index,
                skill_ctx,
                approval_waiter,
                turn,
                tracker,
                plan_box,
            ):
                if plan_ev is not None:
                    yield plan_ev
                if plan_obs is not None:
                    turn.messages.append(
                        context.tool_result_message(tool_call_id, "make_plan", plan_obs)
                    )
                    return
            continue

        async for ev in _process_skill_call(
            tc=tc,
            rationale=rationale,
            skill_index=skill_index,
            skill_ctx=skill_ctx,
            approval_waiter=approval_waiter,
            turn=turn,
            tracker=tracker,
        ):
            yield ev

        # finalize / followup / doom / rejected 都会改变 turn 状态
        if turn.finalization_pending or turn.status != "running":
            return
        if turn.finalization_request is not None:
            async for ev in _finalize_requested_error(turn):
                yield ev
            return

    _reorder_parallel_tool_messages(turn, tool_calls)


async def _dispatch_parallel_tool_calls(
    *,
    tool_calls: list[dict],
    rationale: str,
    skill_index: SkillLookup,
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    turn: Turn,
    tracker: verify.CallTracker,
    max_parallel_skills: int,
) -> AsyncGenerator[dict, None]:
    """并行执行同一轮中相互独立的只读 Skill。

    每个调用仍复用完整的校验、trace 和 observation 流程。事件按完成顺序
    推送，Tool 结果消息在批次结束时按原始 tool_call_id 顺序整理；写操作和
    Plan 不会进入这个分支。
    """
    queue: asyncio.Queue[tuple[int, dict | None]] = asyncio.Queue()
    semaphore = asyncio.Semaphore(max(1, max_parallel_skills))
    skill_semaphores: dict[str, asyncio.Semaphore] = {}
    for tool_call in tool_calls:
        skill = skill_index.get(tool_call["name"])
        if skill is not None:
            skill_semaphores.setdefault(
                skill.name,
                asyncio.Semaphore(min(max_parallel_skills, skill.max_concurrency)),
            )
    active = 0
    max_inflight = 0
    active_lock = asyncio.Lock()

    async def collect(index: int, tool_call: dict) -> None:
        nonlocal active, max_inflight
        try:
            async with semaphore:
                skill_semaphore = skill_semaphores.get(tool_call["name"])
                if skill_semaphore is None:
                    async with active_lock:
                        active += 1
                        max_inflight = max(max_inflight, active)
                    try:
                        async for event in _process_skill_call(
                            tc=tool_call,
                            rationale=rationale,
                            skill_index=skill_index,
                            skill_ctx=skill_ctx,
                            approval_waiter=approval_waiter,
                            turn=turn,
                            tracker=tracker,
                        ):
                            await queue.put((index, event))
                    finally:
                        async with active_lock:
                            active -= 1
                else:
                    async with skill_semaphore:
                        async with active_lock:
                            active += 1
                            max_inflight = max(max_inflight, active)
                        try:
                            async for event in _process_skill_call(
                                tc=tool_call,
                                rationale=rationale,
                                skill_index=skill_index,
                                skill_ctx=skill_ctx,
                                approval_waiter=approval_waiter,
                                turn=turn,
                                tracker=tracker,
                            ):
                                await queue.put((index, event))
                        finally:
                            async with active_lock:
                                active -= 1
        finally:
            await queue.put((index, None))

    tasks = [
        asyncio.create_task(collect(index, tool_call))
        for index, tool_call in enumerate(tool_calls)
    ]
    completed = 0
    batch_events: list[dict] = []
    try:
        while completed < len(tasks):
            _, event = await queue.get()
            if event is None:
                completed += 1
                continue
            batch_events.append(event)
            yield event
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        _reorder_parallel_tool_messages(turn, tool_calls)
        log_event(
            logger,
            logging.INFO,
            "parallel_tool_batch",
            status="completed",
            data={
                "parallel_batch_size": len(tool_calls),
                "parallel_inflight_max": max_inflight,
                "tool_failure_count": sum(
                    event["type"] == "observation" and bool(event["data"].get("error"))
                    for event in batch_events
                ),
                "event_sequence": [event["type"] for event in batch_events],
                "tool_durations_ms": [
                    event["data"]["duration_ms"]
                    for event in batch_events
                    if event["type"] == "tool_finished"
                ],
            },
        )


def _reorder_parallel_tool_messages(turn: Turn, tool_calls: list[dict]) -> None:
    """按 assistant 原始 Tool Call 顺序写回并行结果消息。"""
    order = {call["id"]: index for index, call in enumerate(tool_calls)}
    indexed = [
        (index, message)
        for index, message in enumerate(turn.messages)
        if message.get("role") == "tool" and message.get("tool_call_id") in order
    ]
    if len(indexed) != len(tool_calls):
        return
    positions = [index for index, _ in indexed]
    messages = [
        message
        for _, message in sorted(
            indexed, key=lambda item: order[item[1]["tool_call_id"]]
        )
    ]
    for position, message in zip(positions, messages):
        turn.messages[position] = message


async def _process_skill_call(
    *,
    tc: dict,
    rationale: str,
    skill_index: SkillLookup,
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    turn: Turn,
    tracker: verify.CallTracker,
) -> AsyncGenerator[dict, None]:
    """单个 skill tool_call 完整处理：校验→审批→执行→后处理。终止分支通过 turn 状态通知外层。"""
    turn.set_phase(TurnPhase.TOOL_PREPARING)
    tool_name = tc["name"]
    args = tc["arguments"]
    tool_call_id = tc["id"]

    skill = skill_index.get(tool_name)
    if skill is None:
        async for ev in _emit_unknown_tool(turn, tool_call_id, tool_name):
            yield ev
        return

    if not skill.exposed:
        async for ev in _emit_not_exposed_tool(turn, tool_call_id, tool_name, args):
            yield ev
        return

    # 参数校验：enrich + missing + dup
    prepared = _PreparedCall(args=args)
    async for ev in _prepare_skill_call(tc, skill, skill_ctx, turn, tracker, prepared):
        yield ev
    if not prepared.proceed:
        return
    args = prepared.args

    async for ev in _apply_approval_gate(
        turn=turn,
        skill=skill,
        args=args,
        rationale=rationale,
        approval_waiter=approval_waiter,
        tool_call_id=tool_call_id,
    ):
        yield ev

    rejected_answer = _rejected_final_answer(turn)
    if rejected_answer is not None:
        turn.final_answer = rejected_answer
        yield sse.final_answer(rejected_answer)
        return

    state = _SkillExecState()
    async for ev in _run_skill_call(
        turn=turn,
        skill=skill,
        args=args,
        skill_ctx=skill_ctx,
        rationale=rationale,
        state=state,
        tool_call_id=tool_call_id,
    ):
        yield ev

    async for ev in _post_process_skill_result(
        tc=tc,
        turn=turn,
        skill=skill,
        tracker=tracker,
        state=state,
        skill_index=skill_index,
        skill_ctx=skill_ctx,
        approval_waiter=approval_waiter,
        rationale=rationale,
    ):
        yield ev


async def _post_process_skill_result(
    *,
    tc: dict,
    turn: Turn,
    skill: Skill,
    tracker: verify.CallTracker,
    state: _SkillExecState,
    skill_index: SkillLookup,
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    rationale: str,
) -> AsyncGenerator[dict, None]:
    """后处理：append tool_msg → finalize/followup。"""
    turn.messages.append(
        context.tool_result_message(tc["id"], tc["name"], state.result)
    )
    tracker.record_observation(skill.name, tc["arguments"], state.result)
    if state.error:
        result = state.result if isinstance(state.result, dict) else {}
        if not bool(result.get("retryable", False)):
            turn.finalization_request = {
                "code": str(result.get("code") or "tool_failed"),
                "message": state.error,
                "tool_name": skill.name,
                "result": result,
            }
        return
    if state.finalize_after_success:
        _mark_committed(turn, state.result)
        committed_event = sse.operation_committed(turn.committed_result)
        turn.emit(committed_event["type"], committed_event["data"])
        yield committed_event
        return
    async for ev in _drive_followup_if_ready(
        skill=skill,
        state=state,
        skill_index=skill_index,
        skill_ctx=skill_ctx,
        approval_waiter=approval_waiter,
        turn=turn,
        rationale=rationale,
    ):
        yield ev


async def _prepare_skill_call(
    tc: dict,
    skill: Skill,
    skill_ctx: SkillContext,
    turn: Turn,
    tracker: verify.CallTracker,
    prepared: _PreparedCall,
) -> AsyncGenerator[dict, None]:
    """参数 enrich + missing + dup 校验。失败时设 prepared.proceed=False。"""
    args = tc["arguments"]
    enriched = skill.enrich_params(args, skill_ctx)
    if enriched != args:
        logger.info("skill %s params enriched: %s → %s", skill.name, args, enriched)
        args = enriched
        tc["arguments"] = enriched  # 回写，确保 action 事件显示真实参数
    prepared.args = args

    tracker.record(skill.name, args)
    missing = skill.missing_required_params(args)
    if missing:
        async for ev in _emit_missing_params(
            turn, skill, tc["id"], skill.name, args, missing
        ):
            yield ev
        prepared.proceed = False
        return

    async for ev in _check_duplication(turn, tracker, skill.name, args):
        yield ev
    if turn.status != "running":
        prepared.proceed = False


async def _drive_followup_if_ready(
    *,
    skill: Skill,
    state: _SkillExecState,
    skill_index: SkillLookup,
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    turn: Turn,
    rationale: str,
) -> AsyncGenerator[dict, None]:
    """prepare 返回 ready 时，Runtime 自动驱动审批 + commit 后继。"""
    followup = skill.approval_followup
    if (
        not followup
        or not isinstance(state.result, dict)
        or state.result.get("status") != "ready"
    ):
        return
    async for ev in _drive_approval_followup(
        prepare_result=state.result,
        followup_config=followup,
        skill_index=skill_index,
        skill_ctx=skill_ctx,
        approval_waiter=approval_waiter,
        turn=turn,
        rationale=rationale,
    ):
        yield ev


def _rejected_final_answer(turn: Turn) -> str | None:
    """若 turn 被拒绝，返回最终答复文本；否则返回 None。"""
    if turn.status != "rejected":
        return None
    reason = turn.rejected_reason or ""
    if not reason or reason == "user rejected":
        reason = "用户拒绝执行"
    return f"已取消该操作：{reason}"


def _mark_committed(turn: Turn, result: dict | None) -> None:
    """标记 turn 已提交：写 committed_result + finalization_pending + trace。"""
    committed = result if isinstance(result, dict) else {"result": result}
    turn.committed_result = committed
    turn.finalization_pending = True
    trace_commit_state(committed, reply_generated=False)


async def _emit_unknown_tool(
    turn: Turn, tool_call_id: str, tool_name: str
) -> AsyncGenerator[dict, None]:
    """未知工具错误：发 observation + 写 tool_msg。"""
    err_msg = f"未知工具: {tool_name}"
    result = {"error": err_msg}
    ev = sse.observation(
        tool_name,
        None,
        error=err_msg,
        error_info={
            "code": "unknown_tool",
            "message": err_msg,
            "phase": TurnPhase.TOOL_PREPARING.value,
            "tool_name": tool_name,
            "retryable": False,
            "attempt": 0,
        },
    )
    turn.emit("observation", ev["data"])
    yield ev
    turn.messages.append(context.tool_result_message(tool_call_id, tool_name, result))


async def _emit_not_exposed_tool(
    turn: Turn, tool_call_id: str, tool_name: str, args: dict
) -> AsyncGenerator[dict, None]:
    """阻止模型直接调用内部后继动作（如 commit_planting_plan）。"""
    err_msg = f"工具 {tool_name} 不可直接调用，需先准备计划并通过审批控件确认"
    result = {
        "error": "tool_not_exposed",
        "code": "tool_not_exposed",
        "message": err_msg,
    }
    trace_tool_call(tool_name, args, result, error=err_msg)
    ev = sse.observation(
        tool_name,
        None,
        error=err_msg,
        error_info={
            "code": "tool_not_exposed",
            "message": err_msg,
            "phase": TurnPhase.TOOL_PREPARING.value,
            "tool_name": tool_name,
            "retryable": False,
            "attempt": 0,
        },
    )
    turn.emit("observation", ev["data"])
    yield ev
    turn.messages.append(context.tool_result_message(tool_call_id, tool_name, result))


async def _emit_missing_params(
    turn: Turn,
    skill: Skill,
    tool_call_id: str,
    tool_name: str,
    args: dict,
    missing: list[str],
) -> AsyncGenerator[dict, None]:
    """缺失必填参数：发 observation + 写 tool_msg。"""
    result = _missing_params_result(skill, missing)
    message = result["message"]
    trace_tool_call(tool_name, args, result, error=message)
    ev = sse.observation(
        tool_name,
        None,
        error=message,
        error_info={
            "code": str(result.get("code") or "missing_required_params"),
            "message": message,
            "phase": TurnPhase.TOOL_PREPARING.value,
            "tool_name": tool_name,
            "retryable": False,
            "attempt": 0,
        },
    )
    turn.emit("observation", ev["data"])
    yield ev
    turn.messages.append(context.tool_result_message(tool_call_id, tool_name, result))
    # 缺参是确定性的用户澄清分支，不能再把内部结果交回模型反复选工具。
    turn.finalization_request = {
        "code": str(result.get("error") or "missing_required_params"),
        "message": message,
        "answer": skill.missing_params_prompt(missing),
        "tool_name": tool_name,
        "result": result,
    }


async def _check_duplication(
    turn: Turn,
    tracker: verify.CallTracker,
    tool_name: str,
    args: dict,
) -> AsyncGenerator[dict, None]:
    """重复调用 warning；doom loop 时设置 turn.status=completed 终止。"""
    dup_warn = verify.check_duplication(tracker, tool_name, args)
    if not dup_warn:
        return
    ev = sse.verification_warning([dup_warn], step=turn.step_count)
    turn.emit("verification_warning", ev["data"])
    yield ev

    # doom loop 强制终止：同一 (skill, args) 重复 >= 3 次
    doom = verify.detect_doom_loop(tracker.calls)
    if doom:
        message = (
            f"⚠️ 已终止：{doom}\n\n"
            "相同查询没有产生新的结果，已停止继续调用工具。"
            "如需继续，请补充筛选条件或明确下一步业务动作。"
        )
        async for ev in _emit_doom_loop_terminal(turn, message):
            yield ev


async def _emit_doom_loop_terminal(
    turn: Turn, detail: str
) -> AsyncGenerator[dict, None]:
    """发布 Doom 警告，再交给统一失败终止器收口。"""
    warning_ev = sse.doom_loop_warning(detail, step=turn.step_count)
    turn.emit("doom_loop_warning", warning_ev["data"])
    yield warning_ev
    async for ev in _emit_failure_terminal(
        turn,
        code="doom_loop_detected",
        message="检测到重复工具调用，已停止本轮执行。",
        answer=detail,
        phase=TurnPhase.REASONING,
        stop_reason=StopReason.DOOM_LOOP_DETECTED,
    ):
        yield ev


async def _finalize_requested_error(
    turn: Turn,
) -> AsyncGenerator[dict, None]:
    """收口批次中记录的不可重试错误，避免错误继续消耗 ReAct 步数。"""
    request = turn.finalization_request or {}
    code = str(request.get("code") or "tool_failed")
    message = str(request.get("message") or "工具执行失败")
    tool_name = str(request.get("tool_name") or "")
    answer = str(request.get("answer") or "")
    if not answer:
        answer = (
            f"调用 {tool_name or '业务工具'} 未完成：{message}。"
            "该错误不可重试，已停止继续调用工具，请补充信息后重试。"
        )
    async for ev in _emit_failure_terminal(
        turn,
        code=code,
        message=message,
        answer=answer,
        phase=TurnPhase.FINALIZING,
        tool_name=tool_name,
        stop_reason=StopReason.TOOL_FAILED,
    ):
        yield ev


async def _emit_failure_terminal(
    turn: Turn,
    *,
    code: str,
    message: str,
    answer: str,
    phase: TurnPhase,
    stop_reason: StopReason,
    tool_name: str = "",
) -> AsyncGenerator[dict, None]:
    """统一发出失败终态，保证 error、final_answer 和 done 链路一致。"""
    error_info = turn.record_error(
        code,
        message,
        phase=phase,
        tool_name=tool_name,
        stop_reason=stop_reason,
    )
    error_ev = sse.error_event(
        message,
        code,
        phase=error_info["phase"],
        tool_name=tool_name,
        retryable=False,
        attempt=0,
    )
    turn.emit("error", error_ev["data"])
    yield error_ev
    turn.final_answer = answer
    turn.finalization_request = None
    turn.set_phase(TurnPhase.TERMINAL)
    yield sse.final_answer_start()
    yield sse.final_answer_delta(answer)
    yield sse.final_answer(answer)


# ── HITL 审批闸门（P5）────────────────────────────────────


async def _apply_approval_gate(
    *,
    turn: Turn,
    skill: Skill,
    args: dict,
    rationale: str,
    approval_waiter: ApprovalWaiter,
    tool_call_id: str,
    approval_extras: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """HITL 审批：approval_required → 等待 → approval_result。

    不需要审批时直接返回；被拒绝时设置 turn.status=rejected，由调用方处理。
    approval_extras 透传给 sse.approval_required（如 summary/plan）。
    """
    risk = skill.dynamic_risk_level(args)
    logger.info(
        "skill %s risk_level=%s (meta=%s)",
        skill.name,
        risk,
        getattr(skill, "_meta", {}).get("risk_level"),
    )
    if not hitl.needs_approval(risk):
        return

    turn.set_phase(TurnPhase.AWAITING_APPROVAL)
    turn = hitl.gate(
        turn,
        tool_name=skill.name,
        tool_description=skill.description,
        arguments=args,
        tool_call_id=tool_call_id,
        rationale=rationale,
        risk=risk,
    )

    extra_kwargs = approval_extras or {}
    ev = sse.approval_required(
        tool_name=skill.name,
        arguments=args,
        rationale=rationale,
        risk_level=risk,
        turn_id=turn.turn_id,
        **extra_kwargs,
    )
    turn.emit("approval_required", ev["data"])
    yield ev

    decision, reason = await approval_waiter(turn.turn_id)
    if reason == "approval_expired":
        turn.record_error(
            "approval_expired",
            "审批已过期",
            phase=TurnPhase.AWAITING_APPROVAL,
            stop_reason=StopReason.APPROVAL_EXPIRED,
            status="timeout",
        )
    elif reason == "turn_cancelled":
        turn.record_error(
            "turn_cancelled",
            "本轮任务已取消",
            phase=TurnPhase.AWAITING_APPROVAL,
            stop_reason=StopReason.USER_CANCELLED,
            status="cancelled",
        )
    else:
        turn = hitl.approve(turn, decision, reason)
        if decision:
            turn.set_phase(TurnPhase.TOOL_PREPARING)
        else:
            turn.record_error(
                "approval_rejected",
                reason or "用户拒绝执行该操作",
                phase=TurnPhase.AWAITING_APPROVAL,
                stop_reason=StopReason.APPROVAL_REJECTED,
                status="rejected",
            )

    decision_name = (
        "expired"
        if reason == "approval_expired"
        else "cancelled"
        if reason == "turn_cancelled"
        else "approved"
        if decision
        else "rejected"
    )
    ev = sse.approval_result(decision_name, reason)
    turn.emit("approval_result", ev["data"])
    yield ev


# ── Skill 执行（统一）────────────────────────────────────


async def _run_skill_call(
    *,
    turn: Turn,
    skill: Skill,
    args: dict,
    skill_ctx: SkillContext,
    rationale: str,
    state: _SkillExecState,
    tool_call_id: str = "",
) -> AsyncGenerator[dict, None]:
    """执行 skill：action → skill.execute() → observation。填充 state。

    被三处调用方复用：主循环 _dispatch_tool_calls、_drive_approval_followup、
    _execute_plan_step，避免 HITL/trace/事件逻辑出现三份不同实现。
    """
    turn.set_phase(TurnPhase.TOOL_EXECUTING)
    ev = sse.action(skill.name, args, rationale=rationale)
    # 先 emit 占位事件，skill 可能兜底替换参数后回写
    turn.emit("action", ev["data"])
    yield ev
    started_ev = sse.tool_started(
        turn.turn_id, tool_call_id, skill.name, turn.step_count, args
    )
    turn.emit("tool_started", started_ev["data"])
    yield started_ev

    _tool_start = time.time()
    try:
        execution_task = asyncio.create_task(skill.execute(args, skill_ctx))
        while True:
            done, _ = await asyncio.wait(
                {execution_task}, timeout=HEARTBEAT_INTERVAL_SECONDS
            )
            if done:
                result_obj = execution_task.result()
                break
            heartbeat_ev = sse.heartbeat(f"skill:{skill.name}", turn.step_count)
            turn.emit("heartbeat", heartbeat_ev["data"])
            yield heartbeat_ev
        _tool_ms = int((time.time() - _tool_start) * 1000)
        # skill 兜底可能回写了 action 事件的 arguments
        action_data = _find_latest_action_data(turn, skill.name) or ev["data"]
        if action_data != ev["data"]:
            yield sse.action(
                action_data["tool_name"],
                action_data.get("arguments", args),
                rationale=action_data.get("rationale", ""),
            )
        state.result_obj = result_obj
        if result_obj.error:
            state.result = result_obj.data or {"error": result_obj.error}
            state.error = result_obj.error
            result_data = state.result if isinstance(state.result, dict) else {}
            retryable = bool(result_data.get("retryable", False))
            error_info = {
                "code": str(result_data.get("code") or "tool_failed"),
                "message": result_obj.error,
                "phase": TurnPhase.TOOL_EXECUTING.value,
                "tool_name": skill.name,
                "category": str(
                    result_data.get(
                        "category", "transient" if retryable else "permanent"
                    )
                ),
                "retryable": retryable,
                "attempt": int(result_data.get("attempt") or 0),
            }
            obs_ev = sse.observation(
                skill.name,
                None,
                error=result_obj.error,
                error_info=error_info,
            )
            trace_tool_call(
                skill.name, args, None, duration_ms=_tool_ms, error=result_obj.error
            )
            finished_ev = sse.tool_finished(
                turn.turn_id,
                tool_call_id,
                skill.name,
                turn.step_count,
                _tool_ms,
                error=error_info,
            )
        else:
            state.result = result_obj.data
            state.finalize_after_success = skill.finalize_after_success
            obs_ev = sse.observation(skill.name, state.result)
            trace_tool_call(skill.name, args, state.result, duration_ms=_tool_ms)
            finished_ev = sse.tool_finished(
                turn.turn_id,
                tool_call_id,
                skill.name,
                turn.step_count,
                _tool_ms,
                result=state.result,
            )
        turn.emit("tool_finished", finished_ev["data"])
        yield finished_ev
        turn.emit("observation", obs_ev["data"])
        yield obs_ev
    except Exception as exc:
        logger.exception("skill execution failed: %s", skill.name)
        if isinstance(exc, McpCallError):
            classified = exc.classified
            error_code = f"mcp_{classified.code}"
            error_attempt = exc.attempt
            error_category = classified.category.value
            retryable = classified.retryable
        else:
            classified = classify_exception(exc)
            error_code = "tool_execution_failed"
            error_attempt = 0
            error_category = classified.category.value
            retryable = False
        state.result = {
            "error": str(exc),
            "code": error_code,
            "category": error_category,
            "retryable": retryable,
            "attempt": error_attempt,
        }
        state.error = str(exc)
        error_info = {
            "code": error_code,
            "message": str(exc),
            "phase": TurnPhase.TOOL_EXECUTING.value,
            "tool_name": skill.name,
            "category": error_category,
            "retryable": retryable,
            "attempt": error_attempt,
        }
        obs_ev = sse.observation(
            skill.name,
            None,
            error=str(exc),
            error_info=error_info,
        )
        duration_ms = int((time.time() - _tool_start) * 1000)
        finished_ev = sse.tool_finished(
            turn.turn_id,
            tool_call_id,
            skill.name,
            turn.step_count,
            duration_ms,
            error=error_info,
        )
        turn.emit("tool_finished", finished_ev["data"])
        yield finished_ev
        turn.emit("observation", obs_ev["data"])
        yield obs_ev
        trace_tool_call(skill.name, args, None, error=str(exc))


# ── prepare → commit 审批后继 ─────────────────────────────


async def _drive_approval_followup(
    *,
    prepare_result: dict,
    followup_config: dict,
    skill_index: SkillLookup,
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    turn: Turn,
    rationale: str,
) -> AsyncGenerator[dict, None]:
    """prepare 返回 ready 后驱动审批 + commit。约束（spec §7.1-7.4）：参数不可变、缺字段即终止、错误即收敛。"""
    followup_tool_name = followup_config.get("tool_name") or ""
    field_names = followup_config.get("arguments_from_result") or []

    # 1. 从 prepare 结果提取 commit 参数（不可变）
    followup_args, missing_fields = _extract_followup_args(prepare_result, field_names)
    if missing_fields:
        async for ev in _emit_prepare_incomplete(
            turn, followup_tool_name, missing_fields
        ):
            yield ev
        return

    followup_skill = skill_index.get(followup_tool_name)
    if followup_skill is None:
        async for ev in _emit_followup_skill_missing(turn, followup_tool_name):
            yield ev
        return

    approval_summary = prepare_result.get("approval_summary") or rationale

    # 2. HITL 审批（附加 summary + plan 给前端展示，复用统一闸门）
    async for ev in _apply_approval_gate(
        turn=turn,
        skill=followup_skill,
        args=followup_args,
        rationale=approval_summary,
        approval_waiter=approval_waiter,
        tool_call_id=f"followup-{followup_tool_name}",
        approval_extras={
            "summary": prepare_result.get("approval_summary") or "",
            "plan": prepare_result.get("plan"),
        },
    ):
        yield ev

    rejected_answer = _rejected_final_answer(turn)
    if rejected_answer is not None:
        turn.final_answer = rejected_answer
        yield sse.final_answer(rejected_answer)
        return

    # 3. 执行 commit（使用 prepare 原始参数，禁止模型改写）
    state = _SkillExecState()
    async for ev in _run_skill_call(
        turn=turn,
        skill=followup_skill,
        args=followup_args,
        skill_ctx=skill_ctx,
        rationale=approval_summary,
        state=state,
        tool_call_id=f"followup-{followup_tool_name}",
    ):
        yield ev

    # 4. commit 结果喂回 messages，供收尾 LLM 生成最终答复
    _append_followup_messages(turn, followup_tool_name, followup_args, state.result)

    # 5. 业务错误立即收敛：不再喂给 LLM 选其他工具
    if state.error:
        async for ev in _converge_followup_error(turn, state):
            yield ev
        return

    # 6. 成功 → operation_committed + 进入无工具确定性收尾
    async for ev in _finalize_followup_success(turn, state.result):
        yield ev


async def _emit_followup_skill_missing(
    turn: Turn, followup_tool_name: str
) -> AsyncGenerator[dict, None]:
    """审批后继动作未注册时发出错误并终止 turn。"""
    message = f"审批后继动作 {followup_tool_name} 未注册"
    ev = sse.observation(
        followup_tool_name,
        None,
        error=message,
        error_info={
            "code": "followup_skill_missing",
            "message": message,
            "phase": TurnPhase.TOOL_PREPARING.value,
            "tool_name": followup_tool_name,
            "retryable": False,
            "attempt": 0,
        },
    )
    turn.emit("observation", ev["data"])
    yield ev
    error_info = turn.record_error(
        "followup_skill_missing",
        message,
        phase=TurnPhase.TOOL_PREPARING,
        tool_name=followup_tool_name,
        stop_reason=StopReason.TOOL_FAILED,
    )
    err_ev = sse.error_event(
        message,
        error_info["code"],
        phase=error_info["phase"],
        tool_name=error_info["tool_name"],
        retryable=error_info["retryable"],
        attempt=error_info["attempt"],
    )
    turn.emit("error", err_ev["data"])
    yield err_ev


async def _converge_followup_error(
    turn: Turn, state: _SkillExecState
) -> AsyncGenerator[dict, None]:
    """commit 业务错误立即收敛：不喂给 LLM 选其他工具。"""
    code = (
        state.result.get("code") if isinstance(state.result, dict) else None
    ) or "commit_failed"
    error_info = turn.record_error(
        code,
        state.error or "业务操作失败",
        phase=TurnPhase.TOOL_EXECUTING,
        stop_reason=StopReason.TOOL_FAILED,
    )
    err_ev = sse.error_event(
        error_info["message"],
        error_info["code"],
        phase=error_info["phase"],
        retryable=error_info["retryable"],
        attempt=error_info["attempt"],
    )
    turn.emit("error", err_ev["data"])
    yield err_ev


async def _finalize_followup_success(
    turn: Turn, result: dict
) -> AsyncGenerator[dict, None]:
    """commit 成功 → operation_committed + 进入无工具确定性收尾。"""
    committed = result if isinstance(result, dict) else {"result": result}
    turn.committed_result = committed
    turn.finalization_pending = True
    trace_commit_state(committed, reply_generated=False)
    committed_event = sse.operation_committed(committed)
    turn.emit(committed_event["type"], committed_event["data"])
    yield committed_event


def _extract_followup_args(
    prepare_result: dict, field_names: list[str]
) -> tuple[dict, list[str]]:
    """从 prepare 结果提取 commit 参数（不可变）。"""
    followup_args: dict = {}
    missing_fields: list[str] = []
    for name in field_names:
        if name in prepare_result and prepare_result[name] is not None:
            followup_args[name] = prepare_result[name]
        else:
            missing_fields.append(name)
    return followup_args, missing_fields


async def _emit_prepare_incomplete(
    turn: Turn, followup_tool_name: str, missing_fields: list[str]
) -> AsyncGenerator[dict, None]:
    """prepare 结果缺字段时发出错误并终止 turn。"""
    message = f"准备结果缺少提交所需字段：{missing_fields}"
    result = {
        "status": "failed",
        "error": "prepare_result_incomplete",
        "code": "prepare_result_incomplete",
        "missing": missing_fields,
        "message": message,
    }
    trace_tool_call(followup_tool_name, {}, result, error="prepare_result_incomplete")
    ev = sse.observation(
        followup_tool_name,
        None,
        error=message,
        error_info={
            "code": "prepare_result_incomplete",
            "message": message,
            "phase": TurnPhase.TOOL_PREPARING.value,
            "tool_name": followup_tool_name,
            "retryable": False,
            "attempt": 0,
        },
    )
    turn.emit("observation", ev["data"])
    yield ev
    error_info = turn.record_error(
        "prepare_result_incomplete",
        message,
        phase=TurnPhase.TOOL_PREPARING,
        tool_name=followup_tool_name,
        stop_reason=StopReason.TOOL_FAILED,
    )
    err_ev = sse.error_event(
        message,
        error_info["code"],
        phase=error_info["phase"],
        tool_name=error_info["tool_name"],
        retryable=error_info["retryable"],
        attempt=error_info["attempt"],
    )
    turn.emit("error", err_ev["data"])
    yield err_ev


# ── make_plan 处理 ────────────────────────────────────────


async def _handle_make_plan(
    args: dict,
    rationale: str,
    skill_index: SkillLookup,
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    turn: Turn,
    tracker: verify.CallTracker,
    current_plan_box: dict,
) -> AsyncGenerator[tuple[dict | None, str | None], None]:
    """处理 make_plan 工具调用。

    async generator：yield (sse_event_or_None, observation_str_or_None)。
    observation 非 None 时表示 plan 执行完毕（成功或失败），外层应停止遍历。

    参考 _example/core/planner.py:execute_plan。
    """
    plan = planner.parse_plan(args, turn.user_input, skill_index)
    if plan is None:
        yield (
            None,
            "make_plan 失败：未产出 ≥2 个有效步骤。请改用单步 skill 调用，或 final_answer 询问。",
        )
        return

    # 保存到 box，让外层 final_answer 前的 checklist 能用
    current_plan_box["plan"] = plan

    # 发 plan_created 事件
    plan_event_data = planner.plan_to_event_data(plan)
    ev = sse.plan_created(plan.goal, plan_event_data["steps"])
    turn.emit("plan_created", ev["data"])
    yield (ev, None)

    # 计划步骤也要走同一套 operation 兜底，否则单步和计划的行为会分叉。
    for step in plan.steps:
        skill = skill_index.get(step.skill)
        if skill is not None:
            step.args = skill.enrich_params(step.args, skill_ctx)

    # 校验 plan 参数
    issues = planner.validate_plan(plan, skill_index)
    if issues:
        yield (None, f"plan 参数校验失败：{issues}。请 final_answer 询问用户补全。")
        return

    # 按顺序执行每个 step
    async for step_ev, step_obs, interrupted in _execute_plan_steps(
        plan, rationale, skill_index, skill_ctx, approval_waiter, turn, tracker
    ):
        if step_ev is not None:
            yield (step_ev, None)
        if interrupted:
            yield (None, step_obs)
            return

    # plan 完成，给 LLM 一个总结性 observation
    summary = planner.plan_summary_for_observation(plan)
    yield (None, summary)


async def _execute_plan_steps(
    plan,
    rationale: str,
    skill_index: SkillLookup,
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    turn: Turn,
    tracker: verify.CallTracker,
) -> AsyncGenerator[tuple[dict | None, str | None, bool], None]:
    """按顺序执行 plan 的每个 step。

    yields (step_event, step_obs, interrupted):
    - step_event: 子步骤事件或 plan_step_done 事件
    - step_obs: 步骤观察字符串（仅 interrupted=True 时有意义）
    - interrupted: 用户拒绝审批时为 True
    """
    for step_idx, step in enumerate(plan.steps):
        step.status = "running"
        step_obs: str | None = None
        async for sub_event, obs in _execute_plan_step(
            step.skill,
            step.args,
            rationale,
            skill_index,
            skill_ctx,
            approval_waiter,
            turn,
            tracker,
        ):
            if sub_event is not None:
                yield (sub_event, None, False)
            if obs is not None:
                step_obs = obs
                break

        if step_obs is None:
            step_obs = f"步骤 {step_idx + 1} 未产出观察"
            step.status = "failed"
            step.error = "no observation"
        else:
            step.status = "done"
        step.result = step_obs

        step_ev = sse.plan_step_done(step_idx, step.skill, step.status, step.result)
        turn.emit("plan_step_done", step_ev["data"])
        yield (step_ev, step_obs, False)

        if turn.status == "rejected":
            yield (None, f"plan 中断：{step_obs}", True)
            return


async def _execute_plan_step(
    tool_name: str,
    args: dict,
    rationale: str,
    skill_index: SkillLookup,
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    turn: Turn,
    tracker: verify.CallTracker,
) -> AsyncGenerator[tuple[dict | None, str | None], None]:
    """执行单个 skill 调用（plan 内部每步都走这个）。

    复用 _apply_approval_gate + _run_skill_call，与主循环保持一致。
    async generator：yield (sse_event_or_None, observation_str_or_None)。
    """
    skill = skill_index.get(tool_name)
    if skill is None:
        err_msg = f"未知工具: {tool_name}"
        ev = sse.observation(tool_name, None, error=err_msg)
        turn.emit("observation", ev["data"])
        yield (ev, err_msg)
        return

    enriched = skill.enrich_params(args, skill_ctx)
    if enriched != args:
        args = enriched

    tracker.record(tool_name, args)
    missing = skill.missing_required_params(args)
    if missing:
        result = _missing_params_result(skill, missing)
        message = result["message"]
        ev = sse.observation(tool_name, None, error=message)
        turn.emit("observation", ev["data"])
        yield (ev, message)
        return

    # CallTracker 记录
    dup_warn = verify.check_duplication(tracker, tool_name, args)
    if dup_warn:
        ev = sse.verification_warning([dup_warn], step=turn.step_count)
        turn.emit("verification_warning", ev["data"])
        yield (ev, None)

    # HITL（复用统一闸门）
    async for ev in _apply_approval_gate(
        turn=turn,
        skill=skill,
        args=args,
        rationale=rationale,
        approval_waiter=approval_waiter,
        tool_call_id=f"plan-{tool_name}",
    ):
        yield (ev, None)

    if turn.status == "rejected":
        obs = f"用户拒绝执行 {tool_name}：{turn.rejected_reason or '用户拒绝'}"
        yield (None, obs)
        return

    # 执行（复用统一 skill 执行器）
    state = _SkillExecState()
    async for ev in _run_skill_call(
        turn=turn,
        skill=skill,
        args=args,
        skill_ctx=skill_ctx,
        rationale=rationale,
        state=state,
        tool_call_id=f"plan-{tool_name}",
    ):
        yield (ev, None)

    # 给 LLM 的 observation 字符串
    yield (None, _build_skill_obs_str(tool_name, args, state))


def _build_skill_obs_str(tool_name: str, args: dict, state: _SkillExecState) -> str:
    """构造给 plan LLM 的 observation 字符串。"""
    if state.error:
        return f"调用 {tool_name} 失败：{state.error}"
    return (
        f"调用 {tool_name}("
        f"{_json.dumps(args, ensure_ascii=False, default=str)}) 成功，"
        f"返回: {_json.dumps(state.result, ensure_ascii=False, default=str)}"
    )


# ── Finalize & Teardown ───────────────────────────────────


async def _finalize_turn(turn: Turn) -> AsyncGenerator[dict, None]:
    """while 循环结束后：running→completed/failed。"""
    if turn.committed_result is not None:
        async for ev in _finalize_committed_with_fallback(
            turn, "写入已成功，但收尾轮次未生成最终答复。"
        ):
            yield ev
    else:
        error_info = turn.record_error(
            "max_steps_reached",
            "达到最大步数限制，请缩小问题范围或重试",
            phase=TurnPhase.FINALIZING,
            stop_reason=StopReason.STEP_BUDGET_EXHAUSTED,
        )
        ev = sse.error_event(
            error_info["message"],
            "max_steps",
            phase=error_info["phase"],
            retryable=error_info["retryable"],
            attempt=error_info["attempt"],
        )
        turn.emit("error", ev["data"])
        yield ev
        answer = "本轮执行已达到推理步数上限，尚未完成请求。已停止继续调用工具，请补充信息后重试。"
        turn.final_answer = answer
        turn.set_phase(TurnPhase.TERMINAL)
        yield sse.final_answer_start()
        yield sse.final_answer(answer)


async def _finalize_committed_with_fallback(
    turn: Turn, message: str
) -> AsyncGenerator[dict, None]:
    """写入已提交但收尾失败时，用结构化结果生成确定性答复。

    统一处理三种场景：
    - LLM 流式调用失败（_handle_llm_error）
    - 收尾轮仍请求工具（_run_single_reasoning_step）
    - while 结束后仍未生成答复（_finalize_turn）
    """
    ev = sse.write_committed_reply_failed(message)
    turn.emit(ev["type"], ev["data"])
    yield ev
    turn.final_answer = _structured_commit_answer(turn.committed_result or {})
    turn.finalization_pending = False
    turn.status = "completed"
    turn.stop_reason = StopReason.MODEL_COMPLETED
    turn.set_phase(TurnPhase.TERMINAL)
    yield sse.final_answer_start()
    yield sse.final_answer(turn.final_answer)


# ── 辅助函数 ──────────────────────────────────────────────


def _persist_memory(turn: Turn) -> None:
    non_system = [m for m in turn.messages if m.get("role") != "system"]
    if turn.final_answer:
        non_system.append({"role": "assistant", "content": turn.final_answer})
    memory.save_messages(turn.memory_key or turn.conversation_id, non_system)


def _structured_commit_answer(result: dict) -> str:
    """LLM 收尾失败时，只使用已提交结果生成确定性答复。"""
    template = result.get("template") or {}
    cycle = result.get("cycle") or {}
    unit = result.get("planting_unit") or {}
    replay_note = (
        "（本次返回的是已提交请求的幂等结果）"
        if result.get("idempotent_replay")
        else ""
    )
    return (
        "种植计划已提交成功"
        f"{replay_note}：模板“{template.get('name', '未知')}”（ID {template.get('id', '-')}），"
        f"茬口“{cycle.get('name', '未知')}”（ID {cycle.get('id', '-')}），"
        f"种植单元“{unit.get('name', '未知')}”（ID {unit.get('id', '-')}，"
        f"面积 {unit.get('area_mu', '-')} 亩）。"
    )


def _append_followup_messages(
    turn: Turn,
    tool_name: str,
    args: dict,
    result: dict,
) -> None:
    """把后继动作（commit）的结果合成进 messages，供收尾 LLM 看到完整链路。

    LLM 没有真正调用 commit，但消息历史需要保持 OpenAI tool_calls 结构一致：
    追加一条带 tool_calls 的 assistant 消息 + 对应 tool 结果。
    """
    synthetic_call_id = f"followup-{tool_name}-{turn.step_count}"
    assistant_msg = context.assistant_message_with_tool_calls(
        "",
        [
            {
                "id": synthetic_call_id,
                "name": tool_name,
                "arguments": args,
            }
        ],
    )
    turn.messages.append(assistant_msg)
    turn.messages.append(
        context.tool_result_message(synthetic_call_id, tool_name, result)
    )


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


def _missing_params_result(skill: Skill, missing: list[str]) -> dict:
    """构造只给模型看的缺失信息，禁止把内部字段名直接回复给用户。"""
    required_any = skill.required_any_params()
    missing_fields = [name for name in missing if name != "__required_any__"]
    for name in required_any:
        if "__required_any__" in missing and name not in missing_fields:
            missing_fields.append(name)
    return {
        "error": "missing_information",
        "missing": missing_fields,
        "message": (
            skill.missing_params_prompt(missing)
            + "。请停止调用工具，直接用自然、简短的中文向用户询问这些业务信息；"
            "不要提及参数名、operation、tool 或 MCP。"
        ),
    }
