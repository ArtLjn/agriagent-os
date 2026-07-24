"""Executor 级 pending action 统一服务。"""

import logging
import re

from app.agent.executor.models import PendingActionDecision
from app.agent.executor.pending_aliases import (
    pending_alias_metadata,
    pending_alias_metadata_or_trace,
)
from app.agent.executor.skill_raw_executor import execute_write_skill_raw
from app.agent.executor.tool_failure_reflection import reflect_tool_failure
from app.agent.runtime.tool_arg_validation import validate_pending_tool_args
from app.agent.reflector import (
    ReflectionDecision,
    ReflectionTrigger,
    ReflectorService,
)
from app.skills import get_langchain_tools
from app.infra.pending_actions import (
    PendingAction,
    PendingPlan,
    PendingPlanStep,
    _pending,
    _pending_plans,
    build_confirm_message,
    build_confirmation_context,
    build_plan_confirm_message,
    detect_user_intent,
    get_cache_groups_for_skill,
    get_pending,
    get_pending_plan,
    remove_pending,
    store_pending,
)
from app.shared.database import SessionLocal
from app.agent.pending_plan_service import (
    cancel_active_plan,
    mark_step_executed,
    mark_step_failed,
)
from app.infra.skill_cache import clear_cache as clear_skill_cache
from app.infra.trace_collector import get_collector

logger = logging.getLogger(__name__)

_MISSING_TEMPLATE_RE = re.compile(r"系统还没有\s*(?P<crop>.+?)\s*模板")
_CLEAR_CORRECTION_RE = re.compile(
    r"(?:改成|改为|改到|更正|纠正|不是|金额|分类|日期|对象|备注|\d+\s*(?:元|块|万|w|W|千|百))"
)


async def _execute_write_skill(
    farm_id: int,
    skill_name: str,
    params: dict,
    farm_uid: str | None = None,
):
    """执行 pending action 中存储的写操作 Skill，并返回结构化结果。"""
    return await execute_write_skill_raw(
        farm_id=farm_id,
        skill_name=skill_name,
        params=params,
        farm_uid=farm_uid,
    )


def _get_metadata_cache_groups(
    skill_name: str,
    farm_id: int,
    farm_uid: str | None = None,
) -> list[str]:
    """从 LangChain tool metadata 读取缓存失效组，缺失时回退旧映射。"""
    try:
        tool_map = {
            tool.name: tool
            for tool in get_langchain_tools(farm_id=farm_id, farm_uid=farm_uid)
        }
        alias_metadata = pending_alias_metadata(skill_name, {})
        resolved_tool_name = alias_metadata.get("resolved_capability") or skill_name
        tool = tool_map.get(resolved_tool_name) or tool_map.get(skill_name)
        metadata = getattr(tool, "skill_metadata", None) if tool else None
        cache_groups = getattr(metadata, "cache_invalidation", None)
        if cache_groups:
            return list(cache_groups)
    except Exception as exc:
        logger.warning(
            "读取 Skill metadata 缓存失效配置失败，使用 fallback | skill=%s error=%s",
            skill_name,
            exc,
        )

    return get_cache_groups_for_skill(skill_name)


def _clear_cache_groups(skill_name: str, cache_groups: list[str]) -> list[str]:
    """清理指定缓存组。"""
    cleared_groups = []
    for group in cache_groups:
        cleared = clear_skill_cache(group)
        cleared_groups.append(group)
        if cleared:
            logger.info(
                "写操作后清除缓存 | skill=%s group=%s cleared=%d",
                skill_name,
                group,
                cleared,
            )
    return cleared_groups


def _format_follow_up_intro(skill_name: str, params: dict) -> str:
    """生成后续确认动作的自然语言引导。"""
    if skill_name == "create_crop_cycle":
        crop_name = str(params.get("crop_name") or "").strip()
        return (
            f"现在可以继续创建{crop_name}茬口。"
            if crop_name
            else "现在可以继续创建茬口。"
        )

    return "下一步需要继续确认。"


def _is_clear_pending_correction(message: str) -> bool:
    """判断用户是否在明确修正待确认参数，需要交给 LLM 重新规划。"""
    return bool(_CLEAR_CORRECTION_RE.search(message.strip()))


