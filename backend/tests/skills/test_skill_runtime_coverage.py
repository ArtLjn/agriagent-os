"""Skill 运行时覆盖审计测试。"""

from pathlib import Path
import re

import pytest

from app.agent.skills import get_langchain_tools, get_skill_manager
from app.agent.skills.metadata import (
    SkillPermissionLevel,
    get_skill_metadata,
)
from app.agent.tool_selector import QUERY_TRIGGERS, TOOL_CHAIN_MAP, WRITE_PATTERNS
from app.infra.pending_actions import WRITE_SKILLS

pytestmark = pytest.mark.no_db


EXPECTED_REGISTERED_SKILLS = {
    "manage_cost",
    "manage_crop_cycle",
    "manage_crop_templates",
    "manage_work_orders",
    "manage_farm_logs",
    "get_farm_status",
    "get_labor_payables",
    "get_workers",
    "manage_cost_categories",
    "get_planting_units",
    "manage_planting_units",
    "manage_user_settings",
    "settle_labor_payment",
    "manage_workers",
    "manage_wages",
    "get_weather_forecast",
    "web_search",
}

EXPECTED_WRITE_SKILLS = {
    "manage_work_orders",
    "settle_labor_payment",
    "manage_workers",
    "manage_wages",
    "manage_cost_categories",
    "manage_planting_units",
    "manage_user_settings",
}
OPERATION_AWARE_WRITE_DOCS = {
    "manage_cost",
    "manage_crop_cycle",
    "manage_crop_templates",
    "manage_farm_logs",
}
RETIRED_COST_WRITE_ALIASES = {
    "create_cost_record",
    "delete_cost_record",
    "settle_debt",
}
RETIRED_CROP_CYCLE_WRITE_ALIASES = {
    "create_crop_cycle",
    "update_crop_cycle",
    "delete_crop_cycle",
}
RETIRED_CROP_TEMPLATE_WRITE_ALIASES = {
    "create_crop_template",
}
RETIRED_FARM_LOG_WRITE_ALIASES = {
    "log_farm_activity",
}
RETIRED_WORK_ORDER_WRITE_ALIASES = {
    "create_operation_work_order",
    "update_operation_work_order",
}

SKILLS_DIR = Path(__file__).parents[2] / "app" / "agent" / "skills"


def _registered_skills() -> dict[str, object]:
    manager = get_skill_manager()
    result = {}
    for skill_def in manager.list_skills():
        skill = manager.get_skill(skill_def.name)
        if skill is not None:
            result[skill_def.name] = skill
    return result


def _write_skill_docs() -> set[str]:
    names = set()
    for path in SKILLS_DIR.glob("*/skill.md"):
        text = path.read_text(encoding="utf-8")
        frontmatter = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if frontmatter is None:
            continue
        frontmatter_text = frontmatter.group(1)
        if not re.search(r"^type:\s*write\s*$", frontmatter_text, re.MULTILINE):
            continue
        name = re.search(r"^name:\s*(\S+)\s*$", frontmatter_text, re.MULTILINE)
        if name is not None:
            names.add(name.group(1).strip("\"'"))
    return names


def test_registered_skill_inventory_is_expected() -> None:
    skills = _registered_skills()

    assert set(skills) == EXPECTED_REGISTERED_SKILLS


def test_cost_category_tool_surface_uses_single_capability() -> None:
    tool_names = {tool.name for tool in get_langchain_tools()}

    assert "manage_cost_categories" in tool_names
    assert "get_cost_categories" not in tool_names
    assert not (SKILLS_DIR / "get-cost-categories").exists()


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


def test_write_skill_docs_are_registered_for_pending_confirmation() -> None:
    assert (
        _write_skill_docs()
        == (
            WRITE_SKILLS
            - RETIRED_COST_WRITE_ALIASES
            - RETIRED_CROP_CYCLE_WRITE_ALIASES
            - RETIRED_CROP_TEMPLATE_WRITE_ALIASES
            - RETIRED_FARM_LOG_WRITE_ALIASES
            - RETIRED_WORK_ORDER_WRITE_ALIASES
        )
        | OPERATION_AWARE_WRITE_DOCS
    )


def test_disabled_skills_have_disabled_reason() -> None:
    skills = _registered_skills()
    disabled = {
        name: get_skill_metadata(skill).disabled_reason
        for name, skill in skills.items()
        if not get_skill_metadata(skill).enabled
    }

    assert disabled == {"web_search": "SearXNG 引擎不稳定（CAPTCHA/限流），暂禁用"}
