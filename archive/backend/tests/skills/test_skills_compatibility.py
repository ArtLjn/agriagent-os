"""Skill 新路径运行护栏测试。"""

from importlib import import_module
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.no_db


def test_skills_package_exposes_runtime_api() -> None:
    module = import_module("app.skills")

    for name in (
        "get_skill_manager",
        "get_langchain_tools",
        "get_skill_registry",
        "clear_skill_cache",
        "build_skill_context",
    ):
        assert callable(getattr(module, name))


def test_skills_registry_package_exposes_loader_api() -> None:
    module = import_module("app.skills.registry")

    assert callable(module.load_skill_registry)
    assert callable(module.validate_skill_registry)


def test_skills_metadata_module_exposes_contract_types() -> None:
    module = import_module("app.skills.metadata")

    assert module.SkillMetadata is not None
    assert module.SkillPermissionLevel is not None
    assert module.SkillRiskLevel is not None


def test_hyphenated_skill_dynamic_import_path_loads() -> None:
    module = import_module("app.skills.manage-cost.scripts.main")

    assert module.ManageCostSkill is not None


def test_patch_targets_remain_resolvable_on_new_paths() -> None:
    with (
        patch("app.skills.web_search.scripts.main.get_llm") as get_llm,
        patch("app.skills.web_search.scripts.main.settings") as settings,
        patch(
            "app.skills.registry.governance.load_skill_registry"
        ) as load_skill_registry,
    ):
        assert get_llm is not None
        assert settings is not None
        assert load_skill_registry is not None