def _extract_missing_template_crop(pending: PendingAction, result: str) -> str:
    """从缺模板结果中提取作物名，优先使用 pending 参数。"""
    crop_name = str(pending.params.get("crop_name") or "").strip()
    if crop_name:
        return crop_name

    match = _MISSING_TEMPLATE_RE.search(result)
    return match.group("crop").strip() if match else ""


def _skill_result_reply(result) -> str:
    return str(getattr(result, "reply", result) or "")


def _skill_result_status(result) -> str:
    if isinstance(result, str):
        return "success" if result else "failed"
    status = getattr(result, "status", None)
    value = getattr(status, "value", status)
    text = str(value or "").lower()
    if "." in text:
        text = text.rsplit(".", maxsplit=1)[-1]
    return text


def _skill_result_failed_or_needs_clarify(result) -> bool:
    return _skill_result_status(result) in {"failed", "need_clarify"}


def _contract_blocked_confirmation(
    *,
    farm_id: int,
    pending: PendingAction,
    session_id: str | None,
) -> PendingActionDecision | None:
    validation = validate_pending_tool_args(
        skill_name=pending.skill_name,
        params=pending.params,
        farm_id=farm_id,
    )
    pending.params.clear()
    pending.params.update(validation.params)
    if validation.valid:
        return None
    get_collector().record(
        node_type="skill_call",
        node_name=pending.skill_name,
        input_data=pending.params,
        output_data={
            "status": "contract_blocked",
            "phase": "confirm_pending_action",
            "action_id": pending.action_id,
            "session_id": session_id,
            "contract_validation": validation.trace_payload(),
        },
        duration_ms=0,
    )
    return PendingActionDecision.modified(
        reply=validation.message,
        handled=True,
    )


async def _confirm_pending(
    farm_id: int,
    pending: PendingAction,
    farm_uid: str | None = None,
    session_id: str | None = None,
) -> PendingActionDecision:
    """执行已确认的 pending action，并处理缺模板和链式动作。"""
    contract_block = _contract_blocked_confirmation(
        farm_id=farm_id, pending=pending, session_id=session_id
    )
    if contract_block is not None:
        return contract_block

    reflection_block, alias_metadata = _pre_execution_reflection_block(
        farm_id=farm_id,
        pending=pending,
        session_id=session_id,
    )
    if reflection_block is not None:
        return reflection_block

    result = await _execute_write_skill(
        farm_id=farm_id,
        skill_name=pending.skill_name,
        params=pending.params,
        farm_uid=farm_uid,
    )
    if _skill_result_failed_or_needs_clarify(result):
        return _failed_skill_result_decision(
            farm_id=farm_id,
            pending=pending,
            result=result,
            session_id=session_id,
        )

    return _successful_skill_result_decision(
        farm_id=farm_id,
        pending=pending,
        result=result,
        alias_metadata=alias_metadata,
        farm_uid=farm_uid,
        session_id=session_id,
    )


def _pre_execution_reflection_block(
    *,
    farm_id: int,
    pending: PendingAction,
    session_id: str | None,
) -> tuple[PendingActionDecision | None, dict]:
    alias_metadata = pending_alias_metadata_or_trace(
        pending.skill_name,
        pending.params,
    )
    reflection_result = ReflectorService().check_write_plan(
        trigger=ReflectionTrigger.PRE_EXECUTION,
        skill_name=pending.skill_name,
        params=pending.params,
        confirmation_text=build_confirm_message(
            pending.skill_name,
            pending.params,
            original_input=pending.original_input,
        ),
        trace_metadata={
            "farm_id": farm_id,
            "session_id": session_id,
            "phase": "confirm_pending_action",
            "action_id": pending.action_id,
            "tool_name": pending.skill_name,
            **alias_metadata,
        },
    )
    if reflection_result.decision != ReflectionDecision.PASS:
        return (
            PendingActionDecision.failed(f"执行失败：{reflection_result.reason}"),
            alias_metadata,
        )
    return None, alias_metadata


