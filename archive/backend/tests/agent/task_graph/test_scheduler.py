"""Runtime Scheduler 测试。"""

import pytest

from app.agent.task_graph.compiler import compile_plan_ir
from app.agent.task_graph.plan_ir import create_plan_ir
from app.agent.task_graph.runtime.scheduler import (
    blocked_by_terminal_dependency,
    next_runnable_nodes,
)
from app.agent.task_graph.runtime.state import create_execution_state, start_execution

pytestmark = pytest.mark.no_db


def test_scheduler_returns_same_batch_for_independent_ready_nodes() -> None:
    graph = compile_plan_ir(
        create_plan_ir(
            ir_id="ir-1",
            task_type="planting_plan",
            intent="plan_crop_cycle",
            planner_version="planner.v1",
            context_hash="ctx-1",
            response_contract="PlantingPlanResponse",
            steps=[
                {
                    "step_id": "template",
                    "op": "query",
                    "capability": "QueryCropTemplate",
                },
                {
                    "step_id": "weather",
                    "op": "query",
                    "capability": "QueryWeatherForecast",
                },
                {
                    "step_id": "layout",
                    "op": "calculate",
                    "capability": "CalculatePlantingLayout",
                    "needs": ["template", "weather"],
                },
            ],
        )
    ).graph
    state = start_execution(
        create_execution_state(execution_id="exec-1", graph_id=graph.graph_id)
    )

    first_batch = next_runnable_nodes(graph, state)
    second_batch = next_runnable_nodes(
        graph, state.model_copy(update={"completed_node_ids": ["template", "weather"]})
    )

    assert [node.node_id for node in first_batch] == ["template", "weather"]
    assert [node.node_id for node in second_batch] == ["layout"]


def test_scheduler_ignores_terminal_and_blocked_nodes() -> None:
    graph = compile_plan_ir(
        create_plan_ir(
            ir_id="ir-1",
            task_type="planting_plan",
            intent="plan_crop_cycle",
            planner_version="planner.v1",
            context_hash="ctx-1",
            response_contract="PlantingPlanResponse",
            steps=[
                {
                    "step_id": "template",
                    "op": "query",
                    "capability": "QueryCropTemplate",
                },
                {
                    "step_id": "layout",
                    "op": "calculate",
                    "capability": "CalculatePlantingLayout",
                    "needs": ["template"],
                },
            ],
        )
    ).graph
    created = create_execution_state(execution_id="exec-1", graph_id=graph.graph_id)
    waiting = created.model_copy(
        update={"status": "waiting_user", "waiting_for": "slot"}
    )

    assert [node.node_id for node in next_runnable_nodes(graph, created)] == [
        "template"
    ]
    assert next_runnable_nodes(graph, waiting) == []


def test_scheduler_keeps_unrelated_ready_nodes_when_one_node_failed() -> None:
    graph = compile_plan_ir(
        create_plan_ir(
            ir_id="ir-1",
            task_type="planting_plan",
            intent="plan_crop_cycle",
            planner_version="planner.v1",
            context_hash="ctx-1",
            response_contract="PlantingPlanResponse",
            steps=[
                {
                    "step_id": "template",
                    "op": "query",
                    "capability": "QueryCropTemplate",
                },
                {
                    "step_id": "layout",
                    "op": "calculate",
                    "capability": "CalculatePlantingLayout",
                    "needs": ["template"],
                },
                {
                    "step_id": "weather",
                    "op": "query",
                    "capability": "QueryWeatherForecast",
                },
            ],
        )
    ).graph
    state = start_execution(
        create_execution_state(execution_id="exec-1", graph_id=graph.graph_id)
    ).model_copy(update={"failed_node_ids": ["template"]})

    runnable = next_runnable_nodes(graph, state)

    assert [node.node_id for node in runnable] == ["weather"]


def test_scheduler_reports_downstream_nodes_blocked_by_failed_dependencies() -> None:
    graph = compile_plan_ir(
        create_plan_ir(
            ir_id="ir-1",
            task_type="planting_plan",
            intent="plan_crop_cycle",
            planner_version="planner.v1",
            context_hash="ctx-1",
            response_contract="PlantingPlanResponse",
            steps=[
                {
                    "step_id": "template",
                    "op": "query",
                    "capability": "QueryCropTemplate",
                },
                {
                    "step_id": "layout",
                    "op": "calculate",
                    "capability": "CalculatePlantingLayout",
                    "needs": ["template"],
                },
                {
                    "step_id": "response",
                    "op": "synthesize",
                    "capability": "SynthesizePlantingPlan",
                    "needs": ["layout"],
                },
                {
                    "step_id": "weather",
                    "op": "query",
                    "capability": "QueryWeatherForecast",
                },
            ],
        )
    ).graph
    state = start_execution(
        create_execution_state(execution_id="exec-1", graph_id=graph.graph_id)
    ).model_copy(update={"failed_node_ids": ["template"]})

    blocked = blocked_by_terminal_dependency(graph, state)

    assert [node.node_id for node in blocked] == ["layout", "response"]


def test_scheduler_allows_downstream_when_optional_dependency_is_skipped() -> None:
    graph = compile_plan_ir(
        create_plan_ir(
            ir_id="ir-1",
            task_type="planting_plan",
            intent="plan_crop_cycle",
            planner_version="planner.v1",
            context_hash="ctx-1",
            response_contract="PlantingPlanResponse",
            steps=[
                {
                    "step_id": "template",
                    "op": "query",
                    "capability": "QueryCropTemplate",
                },
                {
                    "step_id": "weather",
                    "op": "query",
                    "capability": "QueryWeatherForecast",
                    "optional": True,
                },
                {
                    "step_id": "layout",
                    "op": "calculate",
                    "capability": "CalculatePlantingLayout",
                    "needs": ["template", "weather"],
                },
            ],
        )
    ).graph
    state = start_execution(
        create_execution_state(execution_id="exec-1", graph_id=graph.graph_id)
    ).model_copy(
        update={"completed_node_ids": ["template"], "skipped_node_ids": ["weather"]}
    )

    assert [node.node_id for node in next_runnable_nodes(graph, state)] == ["layout"]
    assert blocked_by_terminal_dependency(graph, state) == []
