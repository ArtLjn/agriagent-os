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
from agent.skills.context import SkillContext

logger = logging.getLogger(__name__)

ApprovalWaiter = Callable[[str], Awaitable[tuple[bool, str]]]


async def run_turn(
    turn: Turn,
    approval_waiter: ApprovalWaiter,
) -> AsyncGenerator[dict, None]:
    """Execute one user turn. Yields SSE events as they happen."""
    turn.memory_snapshot = memory.snapshot(turn.conversation_id)

    yield sse.meta(
        turn.turn_id,
        turn.conversation_id,
        turn.user_input,
        request_id=(get_trace().request_id if get_trace() else ""),
    )

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

    # turn 开始时检查 token 使用情况，超阈值触发压缩
    usage = tokenizer.compute_usage(turn.messages)
    yield sse.context_usage(usage.used, usage.total, usage.percent, usage.level, step=0)
    if tokenizer.must_compress(usage):
        yield sse.context_compressing("hard", usage.percent)
        summary = await summarizer.maybe_summarize_async(
            turn.conversation_id, force=True
        )
        if summary:
            # 压缩后重建 messages
            turn.memory_snapshot = memory.snapshot(turn.conversation_id)
            turn.messages = context.build_initial_messages(
                turn.user_input, turn.memory_snapshot
            )
            new_usage = tokenizer.compute_usage(turn.messages)
            yield sse.context_compressed(new_usage.percent, summary[:200])
    elif tokenizer.should_compress(usage):
        # soft 阈值：异步压缩，不阻塞当前 turn
        import asyncio

        asyncio.create_task(
            summarizer.maybe_summarize_async(turn.conversation_id, force=False)
        )

    # CallTracker 跟踪本 turn 所有 skill 调用（用于 doom loop 检测 + checklist）
    tracker = verify.CallTracker()
    # 当前 plan（如果 LLM 触发了 make_plan），final_answer 前用来跑 checklist。
    # 用 dict 容器让 _handle_make_plan 能跨函数修改（Python 闭包限制）。
    current_plan_box: dict = {"plan": None}

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
                # 不修改 turn.messages，只在 LLM 调用时临时追加
                llm_messages = context.append_reminder(turn.messages, turn.step_count)

                # ── 流式 LLM 调用 ───────────────────────────────
                _llm_start = time.time()
                full_content = ""
                tool_calls_result: list[dict] = []

                try:
                    async for token in chat_stream(llm_messages, tools=tools_schema):
                        if token["type"] == "text":
                            full_content += token["delta"]
                        elif token["type"] == "done":
                            tool_calls_result = token.get("tool_calls", [])
                        elif token["type"] == "error":
                            raise RuntimeError(token["message"])

                    # 记录 LLM trace（MongoDB）+ 结构化日志（log_event）
                    _llm_ms = int((time.time() - _llm_start) * 1000)
                    trace_llm_call(
                        model=MODEL,
                        messages=llm_messages,
                        response={
                            "content_length": len(full_content),
                            "tool_calls_count": len(tool_calls_result),
                            "tool_calls": [
                                {
                                    "name": call.get("name"),
                                    "argument_keys": sorted(
                                        (call.get("arguments") or {}).keys()
                                    ),
                                }
                                for call in tool_calls_result
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
                        data={"model": MODEL, "tool_calls": len(tool_calls_result)},
                    )
                except Exception as exc:
                    if turn.committed_result is not None:
                        message = f"写入已成功，但最终答复生成失败：{exc}"
                        ev = sse.write_committed_reply_failed(message)
                        turn.emit(ev["type"], ev["data"])
                        yield ev
                        turn.final_answer = _structured_commit_answer(
                            turn.committed_result
                        )
                        turn.finalization_pending = False
                        turn.status = "completed"
                        yield sse.final_answer_start()
                        yield sse.final_answer(turn.final_answer)
                    else:
                        turn.status = "failed"
                        turn.error = f"llm_stream_failed: {exc}"
                        ev = sse.error_event(str(exc), "llm_call_failed")
                        turn.emit("error", ev["data"])
                        yield ev
                    break

                if turn.finalization_pending and tool_calls_result:
                    message = "写入已成功，但收尾模型仍请求调用工具；已阻止重复写入。"
                    ev = sse.write_committed_reply_failed(message)
                    turn.emit(ev["type"], ev["data"])
                    yield ev
                    turn.final_answer = _structured_commit_answer(
                        turn.committed_result or {}
                    )
                    turn.finalization_pending = False
                    turn.status = "completed"
                    yield sse.final_answer_start()
                    yield sse.final_answer(turn.final_answer)
                    break

                # 有 tool_calls → 文本是思考过程，发给 thought 事件
                if tool_calls_result and full_content:
                    ev = sse.thought(full_content)
                    turn.emit("thought", ev["data"])
                    yield ev

                # 无 tool_calls → 流式输出最终回答
                if not tool_calls_result:
                    # 完成前 checklist（参考 _example/tools/verify.py:pre_completion_checklist）
                    issues = verify.pre_completion_checklist(
                        current_plan_box["plan"], tracker
                    )
                    if issues:
                        ev = sse.verification_warning(issues, step=turn.step_count)
                        turn.emit("verification_warning", ev["data"])
                        yield ev

                    turn.final_answer = full_content
                    if turn.committed_result is not None:
                        trace_commit_state(
                            turn.committed_result,
                            reply_generated=True,
                        )
                    turn.finalization_pending = False
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

                    # ── make_plan 特殊工具：转入 planner 处理 ──
                    if tool_name == "make_plan":
                        async for plan_ev, plan_obs in _handle_make_plan(
                            args,
                            full_content,
                            skill_index,
                            skill_ctx,
                            approval_waiter,
                            turn,
                            tracker,
                            current_plan_box,
                        ):
                            if plan_ev is not None:
                                yield plan_ev
                            if plan_obs is not None:
                                # 把 plan 的 observation 喂回 LLM
                                turn.messages.append(
                                    context.tool_result_message(
                                        tool_call_id, "make_plan", plan_obs
                                    )
                                )
                                break
                        continue

                    skill = skill_index.get(tool_name)
                    if skill is None:
                        err_msg = f"未知工具: {tool_name}"
                        result = {"error": err_msg}
                        ev = sse.observation(tool_name, None, error=err_msg)
                        turn.emit("observation", ev["data"])
                        yield ev
                        turn.messages.append(
                            context.tool_result_message(tool_call_id, tool_name, result)
                        )
                        continue

                    # ── 参数规范化：仅处理 skill 自身的确定性默认值 ──
                    enriched = skill.enrich_params(args, skill_ctx)
                    if enriched != args:
                        logger.info(
                            "skill %s params enriched: %s → %s",
                            tool_name,
                            args,
                            enriched,
                        )
                        args = enriched
                        tc["arguments"] = enriched  # 回写，确保 action 事件显示真实参数

                    # 缺参调用也计入 tracker，避免模型重复提交同一空参数调用。
                    tracker.record(tool_name, args)
                    missing = skill.missing_required_params(args)
                    if missing:
                        result = _missing_params_result(skill, missing)
                        message = result["message"]
                        trace_tool_call(tool_name, args, result, error=message)
                        ev = sse.observation(tool_name, None, error=message)
                        turn.emit("observation", ev["data"])
                        yield ev
                        turn.messages.append(
                            context.tool_result_message(tool_call_id, tool_name, result)
                        )
                        continue

                    # ── CallTracker 记录 + 重复调用 warning ──
                    dup_warn = verify.check_duplication(tracker, tool_name, args)
                    if dup_warn:
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
                            break

                    risk = skill.dynamic_risk_level(args)
                    logger.info(
                        "skill %s risk_level=%s (meta=%s)",
                        tool_name,
                        risk,
                        getattr(skill, "_meta", {}).get("risk_level"),
                    )
                    if hitl.needs_approval(risk):
                        turn = hitl.gate(
                            turn,
                            tool_name=tool_name,
                            tool_description=skill.description,
                            arguments=args,
                            tool_call_id=tool_call_id,
                            rationale=full_content,
                            risk=risk,
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
                        finalize_after_success = False
                        _tool_start = time.time()
                        result_obj = await skill.execute(args, skill_ctx)
                        _tool_ms = int((time.time() - _tool_start) * 1000)
                        # skill 兜底可能回写了 action 事件的 arguments
                        # 从 turn.events 取最新 action data 发给客户端
                        action_data = (
                            _find_latest_action_data(turn, tool_name) or ev["data"]
                        )
                        yield sse.action(
                            action_data["tool_name"],
                            action_data.get("arguments", args),
                            rationale=action_data.get("rationale", ""),
                        )
                        if result_obj.error:
                            result = result_obj.data or {"error": result_obj.error}
                            ev = sse.observation(
                                tool_name, None, error=result_obj.error
                            )
                            trace_tool_call(
                                tool_name,
                                args,
                                None,
                                duration_ms=_tool_ms,
                                error=result_obj.error,
                            )
                        else:
                            result = result_obj.data
                            finalize_after_success = skill.finalize_after_success
                            ev = sse.observation(tool_name, result)
                            trace_tool_call(
                                tool_name, args, result, duration_ms=_tool_ms
                            )
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
                    if finalize_after_success:
                        committed = (
                            result if isinstance(result, dict) else {"result": result}
                        )
                        turn.committed_result = committed
                        turn.finalization_pending = True
                        trace_commit_state(committed, reply_generated=False)
                        committed_event = sse.operation_committed(committed)
                        turn.emit(committed_event["type"], committed_event["data"])
                        yield committed_event
                        # 业务已经提交，剩余轮次只允许基于结果生成最终答复。
                        tools_schema = []
                        break

                if turn.status == "rejected":
                    break

            if turn.status == "running":
                if turn.committed_result is not None:
                    message = "写入已成功，但收尾轮次未生成最终答复。"
                    ev = sse.write_committed_reply_failed(message)
                    turn.emit(ev["type"], ev["data"])
                    yield ev
                    turn.final_answer = _structured_commit_answer(turn.committed_result)
                    turn.finalization_pending = False
                    turn.status = "completed"
                    yield sse.final_answer_start()
                    yield sse.final_answer(turn.final_answer)
                else:
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


async def _handle_make_plan(
    args: dict,
    rationale: str,
    skill_index: dict,
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
    for step_idx, step in enumerate(plan.steps):
        step.status = "running"
        # 走和单步调用一致的处理流程
        step_obs: str | None = None
        async for sub_event, obs in _execute_single_skill(
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
                yield (sub_event, None)
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

        # 发 plan_step_done 事件
        step_ev = sse.plan_step_done(step_idx, step.skill, step.status, step.result)
        turn.emit("plan_step_done", step_ev["data"])
        yield (step_ev, None)

        # 如果用户拒绝审批，立即终止 plan
        if turn.status == "rejected":
            yield (None, f"plan 中断：{step_obs}")
            return

    # plan 完成，给 LLM 一个总结性 observation
    summary = planner.plan_summary_for_observation(plan)
    yield (None, summary)


async def _execute_single_skill(
    tool_name: str,
    args: dict,
    rationale: str,
    skill_index: dict,
    skill_ctx: SkillContext,
    approval_waiter: ApprovalWaiter,
    turn: Turn,
    tracker: verify.CallTracker,
) -> AsyncGenerator[tuple[dict | None, str | None], None]:
    """执行单个 skill 调用（plan 内部每步都走这个）。

    async generator：yield (sse_event_or_None, observation_str_or_None)。
    逻辑跟 react.py 主循环里的 skill 调用流程一致：HITL + trace + 事件发送。
    """
    import json as _json

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

    # HITL
    risk = skill.dynamic_risk_level(args)
    if hitl.needs_approval(risk):
        turn = hitl.gate(
            turn,
            tool_name=tool_name,
            tool_description=skill.description,
            arguments=args,
            tool_call_id=f"plan-{tool_name}",
            rationale=rationale,
            risk=risk,
        )
        ev = sse.approval_required(
            tool_name=tool_name,
            arguments=args,
            rationale=rationale,
            risk_level=risk,
            turn_id=turn.turn_id,
        )
        turn.emit("approval_required", ev["data"])
        yield (ev, None)

        decision, reason = await approval_waiter(turn.turn_id)
        turn = hitl.approve(turn, decision, reason)

        ev = sse.approval_result("approved" if decision else "rejected", reason)
        turn.emit("approval_result", ev["data"])
        yield (ev, None)

        if not decision:
            obs = f"用户拒绝执行 {tool_name}：{reason or '用户拒绝'}"
            yield (None, obs)
            return

    if turn.status == "rejected":
        return

    # action 事件
    ev = sse.action(tool_name, args, rationale=rationale)
    turn.emit("action", ev["data"])

    try:
        _tool_start = time.time()
        result_obj = await skill.execute(args, skill_ctx)
        _tool_ms = int((time.time() - _tool_start) * 1000)

        # 取兜底后的 action 参数
        action_data = _find_latest_action_data(turn, tool_name) or ev["data"]
        yield (
            sse.action(
                action_data["tool_name"],
                action_data.get("arguments", args),
                rationale=action_data.get("rationale", ""),
            ),
            None,
        )

        if result_obj.error:
            result = {"error": result_obj.error}
            obs_ev = sse.observation(tool_name, None, error=result_obj.error)
            trace_tool_call(
                tool_name, args, None, duration_ms=_tool_ms, error=result_obj.error
            )
            obs_str = f"调用 {tool_name} 失败：{result_obj.error}"
        else:
            result = result_obj.data
            obs_ev = sse.observation(tool_name, result)
            trace_tool_call(tool_name, args, result, duration_ms=_tool_ms)
            obs_str = f"调用 {tool_name}({_json.dumps(args, ensure_ascii=False, default=str)}) 成功，返回: {_json.dumps(result, ensure_ascii=False, default=str)}"
        turn.emit("observation", obs_ev["data"])
        yield (obs_ev, obs_str)
    except Exception as exc:
        logger.exception("skill execution failed: %s", tool_name)
        result = {"error": str(exc)}
        obs_ev = sse.observation(tool_name, None, error=str(exc))
        turn.emit("observation", obs_ev["data"])
        yield (obs_ev, f"调用 {tool_name} 异常: {exc}")
        trace_tool_call(tool_name, args, None, error=str(exc))


def _missing_params_result(skill, missing: list[str]) -> dict:
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