def _failed_skill_result_decision(
    *,
    farm_id: int,
    pending: PendingAction,
    result,
    session_id: str | None,
) -> PendingActionDecision:
    reply = _skill_result_reply(result)
    repair_decision = reflect_tool_failure(
        farm_id=farm_id,
        skill_name=pending.skill_name,
        params=pending.params,
        result=result,
        repair_attempts=pending.repair_attempts,
        original_input=pending.original_input,
        session_id=session_id,
    )
    if repair_decision.action == "ask_repaired_confirmation":
        _store_repaired_pending(farm_id, pending, repair_decision, session_id)
        return PendingActionDecision.modified(
            reply=(
                f"执行失败：{reply}\n\n"
                f"我已根据失败原因修正待确认参数，请重新确认。\n"
                f"{repair_decision.confirmation_text}"
            ),
            handled=True,
        )
    remove_pending(farm_id, session_id=session_id)
    return PendingActionDecision.failed(f"执行失败：{reply}")


def _store_repaired_pending(
    farm_id: int,
    pending: PendingAction,
    repair_decision,
    session_id: str | None,
) -> None:
    repaired_params = repair_decision.repaired_params or {}
    store_pending(
        farm_id,
        pending.skill_name,
        repaired_params,
        original_input=pending.original_input,
        confirmation_context=build_confirmation_context(
            pending.skill_name,
            repaired_params,
            original_input=pending.original_input,
        ),
        follow_up_skill_name=pending.follow_up_skill_name,
        follow_up_params=pending.follow_up_params,
        follow_up_original_input=pending.follow_up_original_input,
        session_id=session_id,
        repair_attempts=repair_decision.repair_attempts,
        metadata={"tool_failure_repair": repair_decision.trace_payload()},
    )


def _successful_skill_result_decision(
    *,
    farm_id: int,
    pending: PendingAction,
    result,
    alias_metadata: dict,
    farm_uid: str | None,
    session_id: str | None,
) -> PendingActionDecision:
    reply = _skill_result_reply(result)
    cache_groups = _get_metadata_cache_groups(
        pending.skill_name,
        farm_id=farm_id,
        farm_uid=farm_uid,
    )
    cleared_groups = _clear_cache_groups(pending.skill_name, cache_groups)
    remove_pending(farm_id, session_id=session_id)
    metadata = {"cache_groups_cleared": cleared_groups, **alias_metadata}

    template_decision = _missing_template_follow_up_decision(
        farm_id=farm_id,
        pending=pending,
        reply=reply,
        metadata=metadata,
        session_id=session_id,
    )
    if template_decision is not None:
        return template_decision

    follow_up_decision = _follow_up_pending_decision(
        farm_id=farm_id,
        pending=pending,
        reply=reply,
        metadata=metadata,
        session_id=session_id,
    )
    if follow_up_decision is not None:
        return follow_up_decision

    return PendingActionDecision.confirmed(f"已执行：{reply}", metadata=metadata)


def _missing_template_follow_up_decision(
    *,
    farm_id: int,
    pending: PendingAction,
    reply: str,
    metadata: dict,
    session_id: str | None,
) -> PendingActionDecision | None:
    if (
        pending.skill_name == "create_crop_cycle"
        and "系统还没有" in reply
        and "模板" in reply
    ):
        crop_name = _extract_missing_template_crop(pending, reply)
        if crop_name:
            store_pending(
                farm_id,
                "manage_crop_templates",
                {"operation": "create_template", "crop_name": crop_name},
                original_input=f"系统还没有{crop_name}作物模板",
                follow_up_skill_name="create_crop_cycle",
                follow_up_params=dict(pending.params),
                follow_up_original_input=pending.original_input,
                session_id=session_id,
            )
            confirm = build_confirm_message(
                "manage_crop_templates",
                {"operation": "create_template", "crop_name": crop_name},
                original_input=f"系统还没有{crop_name}作物模板",
            )
            reply = (
                f"系统还没有{crop_name}作物模板。创建茬口前需要先创建模板。\n{confirm}"
            )
            return PendingActionDecision.confirmed(reply, metadata=metadata)
    return None


def _follow_up_pending_decision(
    *,
    farm_id: int,
    pending: PendingAction,
    reply: str,
    metadata: dict,
    session_id: str | None,
) -> PendingActionDecision | None:
    if pending.follow_up_skill_name and pending.follow_up_params is not None:
        store_pending(
            farm_id,
            pending.follow_up_skill_name,
            dict(pending.follow_up_params),
            original_input=pending.follow_up_original_input,
            session_id=session_id,
        )
        confirm = build_confirm_message(
            pending.follow_up_skill_name,
            pending.follow_up_params,
            original_input=pending.follow_up_original_input,
        )
        intro = _format_follow_up_intro(
            pending.follow_up_skill_name,
            pending.follow_up_params,
        )
        response = f"已执行：{reply}\n\n{intro}\n{confirm}"
        return PendingActionDecision.confirmed(response, metadata=metadata)
    return None


