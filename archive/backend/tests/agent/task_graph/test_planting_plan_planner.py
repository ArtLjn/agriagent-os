"""planting_plan 垂直切片规划测试。"""

import pytest

from app.agent.task_graph.tasks.planting_plan import plan_planting_request

pytestmark = pytest.mark.no_db


def _capabilities(decision) -> list[str]:
    return [
        step.capability
        for step in decision.plan_ir.steps
        if step.capability is not None
    ]


def test_plan_planting_request_outputs_compilable_plan_ir_without_cost() -> None:
    decision = plan_planting_request(
        "我在太仓新租了30亩地 每块地1.5亩 帮我规划下茬口，秋季草莓",
        request_id="req-1",
        session_id="sess-1",
        user_id="user-1",
    )

    assert decision.task_type == "planting_plan"
    assert decision.required_slot_questions == []
    assert decision.plan_ir.task_type == "planting_plan"
    assert decision.compile_result.graph.source_ir_id == decision.plan_ir.ir_id
    assert _capabilities(decision) == [
        "QueryCropTemplate",
        "QueryWeatherForecast",
        "CalculatePlantingLayout",
        "SynthesizePlantingPlan",
    ]
    layout_step = next(
        step for step in decision.plan_ir.steps if step.step_id == "layout"
    )
    assert layout_step.args["total_area_mu"] == 30
    assert layout_step.args["unit_area_mu"] == 1.5
    assert set(layout_step.needs) == {"crop_template", "weather_window"}
    assert "AnalyzeCost" not in _capabilities(decision)


def test_plan_planting_request_asks_required_slots_when_incomplete() -> None:
    decision = plan_planting_request("帮我规划下茬口", request_id="req-2")

    assert decision.task_type == "planting_plan"
    assert {"crop", "season", "total_area_mu"}.issubset(
        set(decision.plan_ir.steps[0].args["missing_slots"])
    )
    assert len(decision.required_slot_questions) >= 3
    assert decision.plan_ir.response_contract == "PlantingPlanResponse"
    assert decision.plan_ir.steps[0].capability == "SynthesizeRequiredSlotQuestions"
    assert decision.compile_result.graph.nodes[0].contract.input_types == [
        "PlanningContext"
    ]
    assert decision.compile_result.graph.nodes[0].contract.output_type == (
        "PlantingPlanResponse"
    )
    assert decision.compile_result.graph.nodes[0].node_id == "response"


def test_plan_planting_request_adds_cost_only_when_user_mentions_cost() -> None:
    decision = plan_planting_request(
        "我在太仓新租了30亩地 每块地1.5亩 帮我规划下茬口，秋季草莓，顺便估算成本",
        request_id="req-3",
    )

    assert "AnalyzeCost" in _capabilities(decision)
    cost_step = next(
        step for step in decision.plan_ir.steps if step.capability == "AnalyzeCost"
    )
    response_step = next(
        step
        for step in decision.plan_ir.steps
        if step.capability == "SynthesizePlantingPlan"
    )
    assert cost_step.needs == ["layout"]
    assert "cost_analysis" in response_step.needs
