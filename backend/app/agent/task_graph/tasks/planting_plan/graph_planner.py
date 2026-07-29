"""planting_plan Graph Planner。"""

from __future__ import annotations

import hashlib

from app.agent.task_graph.models import PlanIR, PlanningContext
from app.agent.task_graph.plan_ir import create_plan_ir
from app.agent.task_graph.tasks.planting_plan.rules import (
    PLANNER_VERSION,
    user_requested_cost,
    user_requested_create,
)


def build_plan_ir(
    *,
    user_input: str,
    context: PlanningContext,
    missing_slots: list[str],
    required_slot_questions: list[str],
) -> PlanIR:
    context_hash = _context_hash(context)
    if missing_slots:
        return _create_plan(
            context=context,
            intent="ask_required_slots",
            context_hash=context_hash,
            response_contract="PlantingPlanResponse",
            steps=_missing_slot_steps(missing_slots, required_slot_questions),
        )

    return _create_plan(
        context=context,
        intent="plan_crop_cycle",
        context_hash=context_hash,
        response_contract="PlantingPlanResponse",
        steps=_complete_plan_steps(user_input, context),
    )


def _missing_slot_steps(
    missing_slots: list[str], required_slot_questions: list[str]
) -> list[dict[str, object]]:
    return [
        {
            "step_id": "response",
            "op": "synthesize",
            "capability": "SynthesizeRequiredSlotQuestions",
            "args": {
                "missing_slots": missing_slots,
                "required_slot_questions": required_slot_questions,
            },
        }
    ]


def _complete_plan_steps(
    user_input: str, context: PlanningContext
) -> list[dict[str, object]]:
    slots = context.slots.slots
    steps: list[dict[str, object]] = [
        {
            "step_id": "crop_template",
            "op": "query",
            "capability": "QueryCropTemplate",
            "args": {"crop": slots["crop"].value},
        }
    ]
    layout_needs = ["crop_template"]
    _append_weather_step(steps, context, layout_needs)
    steps.append(_layout_step(context, layout_needs))
    response_needs = ["layout"]
    _append_cost_step(steps, user_input, response_needs)
    steps.append(_response_step(response_needs))
    _append_create_approval_step(steps, user_input)
    return steps


def _append_weather_step(
    steps: list[dict[str, object]],
    context: PlanningContext,
    layout_needs: list[str],
) -> None:
    slots = context.slots.slots
    if "location" not in slots:
        return
    steps.append(
        {
            "step_id": "weather_window",
            "op": "query",
            "capability": "QueryWeatherForecast",
            "args": {"location": slots["location"].value},
            "optional": True,
        }
    )
    layout_needs.append("weather_window")


def _layout_step(
    context: PlanningContext, layout_needs: list[str]
) -> dict[str, object]:
    slots = context.slots.slots
    return {
        "step_id": "layout",
        "op": "calculate",
        "capability": "CalculatePlantingLayout",
        "args": {
            "total_area_mu": slots["total_area_mu"].value,
            "unit_area_mu": slots.get("unit_area_mu").value
            if "unit_area_mu" in slots
            else None,
            "unit_count": slots.get("unit_count").value
            if "unit_count" in slots
            else None,
        },
        "needs": layout_needs,
    }


def _append_cost_step(
    steps: list[dict[str, object]], user_input: str, response_needs: list[str]
) -> None:
    if not user_requested_cost(user_input):
        return
    steps.append(
        {
            "step_id": "cost_analysis",
            "op": "calculate",
            "capability": "AnalyzeCost",
            "needs": ["layout"],
        }
    )
    response_needs.append("cost_analysis")


def _response_step(response_needs: list[str]) -> dict[str, object]:
    return {
        "step_id": "response",
        "op": "synthesize",
        "capability": "SynthesizePlantingPlan",
        "needs": response_needs,
    }


def _append_create_approval_step(
    steps: list[dict[str, object]], user_input: str
) -> None:
    if not user_requested_create(user_input):
        return
    steps.append(
        {
            "step_id": "propose_create_cycle_plan",
            "op": "approval",
            "capability": "ProposeCreateCyclePlan",
            "needs": ["response"],
            "side_effect": "pending_only",
        }
    )


def _create_plan(
    *,
    context: PlanningContext,
    intent: str,
    context_hash: str,
    response_contract: str,
    steps: list[dict[str, object]],
) -> PlanIR:
    return create_plan_ir(
        ir_id=f"pir:{context.request_id}",
        task_type="planting_plan",
        intent=intent,
        planner_version=PLANNER_VERSION,
        context_hash=context_hash,
        response_contract=response_contract,
        steps=steps,
    )


def _context_hash(context: PlanningContext) -> str:
    payload = context.to_trace_payload()
    return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()[:16]


def build_planting_plan_ir(
    *,
    planning_context: PlanningContext,
    user_input: str,
    missing_slots: list[str],
    required_slot_questions: list[str],
) -> PlanIR:
    return build_plan_ir(
        user_input=user_input,
        context=planning_context,
        missing_slots=missing_slots,
        required_slot_questions=required_slot_questions,
    )
