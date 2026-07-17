"""Skill metadata 治理测试。"""

import pytest

from app.skills import get_langchain_tools
from app.skills import metadata as metadata_module
from app.skills.metadata import (
    SkillPermissionLevel,
    get_skill_metadata,
)

pytestmark = pytest.mark.no_db

RETIRED_CRUD_SKILL_NAMES = {
    "create_cost_record",
    "get_cost_summary",
    "get_cost_analytics",
    "get_debt_summary",
    "delete_cost_record",
    "settle_debt",
    "create_crop_cycle",
    "get_crop_cycles",
    "get_crop_cycle_info",
    "update_crop_cycle",
    "update_crop_stage",
    "delete_crop_cycle",
    "create_crop_template",
    "get_crop_templates",
    "get_planting_units",
    "create_operation_work_order",
    "get_operation_work_orders",
    "update_operation_work_order",
    "get_workers",
    "get_labor_payables",
    "settle_labor_payment",
    "manage_wages",
    "log_farm_activity",
    "get_recent_farm_logs",
    "get_user_settings",
    "get_cost_categories",
}

CANONICAL_METADATA_SKILL_NAMES = {
    "manage_cost",
    "manage_crop_cycle",
    "manage_crop_templates",
    "manage_farm_logs",
    "manage_labor_payment",
    "manage_work_orders",
    "manage_workers",
    "manage_planting_units",
    "manage_cost_categories",
    "manage_user_settings",
    "get_farm_status",
    "weather",
    "web_search",
}


class _SkillRef:
    def __init__(self, name: str) -> None:
        self._name = name

    def name(self) -> str:
        return self._name


def test_canonical_runtime_skill_metadata_uses_capability_defaults():
    metadata = get_skill_metadata(_SkillRef("manage_cost"))

    assert metadata.capability == "manage_cost"
    assert metadata.operation is None
    assert metadata.context_dependencies == [
        "farm",
        "cost_records",
        "cost_categories",
    ]
    assert metadata.cache_invalidation == [
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ]
    assert {"成本", "账单", "趋势"} <= set(metadata.evaluation_tags)
    assert metadata.metadata_incomplete is False


def test_legacy_alias_stub_metadata_resolves_through_registry():
    metadata = get_skill_metadata(_SkillRef("create_cost_record"))

    assert metadata.capability == "manage_cost"
    assert metadata.operation == "create_record"
    assert metadata.legacy_alias == "create_cost_record"
    assert metadata.operation_risk == "write_confirm"
    assert metadata.permission_level == SkillPermissionLevel.WRITE_CONFIRM
    assert metadata.context_dependencies == [
        "farm",
        "cost_records",
        "cost_categories",
    ]


def test_metadata_governance_tables_do_not_contain_retired_crud_skill_names():
    metadata_names = (
        set(metadata_module._READ_SKILL_METADATA)
        | set(metadata_module._WRITE_SKILL_METADATA)
    )

    assert metadata_names == CANONICAL_METADATA_SKILL_NAMES
    assert metadata_names & RETIRED_CRUD_SKILL_NAMES == set()


def test_langchain_tools_do_not_expose_retired_crud_names():
    tool_names = {tool.name for tool in get_langchain_tools()}

    assert tool_names & RETIRED_CRUD_SKILL_NAMES == set()
