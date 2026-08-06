"""Plan IR 创建与校验测试。"""

import pytest

from app.agent.task_graph.models import PlanIR, PlanIRStep
from app.agent.task_graph.plan_ir import (
    PlanIRValidationError,
    create_plan_ir,
    validate_plan_ir,
)

pytestmark = pytest.mark.no_db


def test_create_plan_ir_accepts_valid_dependencies_and_pending_write() -> None:
    plan = create_plan_ir(
        ir_id="ir-1",
        task_type="planting_plan",
        intent="plan_crop_cycle",
        planner_version="planner.v1",
        context_hash="ctx-1",
        response_contract="PlantingPlanResponse",
        steps=[
            {"step_id": "template", "op": "query", "capability": "QueryCropTemplate"},
            {
                "step_id": "create_plan",
                "op": "approval",
                "capability": "ProposeCreateCyclePlan",
                "needs": ["template"],
                "side_effect": "pending_only",
            },
        ],
    )

    issues = validate_plan_ir(plan)

    assert issues == []
    assert plan.steps[1].needs == ["template"]


@pytest.mark.parametrize(
    ("steps", "expected_code"),
    [
        ([{"step_id": "x", "op": "unknown"}], "unknown_op"),
        ([{"op": "query", "capability": "QueryFarmStatus"}], "missing_step_id"),
        (
            [
                {"step_id": "x", "op": "query", "capability": "QueryFarmStatus"},
                {"step_id": "x", "op": "query", "capability": "QueryFarmStatus"},
            ],
            "duplicate_step_id",
        ),
        (
            [
                {
                    "step_id": "x",
                    "op": "query",
                    "capability": "QueryFarmStatus",
                    "needs": ["missing"],
                }
            ],
            "unknown_dependency",
        ),
        (
            [
                {
                    "step_id": "x",
                    "op": "approval",
                    "capability": "ProposeCreateCyclePlan",
                    "side_effect": "write",
                }
            ],
            "unsafe_write",
        ),
    ],
)
def test_create_plan_ir_rejects_invalid_steps(
    steps: list[dict[str, object]], expected_code: str
) -> None:
    with pytest.raises(PlanIRValidationError) as exc_info:
        create_plan_ir(
            ir_id="ir-1",
            task_type="planting_plan",
            intent="plan_crop_cycle",
            planner_version="planner.v1",
            context_hash="ctx-1",
            response_contract="PlantingPlanResponse",
            steps=steps,
        )

    assert expected_code in exc_info.value.codes


def test_validate_plan_ir_reports_invalid_programmatic_mutation() -> None:
    plan = create_plan_ir(
        ir_id="ir-1",
        task_type="planting_plan",
        intent="plan_crop_cycle",
        planner_version="planner.v1",
        context_hash="ctx-1",
        response_contract="PlantingPlanResponse",
        steps=[{"step_id": "x", "op": "query", "capability": "QueryFarmStatus"}],
    )
    plan.steps.append(
        PlanIRStep(
            step_id="y", op="query", capability="QueryFarmStatus", needs=["missing"]
        )
    )

    issues = validate_plan_ir(plan)

    assert [issue["code"] for issue in issues] == ["unknown_dependency"]


def test_validate_plan_ir_rejects_unknown_op_on_materialized_step() -> None:
    plan = PlanIR(
        ir_id="ir-1",
        task_type="planting_plan",
        intent="plan_crop_cycle",
        planner_version="planner.v1",
        context_hash="ctx-1",
        response_contract="PlantingPlanResponse",
        steps=[
            PlanIRStep.model_construct(
                step_id="x",
                op="unknown",
                capability="QueryFarmStatus",
                args={},
                needs=[],
                when=None,
                optional=False,
                side_effect="none",
            )
        ],
    )

    issues = validate_plan_ir(plan)

    assert [issue["code"] for issue in issues] == ["unknown_op"]


def test_validate_plan_ir_rejects_empty_plan() -> None:
    plan = PlanIR(
        ir_id="ir-1",
        task_type="planting_plan",
        intent="plan_crop_cycle",
        planner_version="planner.v1",
        context_hash="ctx-1",
        response_contract="PlantingPlanResponse",
        steps=[],
    )

    issues = validate_plan_ir(plan)

    assert [issue["code"] for issue in issues] == ["empty_plan"]
