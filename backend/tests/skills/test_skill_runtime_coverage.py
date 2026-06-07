"""Skill 运行时覆盖审计测试。"""

import pytest

from app.agent.skills import get_skill_manager
from app.agent.skills.metadata import (
    SkillPermissionLevel,
    get_skill_metadata,
)
from app.agent.tool_selector import QUERY_TRIGGERS, TOOL_CHAIN_MAP, WRITE_PATTERNS

pytestmark = pytest.mark.no_db


EXPECTED_REGISTERED_SKILLS = {
    "get_cost_analytics",
    "get_cost_summary",
    "create_cost_record",
    "delete_cost_record",
    "create_crop_cycle",
    "delete_crop_cycle",
    "create_crop_template",
    "get_crop_templates",
    "manage_crop_templates",
    "create_operation_work_order",
    "get_crop_cycle_info",
    "get_recent_farm_logs",
    "manage_farm_logs",
    "get_farm_status",
    "get_labor_payables",
    "get_workers",
    "get_operation_work_orders",
    "get_cost_categories",
    "manage_cost_categories",
    "get_planting_units",
    "manage_planting_units",
    "get_user_settings",
    "manage_user_settings",
    "log_farm_activity",
    "settle_debt",
    "settle_labor_payment",
    "update_crop_cycle",
    "update_crop_stage",
    "update_operation_work_order",
    "manage_workers",
    "manage_wages",
    "get_weather_forecast",
    "web_search",
}

EXPECTED_WRITE_SKILLS = {
    "create_cost_record",
    "delete_cost_record",
    "create_crop_cycle",
    "delete_crop_cycle",
    "create_crop_template",
    "manage_crop_templates",
    "create_operation_work_order",
    "log_farm_activity",
    "manage_farm_logs",
    "settle_debt",
    "settle_labor_payment",
    "update_crop_cycle",
    "update_crop_stage",
    "update_operation_work_order",
    "manage_workers",
    "manage_wages",
    "manage_cost_categories",
    "manage_planting_units",
    "manage_user_settings",
}


def _registered_skills() -> dict[str, object]:
    manager = get_skill_manager()
    result = {}
    for skill_def in manager.list_skills():
        skill = manager.get_skill(skill_def.name)
        if skill is not None:
            result[skill_def.name] = skill
    return result


def test_registered_skill_inventory_is_expected() -> None:
    skills = _registered_skills()

    assert set(skills) == EXPECTED_REGISTERED_SKILLS


def test_enabled_registered_skills_have_selector_coverage() -> None:
    skills = _registered_skills()
    selector_names = set(WRITE_PATTERNS) | set(QUERY_TRIGGERS)
    missing = {
        name
        for name, skill in skills.items()
        if get_skill_metadata(skill).enabled and name not in selector_names
    }

    assert missing == set()


def test_enabled_registered_skills_have_chain_policy() -> None:
    skills = _registered_skills()
    missing = {
        name
        for name, skill in skills.items()
        if get_skill_metadata(skill).enabled and name not in TOOL_CHAIN_MAP
    }

    assert missing == set()


def test_write_skills_use_write_confirm_permission() -> None:
    skills = _registered_skills()
    wrong_permission = {
        name: get_skill_metadata(skills[name]).permission_level
        for name in EXPECTED_WRITE_SKILLS
        if get_skill_metadata(skills[name]).permission_level
        != SkillPermissionLevel.WRITE_CONFIRM
    }

    assert wrong_permission == {}


def test_disabled_skills_have_disabled_reason() -> None:
    skills = _registered_skills()
    disabled = {
        name: get_skill_metadata(skill).disabled_reason
        for name, skill in skills.items()
        if not get_skill_metadata(skill).enabled
    }

    assert disabled == {"web_search": "SearXNG 引擎不稳定（CAPTCHA/限流），暂禁用"}
