"""planting_plan Execution Planner。"""

from __future__ import annotations

from app.agent.task_graph.models import PlanIR


def apply_execution_policy(plan_ir: PlanIR) -> PlanIR:
    """第一阶段只在 Plan IR args 中表达最小执行提示。"""

    hinted_plan = plan_ir.model_copy(deep=True)
    for step in hinted_plan.steps:
        hints = {"retry_policy": {"max_attempts": 2}}
        if step.optional:
            hints = {
                "failure_policy": "skip",
                "retry_policy": {"max_attempts": 1},
            }
        if step.step_id == "response":
            hints["checkpoint"] = "before_user_visible_response"
        step.args = {**step.args, "execution_hints": hints}
    return hinted_plan
