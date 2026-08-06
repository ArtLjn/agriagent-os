"""planting_plan Task Planner。"""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.task_graph.compiler import compile_plan_ir
from app.agent.task_graph.models import PlannerDecision, PlanningContext
from app.agent.task_graph.planning_context_builder import build_planning_context
from app.agent.task_graph.raw_context_builder import build_raw_context
from app.agent.task_graph.slot_extractor import extract_planting_plan_slots
from app.agent.task_graph.tasks.planting_plan.execution_planner import (
    apply_execution_policy,
)
from app.agent.task_graph.tasks.planting_plan.graph_planner import (
    build_planting_plan_ir,
)
from app.agent.task_graph.tasks.planting_plan.rules import (
    REQUIRED_SLOTS,
    RULE_PLANNER_VERSION,
    required_slot_questions,
)


@dataclass(frozen=True)
class PlantingTaskPlan:
    missing_slots: list[str]
    required_slot_questions: list[str]

    @property
    def is_complete(self) -> bool:
        return not self.missing_slots


def plan_task(context: PlanningContext) -> PlantingTaskPlan:
    missing = [
        slot
        for slot in REQUIRED_SLOTS
        if slot not in context.slots.slots
        or context.slots.slots[slot].value in (None, "")
    ]
    return PlantingTaskPlan(
        missing_slots=missing,
        required_slot_questions=required_slot_questions(missing),
    )


def plan_planting_request(
    user_input: str,
    request_id: str,
    session_id: str | None = None,
    user_id: str | None = None,
    last_failed_task_graph_id: str | None = None,
) -> PlannerDecision:
    slots = extract_planting_plan_slots(user_input)
    raw_context = build_raw_context(
        user_input=user_input,
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        last_failed_task_graph_id=last_failed_task_graph_id,
    )
    planning_context = build_planning_context(
        user_input=user_input,
        raw_context=raw_context,
        task_type="planting_plan",
        slots=slots,
    )
    task_plan = plan_task(planning_context)
    plan_ir = build_planting_plan_ir(
        planning_context=planning_context,
        user_input=user_input,
        missing_slots=task_plan.missing_slots,
        required_slot_questions=task_plan.required_slot_questions,
    )
    hinted_plan_ir = apply_execution_policy(plan_ir)
    compile_result = compile_plan_ir(hinted_plan_ir)
    return PlannerDecision(
        task_type="planting_plan",
        rule_planner_version=RULE_PLANNER_VERSION,
        plan_ir=hinted_plan_ir,
        compile_result=compile_result,
        required_slot_questions=task_plan.required_slot_questions,
        hard_constraints_applied=planning_context.constraints,
        llm_used_for=[],
    )
