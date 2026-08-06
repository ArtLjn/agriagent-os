"""Capability Catalog 契约测试。"""

import pytest

from app.agent.task_graph import capabilities
from app.agent.task_graph.capabilities.catalog import get_capability, list_capabilities
from app.agent.task_graph.compiler import compile_plan_ir
from app.agent.task_graph.plan_ir import create_plan_ir

pytestmark = pytest.mark.no_db


def test_capability_package_does_not_export_mutable_catalog() -> None:
    assert "CAPABILITY_CATALOG" not in capabilities.__all__
    assert not hasattr(capabilities, "CAPABILITY_CATALOG")


def test_capability_catalog_returns_isolated_copies() -> None:
    capability = get_capability("QueryCropTemplate")
    assert capability is not None

    capability.contract.required_slots.append("polluted")

    fresh = get_capability("QueryCropTemplate")
    assert fresh is not None
    catalog_item = next(
        item for item in list_capabilities() if item.name == "QueryCropTemplate"
    )
    assert fresh.contract.required_slots == ["crop"]
    assert catalog_item.contract.required_slots == ["crop"]


def test_compiled_node_contract_mutation_does_not_pollute_catalog() -> None:
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
                }
            ],
        )
    ).graph

    graph.nodes[0].contract.required_slots.append("polluted")

    capability = get_capability("QueryCropTemplate")
    assert capability is not None
    assert capability.contract.required_slots == ["crop"]
