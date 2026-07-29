"""第一版 Python Capability Catalog。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.agent.task_graph.models import FailurePolicy, NodeContract, SideEffect


class CapabilityDefinition(BaseModel):
    name: str
    description: str
    contract: NodeContract
    side_effect: SideEffect = "none"
    failure_policy: FailurePolicy = "repair"
    adapter_hint: str | None = None

    def to_trace_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


CAPABILITY_CATALOG: dict[str, CapabilityDefinition] = {
    "QueryFarmStatus": CapabilityDefinition(
        name="QueryFarmStatus",
        description="查询用户农场概况。",
        contract=NodeContract(
            input_types=["PlanningContext"],
            output_type="FarmStatus",
            side_effect="none",
            failure_policy="ask_user",
        ),
        adapter_hint="get_farm_status",
    ),
    "QueryActiveCycles": CapabilityDefinition(
        name="QueryActiveCycles",
        description="查询当前活跃茬口或种植周期。",
        contract=NodeContract(
            input_types=["FarmStatus"],
            output_type="ActiveCycleList",
            side_effect="none",
            failure_policy="repair",
        ),
        adapter_hint="manage_crop_cycle.query_cycles",
    ),
    "QueryPlantingUnits": CapabilityDefinition(
        name="QueryPlantingUnits",
        description="查询地块或种植单元列表。",
        contract=NodeContract(
            input_types=["FarmStatus"],
            output_type="PlantingUnitList",
            side_effect="none",
            failure_policy="ask_user",
        ),
        adapter_hint="manage_planting_units.query_units",
    ),
    "QueryCropTemplate": CapabilityDefinition(
        name="QueryCropTemplate",
        description="查询作物模板和种植参数。",
        contract=NodeContract(
            input_types=["PlanningSlotSet"],
            output_type="CropTemplate",
            required_slots=["crop"],
            side_effect="none",
            failure_policy="ask_user",
        ),
        adapter_hint="manage_crop_templates.query_templates",
    ),
    "QueryWeatherForecast": CapabilityDefinition(
        name="QueryWeatherForecast",
        description="查询天气预报或气候窗口。",
        contract=NodeContract(
            input_types=["PlanningSlotSet"],
            output_type="WeatherForecast",
            required_slots=["location"],
            side_effect="none",
            failure_policy="skip",
        ),
        adapter_hint="weather_adapter",
    ),
    "CalculatePlantingLayout": CapabilityDefinition(
        name="CalculatePlantingLayout",
        description="计算面积、地块数、批次和布局窗口。",
        contract=NodeContract(
            input_types=["PlanningSlotSet", "CropTemplate"],
            output_type="PlantingLayout",
            required_slots=["total_area_mu"],
            side_effect="none",
            failure_policy="repair",
        ),
        adapter_hint="deterministic_calculator",
    ),
    "SynthesizePlantingPlan": CapabilityDefinition(
        name="SynthesizePlantingPlan",
        description="汇总已验证事实并生成用户可读规划方案。",
        contract=NodeContract(
            input_types=["PlanningContext", "PlantingLayout"],
            output_type="PlantingPlanResponse",
            side_effect="none",
            failure_policy="hard_fail",
        ),
        adapter_hint="response_synthesizer",
    ),
    "SynthesizeRequiredSlotQuestions": CapabilityDefinition(
        name="SynthesizeRequiredSlotQuestions",
        description="根据缺失槽位生成补问响应，不假定已有布局结果。",
        contract=NodeContract(
            input_types=["PlanningContext"],
            output_type="PlantingPlanResponse",
            side_effect="none",
            failure_policy="ask_user",
        ),
        adapter_hint="response_synthesizer",
    ),
    "ProposeCreateCyclePlan": CapabilityDefinition(
        name="ProposeCreateCyclePlan",
        description="生成待确认的创建茬口计划，不直接落库。",
        contract=NodeContract(
            input_types=["PlantingPlanResponse"],
            output_type="PendingCyclePlan",
            side_effect="pending_only",
            failure_policy="ask_user",
        ),
        side_effect="pending_only",
        failure_policy="ask_user",
        adapter_hint="pending_plan",
    ),
    "ProposeWorkOrderPlan": CapabilityDefinition(
        name="ProposeWorkOrderPlan",
        description="生成待确认的工单计划，不直接落库。",
        contract=NodeContract(
            input_types=["PlanningContext"],
            output_type="PendingWorkOrderPlan",
            side_effect="pending_only",
            failure_policy="ask_user",
        ),
        side_effect="pending_only",
        failure_policy="ask_user",
        adapter_hint="pending_plan",
    ),
    "AnalyzeCost": CapabilityDefinition(
        name="AnalyzeCost",
        description="按用户明确成本需求执行成本估算。",
        contract=NodeContract(
            input_types=["PlanningContext", "PlantingLayout"],
            output_type="CostAnalysis",
            side_effect="none",
            failure_policy="skip",
        ),
        adapter_hint="cost_capability",
    ),
}


def get_capability(name: str) -> CapabilityDefinition | None:
    capability = CAPABILITY_CATALOG.get(name)
    return capability.model_copy(deep=True) if capability is not None else None


def list_capabilities() -> list[CapabilityDefinition]:
    return [
        capability.model_copy(deep=True) for capability in CAPABILITY_CATALOG.values()
    ]
