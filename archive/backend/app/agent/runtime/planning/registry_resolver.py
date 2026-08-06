"""Planning 层到 skills/registry 的 capability operation 解析。"""

from __future__ import annotations

from dataclasses import dataclass

from app.skills.registry import SkillRegistry, load_skill_registry

TASK_GRAPH_CAPABILITY_MAP = {
    "QueryFarmStatus": ("get_farm_status", "query_status"),
    "QueryActiveCycles": ("manage_crop_cycle", "query_cycles"),
    "QueryPlantingUnits": ("manage_planting_units", "query_units"),
    "QueryCropTemplate": ("manage_crop_templates", "query_templates"),
    "QueryWeatherForecast": ("weather", "query_forecast"),
    "CalculateArithmetic": ("calculate_arithmetic", "calculate"),
    "ProposeCreateCyclePlan": ("manage_crop_cycle", "create_cycle"),
    "ProposeWorkOrderPlan": ("manage_work_orders", "create_work_order"),
    "AnalyzeCost": ("manage_cost", "analyze_cost"),
}


@dataclass(frozen=True)
class CapabilityOperationResolution:
    """Capability -> Operation -> Skill 的解析结果。"""

    capability: str
    operation: str
    skill_name: str
    risk: str
    requires_confirmation: bool


def resolve_capability_operation(
    capability: str,
    operation: str,
    *,
    registry: SkillRegistry | None = None,
) -> CapabilityOperationResolution | None:
    """从现有 skills/registry 解析 capability.operation。"""
    skill_registry = registry or load_skill_registry()
    capability_definition = skill_registry.capabilities.get(capability)
    if capability_definition is None:
        return None
    operation_definition = capability_definition.operations.get(operation)
    if operation_definition is None:
        return None
    requires_confirmation = (
        operation_definition.requires_confirmation
        or operation_definition.risk in {"write_confirm", "write_high"}
    )
    return CapabilityOperationResolution(
        capability=capability_definition.name,
        operation=operation_definition.name,
        skill_name=capability_definition.name,
        risk=operation_definition.risk,
        requires_confirmation=requires_confirmation,
    )


def resolve_task_graph_capability(
    task_graph_capability: str,
    *,
    registry: SkillRegistry | None = None,
) -> CapabilityOperationResolution | None:
    """把旧 task_graph capability 名映射到现有 skills/registry。"""
    target = TASK_GRAPH_CAPABILITY_MAP.get(task_graph_capability)
    if target is None:
        return None
    capability, operation = target
    return resolve_capability_operation(capability, operation, registry=registry)


__all__ = [
    "CapabilityOperationResolution",
    "TASK_GRAPH_CAPABILITY_MAP",
    "resolve_capability_operation",
    "resolve_task_graph_capability",
]
