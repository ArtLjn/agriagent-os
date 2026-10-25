"""插件清单、核心+插件合并加载与空结果策略校验回归。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agent.domains.harness.tools import loader
from agent.domains.harness.tools.base import OperationSkill, Skill
from agent.domains.harness.tools.registry import SkillRegistry, SkillRegistryError
from agent.plugins import PluginError, discover_plugin, resolve_plugin_root

_SKILL_MD = """---
name: demo_skill
kind: mcp
mcp_tool: demo_skill
description: demo skill
parameters:
  type: object
  properties: {}
  required: []
---
"""


def _write_plugin(
    root: Path,
    name: str = "demo",
    *,
    manifest: dict | None = None,
    skill_md: str = _SKILL_MD,
) -> Path:
    plugin = root / name
    (plugin / "prompts").mkdir(parents=True)
    (plugin / "skills" / "demo-skill").mkdir(parents=True)
    (plugin / "prompts" / "system.md").write_text("system", encoding="utf-8")
    if skill_md is not None:
        (plugin / "skills" / "demo-skill" / "skill.md").write_text(
            skill_md, encoding="utf-8"
        )
    payload = {
        "schema_version": 2,
        "name": name,
        "display_name": "Demo",
        "system_prompt": "prompts/system.md",
        "skills_dir": "skills",
    }
    payload.update(manifest or {})
    (plugin / "plugin.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
    )
    return plugin


def test_repo_farm_plugin_manifest_is_valid() -> None:
    manifest = discover_plugin(resolve_plugin_root("businesses"), "farm")

    assert manifest.name == "farm"
    assert manifest.display_name == "农场助理"
    assert len(manifest.skill_paths) == 16
    assert manifest.system_prompt_source == "businesses/farm/prompts/system.md"


def test_discover_requires_exactly_one_plugin(tmp_path) -> None:
    with pytest.raises(PluginError, match="plugin_missing"):
        discover_plugin(tmp_path)

    _write_plugin(tmp_path, "one")
    assert discover_plugin(tmp_path).name == "one"

    _write_plugin(tmp_path, "two")
    with pytest.raises(PluginError, match="plugin_ambiguous"):
        discover_plugin(tmp_path)
    assert discover_plugin(tmp_path, "two").name == "two"


@pytest.mark.parametrize(
    "manifest,error",
    [
        ({"unknown": True}, "plugin_manifest_unknown_fields"),
        ({"name": "other"}, "plugin_name_mismatch"),
        ({"system_prompt": "../outside.md"}, "plugin_path_escape"),
        ({"schema_version": 1}, "plugin_schema_version_invalid"),
    ],
)
def test_manifest_rejects_invalid_fields(tmp_path, manifest, error) -> None:
    plugin = _write_plugin(tmp_path, "demo", manifest=manifest)

    with pytest.raises(PluginError, match=error):
        discover_plugin(plugin.parent, "demo")


def test_plugin_without_skills_fails_fast(tmp_path) -> None:
    plugin = _write_plugin(tmp_path, "demo")
    (plugin / "skills" / "demo-skill" / "skill.md").unlink()
    (plugin / "skills" / "demo-skill").rmdir()

    with pytest.raises(PluginError, match="plugin_skills_empty"):
        discover_plugin(tmp_path, "demo")


def test_combined_loader_keeps_catalog_and_order() -> None:
    registry = loader.load_registry()
    names = [tool["function"]["name"] for tool in registry.exposed_tools()]

    assert len(registry.all()) == 59
    assert len(names) == 58
    assert names[0] == "calculate_arithmetic"
    assert names[-1] == "web_search"

    core_only = loader.load_registry([loader._SKILLS_DIR])
    assert len(core_only.all()) == 2


def test_broken_skill_directory_is_not_silently_skipped(tmp_path) -> None:
    plugin = _write_plugin(tmp_path / "businesses", "demo", skill_md=None)

    with pytest.raises(loader.SkillLoadError, match="skill_source_missing"):
        loader.load_registry([plugin / "skills"])


def _operation_skill(
    policy: dict | None,
    *,
    name: str = "demo_query",
    expose: bool = True,
    top_level_policy: dict | None = None,
) -> OperationSkill:
    source = Skill()
    source.mcp_tool = "demo"
    source._meta = {
        "name": "demo",
        "description": "demo",
        "risk_level": "mixed",
        "parameters": {"type": "object", "properties": {}},
        "operations": {
            "query": {
                "tool_name": name,
                "description": "query",
                "risk_level": "read",
                "parameters": [],
                "expose_to_model": expose,
                **({"empty_result_policy": policy} if policy is not None else {}),
            }
        },
    }
    if top_level_policy is not None:
        source._meta["empty_result_policy"] = top_level_policy
    return OperationSkill(source, "query")


def _policy(**overrides) -> dict:
    policy = {
        "observation": {
            "code": "empty_result",
            "message": "empty",
            "missing": ["custom_template.stages"],
        },
        "next_allowed_action": {
            "agent_tool_name": "prepare_plan",
            "arguments": None,
        },
        "task_state": {"reason": "empty_result", "resume_policy": "ask_user"},
    }
    policy.update(overrides)
    return policy


def test_valid_empty_result_policy_is_accepted() -> None:
    source = _operation_skill(_policy())
    target = _operation_skill(None, name="prepare_plan")

    registry = SkillRegistry.from_skills([source, target])
    assert registry.get("demo_query").empty_result_policy == _policy()


@pytest.mark.parametrize(
    "policy,error",
    [
        (
            _policy(next_allowed_action={"agent_tool_name": "prepare_plan"}),
            "invalid_empty_result_policy",
        ),
        (
            _policy(task_state={"reason": "empty_result", "resume_policy": "auto"}),
            "invalid_empty_result_policy",
        ),
        (
            _policy(observation={"code": "empty_result", "message": "empty", "x": 1}),
            "invalid_empty_result_policy",
        ),
    ],
)
def test_invalid_empty_result_policy_shape_is_rejected(policy, error) -> None:
    source = _operation_skill(policy)
    target = _operation_skill(None, name="prepare_plan")

    with pytest.raises(SkillRegistryError, match=error):
        SkillRegistry.from_skills([source, target])


def test_empty_result_policy_target_must_be_registered_exposed_and_distinct() -> None:
    source = _operation_skill(_policy())

    with pytest.raises(SkillRegistryError, match="empty_result_target_missing"):
        SkillRegistry.from_skills([source])

    hidden = _operation_skill(None, name="prepare_plan", expose=False)
    with pytest.raises(SkillRegistryError, match="empty_result_target_not_exposed"):
        SkillRegistry.from_skills([source, hidden])

    self_target = _policy(
        next_allowed_action={"agent_tool_name": "demo_query", "arguments": None}
    )
    with pytest.raises(SkillRegistryError, match="empty_result_target_self"):
        SkillRegistry.from_skills([_operation_skill(self_target)])


def test_empty_result_policy_must_not_be_declared_at_top_level() -> None:
    source = _operation_skill(None, top_level_policy=_policy())

    with pytest.raises(SkillRegistryError, match="empty_result_policy_top_level"):
        SkillRegistry.from_skills([source])


def test_system_prompt_is_loaded_from_active_plugin() -> None:
    from agent import prompts
    from agent.config import settings

    assert prompts.render_system_prompt() == settings.plugins.system_prompt_path.read_text(
        encoding="utf-8"
    )
    system = next(item for item in prompts.inspect_prompts() if item["name"] == "system")
    assert system["source"] == "businesses/farm/prompts/system.md"
    assert system["active"] is True