async def _confirm_pending_plan(
    farm_id: int,
    plan: PendingPlan,
    farm_uid: str | None = None,
    session_id: str | None = None,
) -> PendingActionDecision:
    """按顺序执行 pending plan 中的所有写操作步骤。"""
    reflection_block = _pending_plan_reflection_block(
        farm_id=farm_id,
        plan=plan,
        session_id=session_id,
    )
    if reflection_block is not None:
        return reflection_block

    results: list[str] = []
    cleared_groups_by_step: list[dict] = []
    for step in sorted(plan.steps, key=lambda item: item.step_index):
        step_decision, result_reply, metadata = await _execute_pending_plan_step(
            farm_id=farm_id,
            plan=plan,
            step=step,
            farm_uid=farm_uid,
            session_id=session_id,
        )
        if step_decision is not None:
            return step_decision
        results.append(result_reply or "")
        cleared_groups_by_step.append(metadata or {})

    _clear_runtime_pending_plan_cache(farm_id, session_id)
    reply_lines = ["已执行："]
    reply_lines.extend(f"{index}. {result}" for index, result in enumerate(results, 1))
    return PendingActionDecision.confirmed(
        "\n".join(reply_lines),
        metadata={"steps": cleared_groups_by_step},
    )


def _pending_plan_reflection_block(
    *,
    farm_id: int,
    plan: PendingPlan,
    session_id: str | None,
) -> PendingActionDecision | None:
    plan_alias_metadata = [
        pending_alias_metadata_or_trace(step.tool_name, step.params)
        for step in plan.steps
    ]
    reflection_result = ReflectorService().check_pending_plan(
        trigger=ReflectionTrigger.PRE_EXECUTION,
        steps=plan.steps,
        confirmation_text=build_plan_confirm_message(plan.steps),
        trace_metadata={
            "farm_id": farm_id,
            "session_id": session_id,
            "phase": "confirm_pending_plan",
            "plan_id": plan.plan_id,
            "tool_names": [step.tool_name for step in plan.steps],
            "resolved_operations": plan_alias_metadata,
        },
    )
    if reflection_result.decision == ReflectionDecision.PASS:
        return None
    return PendingActionDecision.failed(f"执行失败：{reflection_result.reason}")


async def _execute_pending_plan_step(
    *,
    farm_id: int,
    plan: PendingPlan,
    step: PendingPlanStep,
    farm_uid: str | None,
    session_id: str | None,
) -> tuple[PendingActionDecision | None, str | None, dict | None]:
    alias_metadata = pending_alias_metadata_or_trace(step.tool_name, step.params)
    params = _normalize_pending_plan_step_params(step.tool_name, step.params)
    contract_block = _contract_blocked_pending_plan_step(
        farm_id=farm_id,
        plan=plan,
        step=step,
        params=params,
        session_id=session_id,
    )
    if contract_block is not None:
        return contract_block, None, None

    result = await _execute_pending_plan_step_raw(
        farm_id=farm_id,
        plan_id=plan.plan_id,
        step=step,
        params=params,
        farm_uid=farm_uid,
    )
    if _skill_result_failed_or_needs_clarify(result):
        decision = _failed_pending_plan_step_decision(
            farm_id=farm_id,
            plan=plan,
            step=step,
            params=params,
            result=result,
            session_id=session_id,
        )
        return decision, None, None

    result_reply = _skill_result_reply(result)
    _mark_pending_plan_step_executed(plan.plan_id, step.step_index, result_reply)
    return (
        None,
        result_reply,
        _cleared_pending_plan_step_metadata(
            step=step,
            alias_metadata=alias_metadata,
            farm_id=farm_id,
            farm_uid=farm_uid,
        ),
    )


