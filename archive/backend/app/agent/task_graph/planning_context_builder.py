"""Task Graph 规划上下文构建。"""

from __future__ import annotations

from app.agent.task_graph.models import (
    PlanningContext,
    PlanningSlotSet,
    RawContext,
    TaskType,
)


def build_planning_context(
    *,
    user_input: str,
    raw_context: RawContext,
    task_type: TaskType,
    slots: PlanningSlotSet,
) -> PlanningContext:
    recent_task_refs = [str(ref) for ref in raw_context.runtime_refs if ref]
    return PlanningContext(
        request_id=raw_context.request_id,
        session_id=raw_context.session_id,
        user_id=raw_context.user_id,
        task_type=task_type,
        slots=slots,
        context_summary={
            "task_type": task_type,
            "input_preview": user_input[:120],
            "last_failed_task_graph_id": recent_task_refs[0]
            if recent_task_refs
            else None,
        },
        recent_task_refs=recent_task_refs,
        facts=dict(slots.slots),
        constraints=["planner_consumes_structured_context_only"],
        risk_policy={
            "no_direct_write": True,
            "write_requires_pending_confirmation": True,
        },
    )
