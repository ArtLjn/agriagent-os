"""Skill Capability Registry loader 和 validation 测试。"""

from pathlib import Path

import pytest
import yaml

from app.agent.skills.registry import load_skill_registry, validate_skill_registry

pytestmark = pytest.mark.no_db


def test_load_default_skill_registry():
    registry = load_skill_registry()

    assert set(registry.domains) == {
        "finance",
        "crop",
        "farm",
        "operation",
        "labor",
        "log",
        "settings",
        "external",
    }
    assert registry.capabilities["manage_cost"].domain == "finance"
    assert registry.capabilities["manage_cost"].operations["create_record"].risk == (
        "write_confirm"
    )
    assert registry.resolve_alias("create_cost_record").target == (
        "manage_cost.create_record"
    )


def test_default_registry_validation_passes_and_covers_all_skill_docs():
    registry = load_skill_registry()
    expected_aliases = _skill_doc_tool_names()

    issues = validate_skill_registry(registry, expected_aliases=expected_aliases)

    assert issues == []
    assert set(registry.aliases) == expected_aliases


def test_aliases_resolve_to_capability_operations():
    registry = load_skill_registry()

    for legacy_name, alias in registry.aliases.items():
        operation = registry.get_operation(alias.capability, alias.operation)

        assert operation is not None
        assert legacy_name in operation.legacy_aliases


def test_validation_reports_structured_issues(tmp_path):
    _write_registry_files(
        tmp_path,
        domains="""
domains:
  - name: finance
    owner: ""
""",
        skills="""
capabilities:
  - name: broken_cost
    domain: missing_domain
    capability: ""
    description: ""
    examples: []
    anti_examples: []
    tags: []
    version: v1
    owner: ""
    status: hidden
    operations:
      create_record:
        risk: ""
        legacy_aliases: []
""",
        aliases="""
aliases:
  - legacy_name: create_cost_record
    capability: broken_cost
    operation: missing_operation
""",
    )
    registry = load_skill_registry(tmp_path)

    issues = validate_skill_registry(
        registry,
        expected_aliases={"create_cost_record", "missing_legacy_tool"},
    )
    issue_payloads = [issue.as_dict() for issue in issues]
    codes = {issue["code"] for issue in issue_payloads}

    assert "missing_owner" in codes
    assert "missing_required_field" in codes
    assert {
        "code": "missing_required_field",
        "location": "capabilities.broken_cost.context_dependencies",
        "message": "capability 缺少必填字段 context_dependencies",
    } in issue_payloads
    assert "missing_anti_examples" in codes
    assert "invalid_domain" in codes
    assert "operation_missing_risk" in codes
    assert "invalid_alias_target" in codes
    assert "missing_alias" in codes
    assert "missing_disabled_reason" in codes
    assert {
        "code": "missing_alias",
        "location": "aliases.missing_legacy_tool",
        "message": "缺少 legacy tool alias：missing_legacy_tool",
    } in issue_payloads


def _skill_doc_tool_names() -> set[str]:
    skills_dir = Path(__file__).parents[2] / "app" / "agent" / "skills"
    tool_names = set()
    for skill_doc in sorted(skills_dir.glob("*/skill.md")):
        front_matter = skill_doc.read_text(encoding="utf-8").split("---", 2)[1]
        metadata = yaml.safe_load(front_matter) or {}
        tool_names.add(str(metadata.get("tool_name") or metadata["name"]))
    return tool_names


def _write_registry_files(
    base_dir: Path,
    *,
    domains: str,
    skills: str,
    aliases: str,
) -> None:
    (base_dir / "domains.yaml").write_text(domains, encoding="utf-8")
    (base_dir / "skills.yaml").write_text(skills, encoding="utf-8")
    (base_dir / "aliases.yaml").write_text(aliases, encoding="utf-8")
