"""SkillLoader 与 SkillRegistry 的目录加载和能力快照契约测试。"""

from pathlib import Path

import pytest

from agent.domains.harness.tools.registry import SkillRegistry, SkillRegistryError


def test_from_directory_loads_current_skill_catalog() -> None:
    skills_dir = Path(__file__).parents[1] / "agent" / "tools"

    registry = SkillRegistry.from_directory(skills_dir)
    snapshot = registry.snapshot()

    assert len(registry.all()) == 53
    assert len(registry.exposed_tools()) == 52
    assert "get_weather" in snapshot["skill_names"]
    assert "commit_planting_plan" not in snapshot["exposed_tool_names"]
    assert snapshot["risk_levels"] == tuple(sorted(snapshot["risk_levels"]))


def test_require_returns_structured_missing_skill_error() -> None:
    registry = SkillRegistry.from_skills([])

    with pytest.raises(SkillRegistryError, match="skill_missing.*missing") as exc_info:
        registry.require("missing")

    assert exc_info.value.code == "skill_missing"
    assert exc_info.value.skill_name == "missing"
