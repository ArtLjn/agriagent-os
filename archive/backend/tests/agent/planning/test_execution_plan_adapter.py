"""PlanIR 到 ExecutionPlan/PendingPlanStep 的 adapter 测试。"""

import pytest

from app.agent.runtime.planning.execution_plan import (
    ExecutionPlanCompileError,
    compile_plan_ir_to_execution_plan,
    pending_steps_from_execution_plan,
)
from app.agent.task_graph.models import PlanIR, PlanIRStep

pytestmark = pytest.mark.no_db


def _plan_ir(steps: list[PlanIRStep]) -> PlanIR:
    return PlanIR(
        ir_id="pir-crop-cycle-1",
        task_type="crop_cycle_setup",
        intent="create_crop_cycle",
        planner_version="test-v1",
        context_hash="ctx-1",
        response_contract="pending_plan",
        steps=steps,
    )


def test_compile_crop_cycle_setup_plan_ir_to_execution_plan() -> None:
    plan_ir = _plan_ir(
        [
            PlanIRStep(
                step_id="ensure_template",
                op="approval",
                capability="manage_crop_templates",
                args={
                    "operation": "create_template",
                    "crop_name": "西瓜",
                    "variety": "8424",
                },
                side_effect="write",
            ),
            PlanIRStep(
                step_id="create_cycle",
                op="approval",
                capability="manage_crop_cycle",
                args={
                    "operation": "create_cycle",
                    "crop_name": "西瓜",
                    "variety": "8424",
                    "area": "20",
                },
                needs=["ensure_template"],
                side_effect="write",
            ),
            PlanIRStep(
                step_id="create_unit",
                op="approval",
                capability="manage_planting_units",
                args={
                    "operation": "manage_units",
                    "action": "create",
                    "cycle_id": "$steps.create_cycle.cycle_id",
                    "name": "东棚",
                    "area_mu": 20,
                },
                needs=["create_cycle"],
                optional=True,
                side_effect="write",
            ),
        ]
    )

    execution_plan = compile_plan_ir_to_execution_plan(plan_ir)

    assert execution_plan.plan_id == "ep-pir-crop-cycle-1"
    assert execution_plan.source_ir_id == "pir-crop-cycle-1"
    assert execution_plan.task_type == "crop_cycle_setup"
    assert [step.skill_name for step in execution_plan.steps] == [
        "manage_crop_templates",
        "manage_crop_cycle",
        "manage_planting_units",
    ]
    assert [step.operation for step in execution_plan.steps] == [
        "create_template",
        "create_cycle",
        "manage_units",
    ]
    assert all(step.requires_confirmation for step in execution_plan.steps)
    assert execution_plan.steps[1].depends_on == ["ensure_template"]
    assert execution_plan.steps[2].params["action"] == "create"
    assert execution_plan.steps[2].params["cycle_id"] == {
        "$from_step": "create_cycle",
        "path": "cycle_id",
    }


def test_pending_steps_from_execution_plan_preserves_runtime_contract() -> None:
    execution_plan = compile_plan_ir_to_execution_plan(
        _plan_ir(
            [
                PlanIRStep(
                    step_id="create_cycle",
                    op="approval",
                    capability="manage_crop_cycle",
                    args={"operation": "create_cycle", "crop_name": "西瓜"},
                    side_effect="write",
                )
            ]
        )
    )

    steps = pending_steps_from_execution_plan(execution_plan)

    assert steps == [
        {
            "step_id": "create_cycle",
            "tool_name": "manage_crop_cycle",
            "params": {
                "operation": "create_cycle",
                "crop_name": "西瓜",
            },
            "depends_on": [],
        }
    ]


def test_compile_plan_ir_rejects_unknown_capability_fail_closed() -> None:
    plan_ir = _plan_ir(
        [
            PlanIRStep(
                step_id="unknown",
                op="approval",
                capability="missing_capability",
                args={"operation": "create_cycle"},
                side_effect="write",
            )
        ]
    )

    with pytest.raises(ExecutionPlanCompileError) as exc_info:
        compile_plan_ir_to_execution_plan(plan_ir)

    assert exc_info.value.codes == ["unknown_capability"]


def test_compile_plan_ir_rejects_missing_operation() -> None:
    plan_ir = _plan_ir(
        [
            PlanIRStep(
                step_id="create_cycle",
                op="approval",
                capability="manage_crop_cycle",
                args={"crop_name": "西瓜"},
                side_effect="write",
            )
        ]
    )

    with pytest.raises(ExecutionPlanCompileError) as exc_info:
        compile_plan_ir_to_execution_plan(plan_ir)

    assert exc_info.value.codes == ["missing_operation"]


def test_compile_plan_ir_rejects_unconfirmed_write_step() -> None:
    plan_ir = _plan_ir(
        [
            PlanIRStep(
                step_id="create_cycle",
                op="query",
                capability="manage_crop_cycle",
                args={"operation": "create_cycle", "crop_name": "西瓜"},
                side_effect="write",
            )
        ]
    )

    with pytest.raises(ExecutionPlanCompileError) as exc_info:
        compile_plan_ir_to_execution_plan(plan_ir)

    assert exc_info.value.codes == ["write_requires_confirmation"]


def test_compile_plan_ir_rejects_invalid_step_binding() -> None:
    plan_ir = _plan_ir(
        [
            PlanIRStep(
                step_id="create_unit",
                op="approval",
                capability="manage_planting_units",
                args={
                    "operation": "manage_units",
                    "action": "create",
                    "cycle_id": "$steps.create_cycle",
                    "name": "东棚",
                },
                side_effect="write",
            )
        ]
    )

    with pytest.raises(ExecutionPlanCompileError) as exc_info:
        compile_plan_ir_to_execution_plan(plan_ir)

    assert exc_info.value.codes == ["invalid_step_binding"]