async def _execute_pending_plan_step_raw(
    *,
    farm_id: int,
    plan_id: str,
    step: PendingPlanStep,
    params: dict,
    farm_uid: str | None,
):
    try:
        return await _execute_write_skill(
            farm_id=farm_id,
            skill_name=step.tool_name,
            params=params,
            farm_uid=farm_uid,
        )
    except Exception as exc:
        _mark_pending_plan_step_failed(plan_id, step.step_index, str(exc))
        raise


def _failed_pending_plan_step_decision(
    *,
    farm_id: int,
    plan: PendingPlan,
    step: PendingPlanStep,
    params: dict,
    result,
    session_id: str | None,
) -> PendingActionDecision:
    result_reply = _skill_result_reply(result)
    _mark_pending_plan_step_failed(plan.plan_id, step.step_index, result_reply)
    repair_decision = reflect_tool_failure(
        farm_id=farm_id,
        skill_name=step.tool_name,
        params=params,
        result=result,
        repair_attempts=_plan_step_repair_attempts(step),
        original_input=plan.raw_user_input,
        session_id=session_id,
    )
    if repair_decision.action == "ask_repaired_confirmation":
        _store_repaired_plan_step_pending(
            farm_id=farm_id,
            plan=plan,
            step=step,
            repair_decision=repair_decision,
            session_id=session_id,
        )
        return PendingActionDecision.modified(
            reply=(
                f"执行计划第 {step.step_index + 1} 步失败：{result_reply}\n\n"
                f"我已根据失败原因修正待确认参数，请重新确认。\n"
                f"{repair_decision.confirmation_text}"
            ),
            handled=True,
        )
    _clear_runtime_pending_plan_cache(farm_id, session_id)
    return PendingActionDecision.failed(
        f"执行计划第 {step.step_index + 1} 步失败：{result_reply}"
    )


def _cleared_pending_plan_step_metadata(
    *,
    step: PendingPlanStep,
    alias_metadata: dict,
    farm_id: int,
    farm_uid: str | None,
) -> dict:
    cache_groups = _get_metadata_cache_groups(
        step.tool_name,
        farm_id=farm_id,
        farm_uid=farm_uid,
    )
    cleared_groups = _clear_cache_groups(step.tool_name, cache_groups)
    return {
        "step_id": step.step_id,
        "tool_name": step.tool_name,
        "cache_groups_cleared": cleared_groups,
        **alias_metadata,
    }


def _contract_blocked_pending_plan_step(
    *,
    farm_id: int,
    plan: PendingPlan,
    step: PendingPlanStep,
    params: dict,
    session_id: str | None,
) -> PendingActionDecision | None:
    validation = validate_pending_tool_args(
        skill_name=step.tool_name,
        params=params,
        farm_id=farm_id,
    )
    step.params.clear()
    step.params.update(validation.params)
    if validation.valid:
        return None
    _mark_pending_plan_step_failed(plan.plan_id, step.step_index, validation.message)
    get_collector().record(
        node_type="skill_call",
        node_name=step.tool_name,
        input_data=step.params,
        output_data={
            "status": "contract_blocked",
            "phase": "confirm_pending_plan",
            "plan_id": plan.plan_id,
            "step_id": step.step_id,
            "session_id": session_id,
            "contract_validation": validation.trace_payload(),
        },
        duration_ms=0,
    )
    return PendingActionDecision.modified(
        reply=f"执行计划第 {step.step_index + 1} 步前参数不完整：{validation.message}",
        handled=True,
    )


def _plan_step_repair_attempts(step: PendingPlanStep) -> int:
    payload = step.error_payload or {}
    try:
        return int(payload.get("repair_attempts") or 0)
    except (TypeError, ValueError):
        return 0


def _store_repaired_plan_step_pending(
    *,
    farm_id: int,
    plan: PendingPlan,
    step: PendingPlanStep,
    repair_decision,
    session_id: str | None,
) -> None:
    repaired_params = repair_decision.repaired_params or {}
    _clear_runtime_pending_plan_cache(farm_id, session_id)
    store_pending(
        farm_id,
        step.tool_name,
        repaired_params,
        original_input=plan.raw_user_input,
        confirmation_context=build_confirmation_context(
            step.tool_name,
            repaired_params,
            original_input=plan.raw_user_input,
        ),
        session_id=session_id,
        repair_attempts=repair_decision.repair_attempts,
        metadata={
            "source_plan_id": plan.plan_id,
            "source_step_id": step.step_id,
            "tool_failure_repair": repair_decision.trace_payload(),
        },
    )


