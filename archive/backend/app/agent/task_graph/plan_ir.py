"""Plan IR 创建与静态校验。"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.agent.task_graph.models import PlanIR, PlanIRStep, TaskType

ALLOWED_OPS = {
    "query",
    "calculate",
    "synthesize",
    "branch",
    "parallel",
    "approval",
    "wait",
    "merge",
}


class PlanIRValidationError(ValueError):
    def __init__(self, issues: list[dict[str, Any]]) -> None:
        self.issues = issues
        self.codes = [issue["code"] for issue in issues]
        super().__init__(", ".join(self.codes))


def create_plan_ir(
    *,
    ir_id: str,
    task_type: TaskType,
    intent: str,
    planner_version: str,
    context_hash: str,
    response_contract: str,
    steps: list[PlanIRStep | dict[str, Any]],
) -> PlanIR:
    step_models = _coerce_steps(steps)
    plan_ir = PlanIR(
        ir_id=ir_id,
        task_type=task_type,
        intent=intent,
        planner_version=planner_version,
        context_hash=context_hash,
        response_contract=response_contract,
        steps=step_models,
    )
    issues = validate_plan_ir(plan_ir)
    if issues:
        raise PlanIRValidationError(issues)
    return plan_ir


def validate_plan_ir(plan_ir: PlanIR) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    seen_step_ids: set[str] = set()

    if not plan_ir.steps:
        issues.append(_issue("empty_plan", "Plan IR 至少需要一个步骤"))

    for index, step in enumerate(plan_ir.steps):
        if not step.step_id:
            issues.append(_issue("missing_step_id", f"steps[{index}] 缺少 step_id"))
            continue
        if step.op not in ALLOWED_OPS:
            issues.append(
                _issue(
                    "unknown_op",
                    f"{step.step_id} 使用未知 op: {step.op}",
                    step.step_id,
                )
            )
        if step.step_id in seen_step_ids:
            issues.append(
                _issue(
                    "duplicate_step_id", f"重复 step_id: {step.step_id}", step.step_id
                )
            )
        seen_step_ids.add(step.step_id)

    for step in plan_ir.steps:
        for dependency in step.needs:
            if dependency not in seen_step_ids:
                issues.append(
                    _issue(
                        "unknown_dependency",
                        f"{step.step_id} 依赖未知步骤 {dependency}",
                        step.step_id,
                    )
                )
        if step.side_effect == "write":
            issues.append(
                _issue(
                    "unsafe_write",
                    f"{step.step_id} 是写操作，必须改为 pending_only 并进入审批。",
                    step.step_id,
                )
            )
    return issues


def _coerce_steps(steps: list[PlanIRStep | dict[str, Any]]) -> list[PlanIRStep]:
    coerced: list[PlanIRStep] = []
    issues: list[dict[str, Any]] = []
    for index, raw_step in enumerate(steps):
        if isinstance(raw_step, PlanIRStep):
            coerced.append(raw_step)
            continue
        step_issues: list[dict[str, Any]] = []
        step_id = raw_step.get("step_id")
        op = raw_step.get("op")
        if not step_id:
            step_issues.append(
                _issue("missing_step_id", f"steps[{index}] 缺少 step_id")
            )
        if op not in ALLOWED_OPS:
            step_issues.append(
                _issue(
                    "unknown_op",
                    f"steps[{index}] 使用未知 op: {op}",
                    str(step_id) if step_id else None,
                )
            )
        if step_issues:
            issues.extend(step_issues)
            continue
        try:
            coerced.append(PlanIRStep.model_validate(raw_step))
        except ValidationError as exc:
            issues.append(
                _issue("invalid_step", str(exc), str(step_id) if step_id else None)
            )
    if issues:
        raise PlanIRValidationError(issues)
    return coerced


def _issue(code: str, message: str, step_id: str | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "step_id": step_id}
