"""Pending 执行中缺作物模板的续接策略。"""

import re

from app.agent.executor.models import PendingActionDecision
from app.infra.pending_actions import (
    PendingAction,
    PendingPlan,
    PendingPlanStep,
    build_confirm_message,
    store_pending,
)

_MISSING_TEMPLATE_RE = re.compile(r"系统还没有\s*(?P<crop>.+?)\s*模板")
_CROP_CYCLE_TOOLS = {"create_crop_cycle", "manage_crop_cycle"}


def missing_template_follow_up_decision(
    *,
    farm_id: int,
    pending: PendingAction,
    reply: str,
    metadata: dict,
    session_id: str | None,
    follow_up_params: dict,
) -> PendingActionDecision | None:
    if not _is_crop_cycle_missing_template(pending.skill_name, reply):
        return None

    crop_name = _extract_missing_template_crop(follow_up_params, reply)
    if not crop_name:
        return None

    _store_template_pending(
        farm_id=farm_id,
        crop_name=crop_name,
        follow_up_skill_name="create_crop_cycle",
        follow_up_params=follow_up_params,
        follow_up_original_input=pending.original_input,
        session_id=session_id,
    )
    confirm = _template_confirm(crop_name)
    reply = f"系统还没有{crop_name}作物模板。创建茬口前需要先创建模板。\n{confirm}"
    return PendingActionDecision.confirmed(reply, metadata=metadata)


def missing_template_pending_plan_step_decision(
    *,
    farm_id: int,
    plan: PendingPlan,
    step: PendingPlanStep,
    params: dict,
    result_reply: str,
    session_id: str | None,
) -> PendingActionDecision | None:
    if not _is_crop_cycle_missing_template(step.tool_name, result_reply):
        return None

    crop_name = _extract_missing_template_crop(params, result_reply)
    if not crop_name:
        return None

    _store_template_pending(
        farm_id=farm_id,
        crop_name=crop_name,
        follow_up_skill_name=step.tool_name,
        follow_up_params=params,
        follow_up_original_input=plan.raw_user_input,
        session_id=session_id,
    )
    confirm = _template_confirm(crop_name)
    reply = (
        f"执行计划第 {step.step_index + 1} 步失败：系统还没有{crop_name}作物模板。"
        f"创建茬口前需要先创建模板。\n{confirm}"
    )
    return PendingActionDecision.confirmed(reply)


def _is_crop_cycle_missing_template(skill_name: str, reply: str) -> bool:
    return (
        skill_name in _CROP_CYCLE_TOOLS and "系统还没有" in reply and "模板" in reply
    )


def _extract_missing_template_crop(params: dict, result: str) -> str:
    crop_name = str(params.get("crop_name") or "").strip()
    if crop_name:
        return crop_name

    match = _MISSING_TEMPLATE_RE.search(result)
    return match.group("crop").strip() if match else ""


def _store_template_pending(
    *,
    farm_id: int,
    crop_name: str,
    follow_up_skill_name: str,
    follow_up_params: dict,
    follow_up_original_input: str | None,
    session_id: str | None,
) -> None:
    store_pending(
        farm_id,
        "manage_crop_templates",
        {"operation": "create_template", "crop_name": crop_name},
        original_input=f"系统还没有{crop_name}作物模板",
        follow_up_skill_name=follow_up_skill_name,
        follow_up_params=dict(follow_up_params),
        follow_up_original_input=follow_up_original_input,
        session_id=session_id,
    )


def _template_confirm(crop_name: str) -> str:
    return build_confirm_message(
        "manage_crop_templates",
        {"operation": "create_template", "crop_name": crop_name},
        original_input=f"系统还没有{crop_name}作物模板",
    )
