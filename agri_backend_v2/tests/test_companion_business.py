"""陪伴业务插件清单与本地技能契约测试。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from agent.domains.harness.tools import loader
from agent.plugins import discover_plugin, resolve_plugin_root

_ROOT = Path(__file__).parents[1]
_COMPANION = _ROOT / "businesses" / "companion"


def test_companion_manifest_exposes_two_local_skills() -> None:
    manifest = discover_plugin(resolve_plugin_root("businesses"), "companion")

    assert manifest.display_name == "陪伴助手"
    assert manifest.assistant_name == "陪伴助手"
    assert len(manifest.skill_paths) == 2
    assert manifest.system_prompt_source == "businesses/companion/prompts/system.md"


def test_companion_skills_load_with_core_tools() -> None:
    registry = loader.load_registry([
        loader.core_skills_dir(),
        _COMPANION / "skills",
    ])

    assert {
        "companion_checkin",
        "companion_activity",
        "calculate_arithmetic",
        "web_search",
    } == {skill.name for skill in registry.all()}


def test_companion_checkin_returns_greeting_and_question() -> None:
    module = loader.load_skill_module(_COMPANION / "skills" / "companion-checkin")

    result = asyncio.run(module.skill.execute({}, None))

    assert result.ok
    assert result.data["period"]
    assert result.data["message"]
    assert result.data["question"].endswith("？")


def test_companion_activity_validates_mood_and_bounds_minutes() -> None:
    module = loader.load_skill_module(_COMPANION / "skills" / "companion-activity")

    result = asyncio.run(module.skill.execute({"mood": "tired", "minutes": 99}, None))
    assert result.ok
    assert result.data["mood"] == "tired"
    assert result.data["duration_minutes"] == 30

    invalid = asyncio.run(module.skill.execute({"mood": "unknown"}, None))
    assert not invalid.ok
    assert "happy" in (invalid.error or "")
