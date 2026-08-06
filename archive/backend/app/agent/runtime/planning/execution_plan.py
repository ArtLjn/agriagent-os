"""PlanIR 到 runtime ExecutionPlan/PendingPlan 的 adapter。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.agent.task_graph.models import PlanIR, PlanIRStep
from app.skills.registry import SkillRegistry, load_skill_registry


@dataclass(frozen=True)
class ExecutionStep:
    """Runtime 可执行的单步计划合同。"""

    step_id: str
    capability: str
    operation: str
    skill_name: str
    params: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    side_effect: str = "none"

    def to_trace_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionPlan:
    """PlanIR 编译后的 runtime 执行合同。"""

    plan_id: str
    source_ir_id: str
    task_type: str
    steps: list[ExecutionStep]
    validation_version: str = "execution-plan-v1"

    def to_trace_payload(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionPlanCompileError(ValueError):
    """PlanIR 无法安全编译为 ExecutionPlan。"""

    def __init__(self, issues: list[dict[str, Any]]) -> None:
        self.issues = issues
        self.codes = [str(issue["code"]) for issue in issues]
        super().__init__(", ".join(self.codes))


def compile_plan_ir_to_execution_plan(
    plan_ir: PlanIR,
    *,
    registry: SkillRegistry | None = None,
) -> ExecutionPlan:
    """把 PlanIR 编译为 runtime ExecutionPlan，未知能力 fail-closed。"""
    skill_registry = registry or load_skill_registry()
    issues: list[dict[str, Any]] = []
    steps: list[ExecutionStep] = []
    for step in plan_ir.steps:
        compiled_step = _compile_step(step, skill_registry, issues)
        if compiled_step is not None:
            steps.append(compiled_step)
    if issues:
        raise ExecutionPlanCompileError(issues)
    return ExecutionPlan(
        plan_id=f"ep-{plan_ir.ir_id}",
        source_ir_id=plan_ir.ir_id,
        task_type=str(plan_ir.task_type),
        steps=steps,
    )


def pending_steps_from_execution_plan(plan: ExecutionPlan) -> list[dict[str, Any]]:
    """把 ExecutionPlan 投影成 pending_plan_service 可存储的 steps。"""
    steps: list[dict[str, Any]] = []
    for step in plan.steps:
        if step.side_effect not in {"write", "pending_only"}:
            continue
        if not step.requires_confirmation:
            raise ExecutionPlanCompileError(
                [
                    _issue(
                        "write_requires_confirmation",
                        "写操作必须进入 pending confirmation",
                        step.step_id,
                    )
                ]
            )
        steps.append(
            {
                "step_id": step.step_id,
                "tool_name": step.skill_name,
                "params": dict(step.params),
                "depends_on": list(step.depends_on),
            }
        )
    return steps


def _compile_step(
    step: PlanIRStep,
    registry: SkillRegistry,
    issues: list[dict[str, Any]],
) -> ExecutionStep | None:
    if step.capability is None:
        if step.side_effect == "none":
            return None
        issues.append(
            _issue("missing_capability", "写步骤缺少 capability", step.step_id)
        )
        return None

    capability = registry.capabilities.get(step.capability)
    if capability is None:
        issues.append(
            _issue(
                "unknown_capability",
                f"未知 capability: {step.capability}",
                step.step_id,
            )
        )
        return None

    operation_name = _operation_name(step)
    if not operation_name:
        issues.append(_issue("missing_operation", "步骤缺少 operation", step.step_id))
        return None

    operation = capability.operations.get(operation_name)
    if operation is None:
        issues.append(
            _issue(
                "unknown_operation",
                f"{step.capability} 不存在 operation: {operation_name}",
                step.step_id,
            )
        )
        return None

    transformed_args, binding_issues = _transform_runtime_bindings(
        step.args, step.step_id
    )
    issues.extend(binding_issues)
    if binding_issues:
        return None

    side_effect = _side_effect_for_step(step, operation.risk, operation.side_effect)
    requires_confirmation = _requires_confirmation(
        step, side_effect, operation.requires_confirmation
    )
    if requires_confirmation and not _has_confirmation_gate(step):
        issues.append(
            _issue(
                "write_requires_confirmation",
                "写步骤必须显式进入 approval/pending confirmation",
                step.step_id,
            )
        )
        return None

    return ExecutionStep(
        step_id=step.step_id,
        capability=capability.name,
        operation=operation.name,
        skill_name=capability.name,
        params=transformed_args,
        depends_on=list(step.needs),
        requires_confirmation=requires_confirmation,
        side_effect=side_effect,
    )


def _operation_name(step: PlanIRStep) -> str:
    return str(step.args.get("operation") or "").strip()


def _side_effect_for_step(
    step: PlanIRStep,
    risk: str,
    operation_side_effect: str,
) -> str:
    if step.side_effect in {"write", "pending_only"}:
        return step.side_effect
    if operation_side_effect in {"write", "pending_only"}:
        return operation_side_effect
    if risk in {"write_confirm", "write_high"}:
        return "pending_only"
    return "none"


def _requires_confirmation(
    step: PlanIRStep,
    side_effect: str,
    operation_requires_confirmation: bool,
) -> bool:
    return side_effect in {"write", "pending_only"} or operation_requires_confirmation


def _has_confirmation_gate(step: PlanIRStep) -> bool:
    return step.op == "approval" or step.side_effect == "pending_only"


def _transform_runtime_bindings(
    value: Any,
    step_id: str,
) -> tuple[Any, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    transformed = _transform_runtime_binding_value(value, step_id, issues)
    return transformed, issues


def _transform_runtime_binding_value(
    value: Any,
    step_id: str,
    issues: list[dict[str, Any]],
) -> Any:
    if isinstance(value, dict):
        return {
            key: _transform_runtime_binding_value(item, step_id, issues)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _transform_runtime_binding_value(item, step_id, issues) for item in value
        ]
    if isinstance(value, str) and value.startswith("$steps."):
        binding = _runtime_binding_from_string(value)
        if binding is None:
            issues.append(
                _issue(
                    "invalid_step_binding",
                    f"无法解析步骤输出绑定: {value}",
                    step_id,
                )
            )
            return value
        return binding
    return value


def _runtime_binding_from_string(value: str) -> dict[str, str] | None:
    parts = value.removeprefix("$steps.").split(".")
    if len(parts) < 2 or not parts[0] or not all(parts[1:]):
        return None
    return {"$from_step": parts[0], "path": ".".join(parts[1:])}


def _issue(code: str, message: str, step_id: str | None) -> dict[str, Any]:
    return {"code": code, "message": message, "step_id": step_id}


__all__ = [
    "ExecutionPlan",
    "ExecutionPlanCompileError",
    "ExecutionStep",
    "compile_plan_ir_to_execution_plan",
    "pending_steps_from_execution_plan",
]
