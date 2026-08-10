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

from agent.core import context, hitl, memory, planner, summarizer, tokenizer, verify
from agent.core.turn import Turn
from agent.infra import sse
from agent.infra.llm import chat_stream, MODEL
from agent.infra.logging import log_event
from agent.infra.mcp_client import BusinessClient
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

logger = logging.getLogger(__name__)

ApprovalWaiter = Callable[[str], Awaitable[tuple[bool, str]]]


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
    yield sse.meta(
        turn.turn_id,
        turn.conversation_id,
        turn.user_input,
        request_id=(get_trace().request_id if get_trace() else ""),
    )

    skills, tools_schema, skill_index, tracker, plan_box = _setup_turn_runtime(turn)

    async for ev in _try_compress_context(turn):
        yield ev

    try:
        identity_headers = {
            "X-Farm-Id": str(turn.farm_id),
            "X-User-Id": turn.user_id,
            "X-Agent-Token": turn.agent_token,
        }
        async with BusinessClient(headers=identity_headers) as business:
            skill_ctx = SkillContext(
                business_client=business,
                turn=turn,
                user_id=turn.user_id,
                farm_id=turn.farm_id,
                agent_token=turn.agent_token,
            )

            while turn.status == "running" and (
                turn.step_count < turn.max_steps or turn.finalization_pending
            ):
                turn.step_count += 1
                increment_step()

                async for ev in _run_single_reasoning_step(
                    turn=turn,
                    tools_schema=tools_schema,
                    tracker=tracker,
                    plan_box=plan_box,
                    skill_index=skill_index,
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
                async for ev in _finalize_turn(turn):
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


# ── 阶段 1: Setup ─────────────────────────────────────────


def _setup_turn_runtime(
    turn: Turn,
) -> tuple[list[Skill], list[dict], dict[str, Skill], verify.CallTracker, dict]:
    """加载 skills、构建 tools schema、初始化 tracker。"""
    turn.memory_snapshot = memory.snapshot(turn.conversation_id)
    skills = skill_loader.load_all()
    tools_schema = skill_loader.to_openai_tools(skills)
    # 注入 make_plan 工具，让 LLM 可以一次性规划多步任务
    tools_schema.append(planner.MAKE_PLAN_TOOL_SCHEMA)
    skill_index = {s.name: s for s in skills}
    logger.info(
        "loaded %d skills: %s",
        len(skills),
        [f"{s.name}({s.kind},{s.risk_level})" for s in skills],
    )
    turn.messages = context.build_initial_messages(
        turn.user_input, turn.memory_snapshot
    )
    return skills, tools_schema, skill_index, verify.CallTracker(), {"plan": None}


async def _try_compress_context(turn: Turn) -> AsyncGenerator[dict, None]:
    """检查 token 用量，超阈值触发压缩。"""
    usage = tokenizer.compute_usage(turn.messages)
    yield sse.context_usage(usage.used, usage.total, usage.percent, usage.level, step=0)
    if tokenizer.must_compress(usage):
        yield sse.context_compressing("hard", usage.percent)
        summary = await summarizer.maybe_summarize_async(
            turn.conversation_id, force=True
        )
        if summary:
            turn.memory_snapshot = memory.snapshot(turn.conversation_id)
            turn.messages = context.build_initial_messages(
                turn.user_input, turn.memory_snapshot
            )
            new_usage = tokenizer.compute_usage(turn.messages)
            yield sse.context_compressed(new_usage.percent, summary[:200])
    elif tokenizer.should_compress(usage):
        # soft 阈值：异步压缩，不阻塞当前 turn
        asyncio.create_task(
            summarizer.maybe_summarize_async(turn.conversation_id, force=False)
        )


# ── 阶段 3: while 主循环单步 ──────────────────────────────


async def _run_single_reasoning_step(
    *,
    turn: Turn,
    tools_schema: list[dict],
    tracker: verify.CallTracker,
    plan_box: dict,
    skill_index: dict[str, Skill],
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
) -> AsyncGenerator[dict, None]:
    """一次 while 迭代：doom 检测 → LLM → 工具分发。"""
    # ── Doom Loop 检测（参考 _example/tools/safety.py）──
    doom_msg = verify.detect_doom_loop(tracker.calls)
    if doom_msg:
        logger.warning("DOOM_LOOP: %s", doom_msg)
        ev = sse.doom_loop_warning(doom_msg, step=turn.step_count)
        turn.emit("doom_loop_warning", ev["data"])
        yield ev

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
        llm_result = await _call_llm_stream(llm_messages, tools_schema)
    except Exception as exc:
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
    yield sse.final_answer_start()
    yield sse.final_answer(content)


# ── LLM 调用 ──────────────────────────────────────────────


async def _call_llm_stream(
    llm_messages: list[dict], tools_schema: list[dict]
) -> _LlmResult:
    """流式 LLM 调用 + trace + 日志。失败时 raise。"""
    _llm_start = time.time()
    full_content = ""
    tool_calls: list[dict] = []

    async for token in chat_stream(llm_messages, tools=tools_schema):
        if token["type"] == "text":
            full_content += token["delta"]
        elif token["type"] == "done":
            tool_calls = token.get("tool_calls", [])
        elif token["type"] == "error":
            raise RuntimeError(token["message"])

    _llm_ms = int((time.time() - _llm_start) * 1000)
    trace_llm_call(
        model=MODEL,
        messages=llm_messages,
        response={
            "content_length": len(full_content),
            "tool_calls_count": len(tool_calls),
            "tool_calls": [
                {
                    "name": call.get("name"),
                    "argument_keys": sorted((call.get("arguments") or {}).keys()),
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
    return _LlmResult(full_content=full_content, tool_calls=tool_calls)


async def _handle_llm_error(turn: Turn, exc: Exception) -> AsyncGenerator[dict, None]:
    """LLM 调用失败时的错误处理：已提交→结构化降级，否则→failed。"""
    if turn.committed_result is not None:
        async for ev in _finalize_committed_with_fallback(
            turn, f"写入已成功，但最终答复生成失败：{exc}"
        ):
            yield ev
    else:
        turn.status = "failed"
        turn.error = f"llm_stream_failed: {exc}"
        ev = sse.error_event(str(exc), "llm_call_failed")
        turn.emit("error", ev["data"])
        yield ev


# ── 工具分发 ──────────────────────────────────────────────


async def _dispatch_tool_calls(
    *,
    tool_calls: list[dict],
    rationale: str,
    skill_index: dict[str, Skill],
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    turn: Turn,
    tracker: verify.CallTracker,
    plan_box: dict,
) -> AsyncGenerator[dict, None]:
    """处理一轮 tool_calls：make_plan / 普通 skill / approval_followup。"""
    for tc in tool_calls:
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


async def _process_skill_call(
    *,
    tc: dict,
    rationale: str,
    skill_index: dict[str, Skill],
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    turn: Turn,
    tracker: verify.CallTracker,
) -> AsyncGenerator[dict, None]:
    """单个 skill tool_call 完整处理：校验→审批→执行→后处理。终止分支通过 turn 状态通知外层。"""
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
    ):
        yield ev

    async for ev in _post_process_skill_result(
        tc=tc,
        turn=turn,
        skill=skill,
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
    state: _SkillExecState,
    skill_index: dict[str, Skill],
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    rationale: str,
) -> AsyncGenerator[dict, None]:
    """后处理：append tool_msg → finalize/followup。"""
    turn.messages.append(
        context.tool_result_message(tc["id"], tc["name"], state.result)
    )
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
    skill_index: dict[str, Skill],
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
    ev = sse.observation(tool_name, None, error=err_msg)
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
    ev = sse.observation(tool_name, None, error=err_msg)
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
    ev = sse.observation(tool_name, None, error=message)
    turn.emit("observation", ev["data"])
    yield ev
    turn.messages.append(context.tool_result_message(tool_call_id, tool_name, result))


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
        turn.final_answer = (
            f"⚠️ 已终止：{doom}\n\n"
            "可能原因：缺少必要参数或操作无法完成。"
            "请提供更详细的信息后重试。"
        )
        turn.status = "completed"
        yield sse.final_answer(turn.final_answer)


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
    turn = hitl.approve(turn, decision, reason)

    ev = sse.approval_result("approved" if decision else "rejected", reason)
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
) -> AsyncGenerator[dict, None]:
    """执行 skill：action → skill.execute() → observation。填充 state。

    被三处调用方复用：主循环 _dispatch_tool_calls、_drive_approval_followup、
    _execute_plan_step，避免 HITL/trace/事件逻辑出现三份不同实现。
    """
    ev = sse.action(skill.name, args, rationale=rationale)
    # 先 emit 占位事件，skill 可能兜底替换参数后回写
    turn.emit("action", ev["data"])

    try:
        _tool_start = time.time()
        result_obj = await skill.execute(args, skill_ctx)
        _tool_ms = int((time.time() - _tool_start) * 1000)
        # skill 兜底可能回写了 action 事件的 arguments
        action_data = _find_latest_action_data(turn, skill.name) or ev["data"]
        yield sse.action(
            action_data["tool_name"],
            action_data.get("arguments", args),
            rationale=action_data.get("rationale", ""),
        )
        state.result_obj = result_obj
        if result_obj.error:
            state.result = result_obj.data or {"error": result_obj.error}
            state.error = result_obj.error
            obs_ev = sse.observation(skill.name, None, error=result_obj.error)
            trace_tool_call(
                skill.name, args, None, duration_ms=_tool_ms, error=result_obj.error
            )
        else:
            state.result = result_obj.data
            state.finalize_after_success = skill.finalize_after_success
            obs_ev = sse.observation(skill.name, state.result)
            trace_tool_call(skill.name, args, state.result, duration_ms=_tool_ms)
        turn.emit("observation", obs_ev["data"])
        yield obs_ev
    except Exception as exc:
        logger.exception("skill execution failed: %s", skill.name)
        state.result = {"error": str(exc)}
        state.error = str(exc)
        obs_ev = sse.observation(skill.name, None, error=str(exc))
        turn.emit("observation", obs_ev["data"])
        yield obs_ev
        trace_tool_call(skill.name, args, None, error=str(exc))


# ── prepare → commit 审批后继 ─────────────────────────────


async def _drive_approval_followup(
    *,
    prepare_result: dict,
    followup_config: dict,
    skill_index: dict[str, Skill],
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
    ev = sse.observation(followup_tool_name, None, error=message)
    turn.emit("observation", ev["data"])
    yield ev
    turn.status = "failed"
    turn.error = message
    err_ev = sse.error_event(message, "followup_skill_missing")
    turn.emit("error", err_ev["data"])
    yield err_ev


async def _converge_followup_error(
    turn: Turn, state: _SkillExecState
) -> AsyncGenerator[dict, None]:
    """commit 业务错误立即收敛：不喂给 LLM 选其他工具。"""
    code = (
        state.result.get("code") if isinstance(state.result, dict) else None
    ) or "commit_failed"
    turn.status = "failed"
    turn.error = code
    err_ev = sse.error_event(state.error, code)
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
    ev = sse.observation(followup_tool_name, None, error=message)
    turn.emit("observation", ev["data"])
    yield ev
    turn.status = "failed"
    turn.error = "prepare_result_incomplete"
    err_ev = sse.error_event(message, "prepare_result_incomplete")
    turn.emit("error", err_ev["data"])
    yield err_ev


# ── make_plan 处理 ────────────────────────────────────────


async def _handle_make_plan(
    args: dict,
    rationale: str,
    skill_index: dict[str, Skill],
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
    skill_index: dict[str, Skill],
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
    skill_index: dict[str, Skill],
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
        turn.status = "failed"
        turn.error = "max_steps_reached"
        ev = sse.error_event("达到最大步数限制，请缩小问题范围或重试", "max_steps")
        turn.emit("error", ev["data"])
        yield ev


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
    yield sse.final_answer_start()
    yield sse.final_answer(turn.final_answer)


# ── 辅助函数 ──────────────────────────────────────────────


def _persist_memory(turn: Turn) -> None:
    non_system = [m for m in turn.messages if m.get("role") != "system"]
    if turn.final_answer:
        non_system.append({"role": "assistant", "content": turn.final_answer})
    memory.save_messages(turn.conversation_id, non_system)


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
    properties = skill.parameters_schema.get("properties") or {}
    details = [
        str((properties.get(name) or {}).get("description") or name) for name in missing
    ]
    return {
        "error": "missing_information",
        "missing": missing,
        "message": (
            "当前请求缺少完成业务动作所需的信息："
            + "；".join(details)
            + "。请停止调用工具，直接用自然、简短的中文向用户询问这些业务信息；"
            "不要提及参数名、operation、tool 或 MCP。"
        ),
    }
