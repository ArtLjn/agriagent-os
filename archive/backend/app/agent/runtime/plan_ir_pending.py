"""PlanIR pending plan 候选生成。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.agent.runtime.planning import (
    ExecutionPlanCompileError,
    compile_plan_ir_to_execution_plan,
    pending_steps_from_execution_plan,
)
from app.agent.runtime.tool_pending_trace import redact_trace_payload
from app.agent.state import AgentState
from app.agent.task_graph.models import PlanIR
from app.infra.trace_collector import get_collector


@dataclass(frozen=True)
class PlanIRPendingPlanCandidate:
    """PlanIR 已安全编译出的 pending plan 候选。"""

    steps: list[dict[str, Any]]
    router_decision: dict[str, Any]


@dataclass(frozen=True)
class PlanIRPendingPlanBlocked:
    """PlanIR 编译失败后的 fail-closed 结果。"""

    codes: list[str]
    issues: list[dict[str, Any]]


def build_plan_ir_pending_plan_candidate(
    state: AgentState,
) -> PlanIRPendingPlanCandidate | PlanIRPendingPlanBlocked | None:
    """从 runtime state 中的 PlanIR 生成 pending plan 候选。"""
    plan_ir, invalid_issues = _plan_ir_from_state(state)
    if invalid_issues:
        _record_invalid_plan_ir_trace(invalid_issues)
        return PlanIRPendingPlanBlocked(
            codes=[str(issue["code"]) for issue in invalid_issues],
            issues=invalid_issues,
        )
    if plan_ir is None:
        return None
    try:
        execution_plan = compile_plan_ir_to_execution_plan(plan_ir)
        _record_plan_ir_compile_traces(plan_ir, execution_plan.to_trace_payload())
    except ExecutionPlanCompileError as exc:
        _record_plan_ir_compile_traces(plan_ir, None, issues=exc.issues)
        return PlanIRPendingPlanBlocked(codes=exc.codes, issues=exc.issues)

    return PlanIRPendingPlanCandidate(
        steps=pending_steps_from_execution_plan(execution_plan),
        router_decision={
            "source": "plan_ir",
            "plan_ir": plan_ir.to_trace_payload(),
            "execution_plan": execution_plan.to_trace_payload(),
        },
    )


def _plan_ir_from_state(
    state: AgentState,
) -> tuple[PlanIR | None, list[dict[str, Any]]]:
    value = state.get("plan_ir")
    if isinstance(value, PlanIR):
        return value, []
    if isinstance(value, dict):
        try:
            return PlanIR.model_validate(value), []
        except (ValidationError, ValueError, TypeError) as exc:
            return None, [_invalid_plan_ir_issue(exc)]
    return None, []


def _invalid_plan_ir_issue(exc: Exception) -> dict[str, Any]:
    return {
        "code": "invalid_plan_ir",
        "message": str(exc)[:300],
        "step_id": None,
    }


def _record_invalid_plan_ir_trace(issues: list[dict[str, Any]]) -> None:
    get_collector().record(
        node_type="plan",
        node_name="plan.validate",
        input_data={"source": "state.plan_ir"},
        output_data={
            "status": "blocked",
            "issues": redact_trace_payload(issues),
        },
        duration_ms=0,
    )


def _record_plan_ir_compile_traces(
    plan_ir: PlanIR,
    execution_plan_payload: dict | None,
    *,
    issues: list[dict[str, Any]] | None = None,
) -> None:
    collector = get_collector()
    collector.record(
        node_type="planner",
        node_name="planner.generate",
        input_data={"source": "state.plan_ir"},
        output_data={"plan_ir": plan_ir.to_trace_payload()},
        duration_ms=0,
    )
    collector.record(
        node_type="plan",
        node_name="plan.validate",
        input_data={"plan_ir_id": plan_ir.ir_id},
        output_data={
            "status": "blocked" if issues else "valid",
            "issues": redact_trace_payload(issues or []),
        },
        duration_ms=0,
    )
    collector.record(
        node_type="execution_plan",
        node_name="execution_plan.compile",
        input_data={"plan_ir_id": plan_ir.ir_id},
        output_data={
            "status": "blocked" if issues else "compiled",
            "execution_plan": redact_trace_payload(execution_plan_payload or {}),
            "issues": redact_trace_payload(issues or []),
        },
        duration_ms=0,
    )


__all__ = [
    "PlanIRPendingPlanBlocked",
    "PlanIRPendingPlanCandidate",
    "build_plan_ir_pending_plan_candidate",
]
