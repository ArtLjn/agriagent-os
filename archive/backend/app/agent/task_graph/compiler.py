"""Plan IR 到 Contract Task Graph 的编译器。"""

from __future__ import annotations

from typing import Any

from app.agent.task_graph.capabilities.catalog import (
    CapabilityDefinition,
    get_capability,
)
from app.agent.task_graph.models import (
    CapabilityInvocation,
    CompileResult,
    NodeContract,
    OperatorInvocation,
    OperatorType,
    PlanIR,
    PlanIRStep,
    TaskGraph,
    TaskGraphNode,
)
from app.agent.task_graph.plan_ir import validate_plan_ir

OPERATOR_BY_IR_OP: dict[str, OperatorType] = {
    "query": "CAPABILITY",
    "calculate": "CAPABILITY",
    "synthesize": "CAPABILITY",
    "approval": "APPROVAL",
    "branch": "IF",
    "parallel": "PARALLEL",
    "wait": "WAIT",
    "merge": "MERGE",
}


class GraphCompileError(ValueError):
    def __init__(self, issues: list[dict[str, Any]]) -> None:
        self.issues = issues
        self.codes = [issue["code"] for issue in issues]
        super().__init__(", ".join(self.codes))


def compile_plan_ir(plan_ir: PlanIR) -> CompileResult:
    issues = validate_plan_ir(plan_ir)
    issues.extend(_validate_capabilities(plan_ir))
    issues.extend(_validate_dag(plan_ir))
    issues.extend(_validate_contract_inputs(plan_ir))
    if issues:
        raise GraphCompileError(issues)

    nodes = [_compile_step(step) for step in plan_ir.steps]
    graph = TaskGraph(
        graph_id=f"graph:{plan_ir.ir_id}",
        source_ir_id=plan_ir.ir_id,
        task_type=plan_ir.task_type,
        planner_version=plan_ir.planner_version,
        context_hash=plan_ir.context_hash,
        nodes=nodes,
        response_contract=plan_ir.response_contract,
    )
    return CompileResult(ir_id=plan_ir.ir_id, graph=graph)


def _compile_step(step: PlanIRStep) -> TaskGraphNode:
    operator = OPERATOR_BY_IR_OP[step.op]
    capability = get_capability(step.capability) if step.capability else None
    contract = _contract_for_step(step, capability)
    capability_invocation = (
        CapabilityInvocation(
            capability=capability.name,
            operation=step.op,
            args=step.args,
            adapter_hint=capability.adapter_hint,
        )
        if capability is not None
        else None
    )
    invocation = OperatorInvocation(
        operator=operator,
        args=_operator_args(step),
        capability_invocation=capability_invocation,
    )
    return TaskGraphNode(
        node_id=step.step_id,
        label=step.capability or step.op,
        source_ir_step_id=step.step_id,
        invocation=invocation,
        contract=contract,
        depends_on=step.needs,
        optional=step.optional,
    )


def _contract_for_step(
    step: PlanIRStep, capability: CapabilityDefinition | None
) -> NodeContract:
    if capability is not None:
        contract = capability.contract.model_copy(deep=True)
        if step.side_effect != "none":
            contract = contract.model_copy(update={"side_effect": step.side_effect})
        return contract
    return NodeContract(
        input_types=[],
        output_type=f"{step.op.title()}Result",
        side_effect=step.side_effect,
        failure_policy="repair",
    )


def _operator_args(step: PlanIRStep) -> dict[str, Any]:
    args = dict(step.args)
    if step.when:
        args["when"] = step.when
    return args


def _validate_capabilities(plan_ir: PlanIR) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for step in plan_ir.steps:
        if OPERATOR_BY_IR_OP.get(step.op) == "CAPABILITY" and not step.capability:
            issues.append(
                _issue(
                    "missing_capability",
                    f"{step.step_id} 缺少 capability",
                    step.step_id,
                )
            )
            continue
        if step.capability is None:
            continue
        capability = get_capability(step.capability)
        if capability is None:
            issues.append(
                _issue(
                    "unknown_capability",
                    f"未知 capability: {step.capability}",
                    step.step_id,
                )
            )
            continue
        if capability.side_effect == "pending_only" and step.op != "approval":
            issues.append(
                _issue(
                    "write_requires_approval",
                    f"{step.capability} 是写意图能力，必须通过 approval op 编译。",
                    step.step_id,
                )
            )
        if step.side_effect == "write":
            issues.append(
                _issue("unsafe_write", f"{step.step_id} 禁止直接 write", step.step_id)
            )
        if (
            capability.side_effect == "pending_only"
            and step.side_effect != "pending_only"
        ):
            issues.append(
                _issue(
                    "pending_capability_requires_pending_only",
                    f"{step.capability} 必须声明 side_effect=pending_only。",
                    step.step_id,
                )
            )
    return issues


def _validate_dag(plan_ir: PlanIR) -> list[dict[str, Any]]:
    node_ids = {step.step_id for step in plan_ir.steps}
    graph = {
        step.step_id: [dep for dep in step.needs if dep in node_ids]
        for step in plan_ir.steps
    }
    visited: set[str] = set()
    visiting: set[str] = set()
    issues: list[dict[str, Any]] = []

    def visit(node_id: str) -> None:
        if node_id in visited or issues:
            return
        if node_id in visiting:
            issues.append(_issue("cyclic_graph", f"图中存在环: {node_id}", node_id))
            return
        visiting.add(node_id)
        for dependency in graph[node_id]:
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)

    for step_id in graph:
        visit(step_id)
    return issues


def _validate_contract_inputs(plan_ir: PlanIR) -> list[dict[str, Any]]:
    output_by_step = _output_types_by_step(plan_ir)
    issues: list[dict[str, Any]] = []
    for step in plan_ir.steps:
        capability = get_capability(step.capability) if step.capability else None
        if capability is None:
            continue
        available_inputs = {"PlanningContext", "PlanningSlotSet"}
        available_inputs.update(
            output_by_step[dependency]
            for dependency in step.needs
            if dependency in output_by_step
        )
        missing_inputs = [
            input_type
            for input_type in capability.contract.input_types
            if input_type not in available_inputs
        ]
        if missing_inputs:
            issues.append(
                _issue(
                    "missing_input_contract",
                    f"{step.step_id} 缺少输入契约: {', '.join(missing_inputs)}",
                    step.step_id,
                )
            )
    return issues


def _output_types_by_step(plan_ir: PlanIR) -> dict[str, str]:
    output_by_step: dict[str, str] = {}
    for step in plan_ir.steps:
        capability = get_capability(step.capability) if step.capability else None
        if capability is not None:
            output_by_step[step.step_id] = capability.contract.output_type
        else:
            output_by_step[step.step_id] = f"{step.op.title()}Result"
    return output_by_step


def _issue(code: str, message: str, step_id: str | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "step_id": step_id}
