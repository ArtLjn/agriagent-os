"""Planning 层复用 skills/registry 的解析测试。"""

import pytest

from app.agent.runtime.planning.registry_resolver import (
    resolve_capability_operation,
    resolve_task_graph_capability,
)
from app.skills.registry import load_skill_registry

pytestmark = pytest.mark.no_db


def test_resolve_capability_operation_returns_three_layer_contract() -> None:
    resolution = resolve_capability_operation(
        "manage_crop_cycle",
        "create_cycle",
    )

    assert resolution is not None
    assert resolution.capability == "manage_crop_cycle"
    assert resolution.operation == "create_cycle"
    assert resolution.skill_name == "manage_crop_cycle"
    assert resolution.risk == "write_confirm"
    assert resolution.requires_confirmation is True


def test_resolve_task_graph_capability_maps_to_skill_registry() -> None:
    resolution = resolve_task_graph_capability("ProposeCreateCyclePlan")

    assert resolution is not None
    assert resolution.capability == "manage_crop_cycle"
    assert resolution.operation == "create_cycle"
    assert resolution.skill_name == "manage_crop_cycle"


def test_unknown_task_graph_capability_fails_closed() -> None:
    assert resolve_task_graph_capability("MissingCapability") is None


def test_registry_loader_exposes_planner_fields() -> None:
    operation = load_skill_registry().get_operation(
        "manage_crop_cycle",
        "create_cycle",
    )

    assert operation is not None
    assert operation.side_effect == "write"
    assert operation.requires_confirmation is True
    assert operation.executor_ref == "skill:manage_crop_cycle"
    assert operation.input_schema == {"operation": "create_cycle"}
    assert operation.output_schema == {"type": "crop_cycle"}
    assert operation.planner_hints == (
        "创建茬口前应确认作物模板存在；需要用户确认后执行。",
    )
    assert operation.failure_policy == "ask_user"
