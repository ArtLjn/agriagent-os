"""Task Graph 编译器测试。"""

import pytest

from app.agent.task_graph.compiler import GraphCompileError, compile_plan_ir
from app.agent.task_graph.plan_ir import create_plan_ir

pytestmark = pytest.mark.no_db


def test_compile_plan_ir_maps_ops_and_binds_capability_contracts() -> None:
    plan = create_plan_ir(
        ir_id="ir-1",
        task_type="planting_plan",
        intent="plan_crop_cycle",
        planner_version="planner.v1",
        context_hash="ctx-1",
        response_contract="PlantingPlanResponse",
        steps=[
            {"step_id": "farm", "op": "query", "capability": "QueryFarmStatus"},
            {"step_id": "template", "op": "query", "capability": "QueryCropTemplate"},
            {
                "step_id": "layout",
                "op": "calculate",
                "capability": "CalculatePlantingLayout",
                "needs": ["template"],
            },
            {
                "step_id": "parallel_gate",
                "op": "parallel",
                "needs": ["farm", "template"],
            },
            {
                "step_id": "response",
                "op": "synthesize",
                "capability": "SynthesizePlantingPlan",
                "needs": ["layout"],
            },
            {
                "step_id": "approval",
                "op": "approval",
                "capability": "ProposeCreateCyclePlan",
                "needs": ["response"],
                "side_effect": "pending_only",
            },
            {"step_id": "merge", "op": "merge", "needs": ["parallel_gate", "approval"]},
            {"step_id": "wait", "op": "wait", "needs": ["merge"]},
            {"step_id": "branch", "op": "branch", "needs": ["wait"]},
        ],
    )

    result = compile_plan_ir(plan)

    operators = {node.node_id: node.invocation.operator for node in result.graph.nodes}
    assert operators == {
        "farm": "CAPABILITY",
        "template": "CAPABILITY",
        "layout": "CAPABILITY",
        "parallel_gate": "PARALLEL",
        "response": "CAPABILITY",
        "approval": "APPROVAL",
        "merge": "MERGE",
        "wait": "WAIT",
        "branch": "IF",
    }
    approval = next(node for node in result.graph.nodes if node.node_id == "approval")
    assert approval.contract.side_effect == "pending_only"
    assert approval.invocation.capability_invocation is not None
    assert approval.invocation.capability_invocation.adapter_hint == "pending_plan"


def test_compile_plan_ir_rejects_unknown_capability() -> None:
    plan = create_plan_ir(
        ir_id="ir-1",
        task_type="planting_plan",
        intent="plan_crop_cycle",
        planner_version="planner.v1",
        context_hash="ctx-1",
        response_contract="PlantingPlanResponse",
        steps=[{"step_id": "x", "op": "query", "capability": "MissingCapability"}],
    )

    with pytest.raises(GraphCompileError) as exc_info:
        compile_plan_ir(plan)

    assert "unknown_capability" in exc_info.value.codes


def test_compile_plan_ir_rejects_cycles() -> None:
    plan = create_plan_ir(
        ir_id="ir-1",
        task_type="planting_plan",
        intent="plan_crop_cycle",
        planner_version="planner.v1",
        context_hash="ctx-1",
        response_contract="PlantingPlanResponse",
        steps=[
            {
                "step_id": "a",
                "op": "query",
                "capability": "QueryFarmStatus",
                "needs": ["c"],
            },
            {
                "step_id": "b",
                "op": "query",
                "capability": "QueryActiveCycles",
                "needs": ["a"],
            },
            {
                "step_id": "c",
                "op": "query",
                "capability": "QueryPlantingUnits",
                "needs": ["b"],
            },
        ],
    )

    with pytest.raises(GraphCompileError) as exc_info:
        compile_plan_ir(plan)

    assert "cyclic_graph" in exc_info.value.codes


def test_compile_plan_ir_rejects_missing_input_contract() -> None:
    plan = create_plan_ir(
        ir_id="ir-1",
        task_type="planting_plan",
        intent="plan_crop_cycle",
        planner_version="planner.v1",
        context_hash="ctx-1",
        response_contract="PlantingPlanResponse",
        steps=[
            {
                "step_id": "layout",
                "op": "calculate",
                "capability": "CalculatePlantingLayout",
            },
        ],
    )

    with pytest.raises(GraphCompileError) as exc_info:
        compile_plan_ir(plan)

    assert "missing_input_contract" in exc_info.value.codes