def _mark_pending_plan_step_executed(
    plan_id: str,
    step_index: int,
    result: str,
) -> None:
    db = SessionLocal()
    try:
        mark_step_executed(
            db,
            plan_id=plan_id,
            step_index=step_index,
            result={"message": result},
        )
    finally:
        db.close()


def _mark_pending_plan_step_failed(
    plan_id: str,
    step_index: int,
    error_message: str,
) -> None:
    db = SessionLocal()
    try:
        mark_step_failed(
            db,
            plan_id=plan_id,
            step_index=step_index,
            error_message=error_message,
        )
    finally:
        db.close()


def _clear_runtime_pending_plan_cache(
    farm_id: int,
    session_id: str | None,
) -> None:
    _pending.pop((farm_id, session_id or None), None)
    _pending_plans.pop((farm_id, session_id or None), None)


def _cancel_pending_plan(
    farm_id: int,
    session_id: str | None,
) -> None:
    db = SessionLocal()
    try:
        cancel_active_plan(db, farm_id=farm_id, session_id=session_id)
    finally:
        db.close()
    _clear_runtime_pending_plan_cache(farm_id, session_id)


def _normalize_pending_plan_step_params(tool_name: str, params: dict) -> dict:
    """把历史 pending plan 参数转换为对应 skill schema 可接受的形态。"""
    normalized = dict(params or {})
    alias_metadata = pending_alias_metadata(tool_name, normalized)
    if alias_metadata.get("resolved_operation") == "create_work_order":
        for key in ("workers", "unit_names"):
            if isinstance(normalized.get(key), list):
                normalized[key] = ",".join(str(item) for item in normalized[key])
    return normalized


async def handle_pending_action(
    *,
    farm_id: int,
    message: str,
    farm_uid: str | None = None,
    session_id: str | None = None,
) -> PendingActionDecision:
    """根据用户消息处理当前农场的 pending action。"""
    pending = get_pending(farm_id, session_id=session_id)
    pending_plan = (
        None
        if pending is not None
        else get_pending_plan(farm_id, session_id=session_id)
    )
    if pending_plan is not None:
        try:
            intent = detect_user_intent(message)
            if intent == "confirm":
                logger.info(
                    "用户确认执行 pending plan | farm=%s plan=%s steps=%d",
                    farm_id,
                    pending_plan.plan_id,
                    len(pending_plan.steps),
                )
                return await _confirm_pending_plan(
                    farm_id,
                    pending_plan,
                    farm_uid=farm_uid,
                    session_id=session_id,
                )

            if intent == "cancel":
                _cancel_pending_plan(farm_id, session_id)
                return PendingActionDecision.canceled()

            confirm = build_plan_confirm_message(pending_plan.steps)
            reply = f"当前有一条待确认计划，还没有执行。\n{confirm}"
            return PendingActionDecision.modified(reply=reply, handled=True)
        except Exception as exc:
            logger.exception("执行 pending plan 失败")
            _clear_runtime_pending_plan_cache(farm_id, session_id)
            return PendingActionDecision.failed(f"执行失败：{exc}")

    if pending is None:
        return PendingActionDecision.unhandled()

    try:
        intent = detect_user_intent(message)
        if intent == "confirm":
            logger.info(
                "用户确认执行 | farm=%s skill=%s params=%s",
                farm_id,
                pending.skill_name,
                pending.params,
            )
            return await _confirm_pending(
                farm_id,
                pending,
                farm_uid=farm_uid,
                session_id=session_id,
            )

        if intent == "cancel":
            remove_pending(farm_id, session_id=session_id)
            return PendingActionDecision.canceled()

        if _is_clear_pending_correction(message):
            return PendingActionDecision.modified()

        confirm = build_confirm_message(
            pending.skill_name,
            pending.params,
            original_input=pending.original_input,
        )
        reply = f"当前有一条待确认操作，还没有执行。\n{confirm}"
        return PendingActionDecision.modified(reply=reply, handled=True)
    except Exception as exc:
        logger.exception("执行 pending action 失败")
        remove_pending(farm_id, session_id=session_id)
        return PendingActionDecision.failed(f"执行失败：{exc}")


__all__ = ["handle_pending_action"]
