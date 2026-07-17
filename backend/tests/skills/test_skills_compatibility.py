"""Skill 旧路径迁移兼容护栏测试。"""

from importlib import import_module
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.no_db


def test_old_agent_skills_package_exposes_runtime_api() -> None:
    new_module = import_module("app.skills")
    module = import_module("app.agent.skills")

    assert module is new_module

    for name in (
        "get_skill_manager",
        "get_langchain_tools",
        "get_skill_registry",
        "clear_skill_cache",
        "build_skill_context",
    ):
        assert callable(getattr(module, name))


def test_old_agent_skills_registry_package_exposes_loader_api() -> None:
    new_module = import_module("app.skills.registry")
    module = import_module("app.agent.skills.registry")

    assert module is new_module
    assert callable(module.load_skill_registry)
    assert callable(module.validate_skill_registry)


def test_old_agent_skills_metadata_module_exposes_contract_types() -> None:
    new_module = import_module("app.skills.metadata")
    module = import_module("app.agent.skills.metadata")

    assert module is new_module
    assert module.SkillMetadata is not None
    assert module.SkillPermissionLevel is not None
    assert module.SkillRiskLevel is not None


def test_old_hyphenated_skill_dynamic_import_path_still_loads() -> None:
    new_module = import_module("app.skills.manage-cost.scripts.main")
    module = import_module("app.agent.skills.manage-cost.scripts.main")

    assert module is new_module


def test_old_patch_targets_remain_resolvable() -> None:
    with (
        patch("app.agent.skills.web_search.scripts.main.get_llm") as get_llm,
        patch("app.agent.skills.web_search.scripts.main.settings") as settings,
        patch(
            "app.agent.skills.registry.governance.load_skill_registry"
        ) as load_skill_registry,
    ):
        assert get_llm is not None
        assert settings is not None
        assert load_skill_registry is not None
