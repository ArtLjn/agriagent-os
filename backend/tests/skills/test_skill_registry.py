"""Skill Capability Registry loader 和 validation 测试。"""

from pathlib import Path

import pytest
import yaml

from app.agent.skills.registry import load_skill_registry, validate_skill_registry
from app.agent.skills.registry.governance import check_skill_registry

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
    expected_aliases = set(registry.aliases)

    issues = validate_skill_registry(registry, expected_aliases=expected_aliases)

    assert issues == []
    assert "manage_cost" in _skill_doc_tool_names()
    assert registry.resolve_alias("get_cost_analytics").target == (
        "manage_cost.analyze_cost"
    )


def test_aliases_resolve_to_capability_operations():
    registry = load_skill_registry()

    for legacy_name, alias in registry.aliases.items():
        operation = registry.get_operation(alias.capability, alias.operation)

        assert operation is not None
        assert legacy_name in operation.legacy_aliases


def test_manage_settings_legacy_aliases_resolve_to_operations():
    registry = load_skill_registry()

    query_alias = registry.resolve_alias("get_user_settings")
    update_alias = registry.resolve_alias("manage_user_settings")

    assert query_alias is not None
    assert query_alias.capability == "manage_settings"
    assert query_alias.operation == "query_settings"
    assert update_alias is not None
    assert update_alias.capability == "manage_settings"
    assert update_alias.operation == "update_settings"
    assert registry.capabilities["manage_settings"].capability == "manage_settings"
    assert registry.get_operation("manage_settings", "query_settings").risk == "read"
    assert (
        registry.get_operation("manage_settings", "update_settings").risk
        == "write_confirm"
    )


def test_manage_workers_legacy_aliases_resolve_to_operations():
    registry = load_skill_registry()

    query_alias = registry.resolve_alias("get_workers")
    manage_alias = registry.resolve_alias("manage_workers")

    assert query_alias is not None
    assert query_alias.capability == "manage_workers"
    assert query_alias.operation == "query_workers"
    assert manage_alias is not None
    assert manage_alias.capability == "manage_workers"
    assert manage_alias.operation == "manage_worker"
    assert registry.capabilities["manage_workers"].capability == "manage_workers"
    assert registry.get_operation("manage_workers", "query_workers").risk == "read"
    assert (
        registry.get_operation("manage_workers", "manage_worker").risk
        == "write_confirm"
    )


def test_manage_labor_payment_legacy_aliases_resolve_to_operations():
    registry = load_skill_registry()

    query_alias = registry.resolve_alias("get_labor_payables")
    settle_alias = registry.resolve_alias("settle_labor_payment")
    wage_alias = registry.resolve_alias("manage_wages")

    assert query_alias is not None
    assert query_alias.capability == "manage_labor_payment"
    assert query_alias.operation == "query_payables"
    assert settle_alias is not None
    assert settle_alias.capability == "manage_labor_payment"
    assert settle_alias.operation == "settle_payment"
    assert wage_alias is not None
    assert wage_alias.capability == "manage_labor_payment"
    assert wage_alias.operation == "manage_wage"
    assert registry.capabilities["manage_labor_payment"].capability == (
        "labor_payment_management"
    )
    assert registry.get_operation("manage_labor_payment", "query_payables").risk == (
        "read"
    )
    assert (
        registry.get_operation("manage_labor_payment", "settle_payment").risk
        == "write_confirm"
    )
    assert (
        registry.get_operation("manage_labor_payment", "manage_wage").risk
        == "write_confirm"
    )


def test_manage_planting_units_legacy_aliases_resolve_to_operations():
    registry = load_skill_registry()

    query_alias = registry.resolve_alias("get_planting_units")
    manage_alias = registry.resolve_alias("manage_planting_units")

    assert query_alias is not None
    assert query_alias.capability == "manage_planting_units"
    assert query_alias.operation == "query_units"
    assert manage_alias is not None
    assert manage_alias.capability == "manage_planting_units"
    assert manage_alias.operation == "manage_units"
    assert registry.capabilities["manage_planting_units"].capability == (
        "manage_planting_units"
    )
    assert registry.get_operation("manage_planting_units", "query_units").risk == (
        "read"
    )
    assert registry.get_operation("manage_planting_units", "manage_units").risk == (
        "write_confirm"
    )


def test_manage_cost_categories_legacy_aliases_resolve_to_operations():
    registry = load_skill_registry()

    query_alias = registry.resolve_alias("get_cost_categories")
    manage_alias = registry.resolve_alias("manage_cost_categories")

    assert query_alias is not None
    assert query_alias.capability == "manage_cost_categories"
    assert query_alias.operation == "query_categories"
    assert manage_alias is not None
    assert manage_alias.capability == "manage_cost_categories"
    assert manage_alias.operation == "manage_category"
    assert registry.capabilities["manage_cost_categories"].capability == (
        "manage_cost_categories"
    )
    assert registry.get_operation(
        "manage_cost_categories", "query_categories"
    ).risk == ("read")
    assert registry.get_operation("manage_cost_categories", "manage_category").risk == (
        "write_confirm"
    )


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


def test_default_registry_governance_check_passes():
    issues = check_skill_registry()

    assert issues == []


def test_registry_governance_reports_duplicate_alias_and_key_guardrails(tmp_path):
    _write_registry_files(
        tmp_path,
        domains="""
domains:
  - name: external
    owner: agent-platform
  - name: finance
    owner: agent-platform
""",
        skills="""
capabilities:
  - name: web_search
    domain: external
    capability: web_search
    description: 网络搜索。
    examples: [搜索新闻]
    anti_examples: [查询农场账单]
    tags: [搜索]
    version: v1
    owner: agent-platform
    status: active
    context_dependencies: [external_search]
    operations:
      search:
        risk: read
        legacy_aliases: [web_search]
  - name: weather
    domain: external
    capability: weather_forecast_query
    description: 查询天气。
    examples: [明天天气]
    anti_examples: [搜索新闻]
    tags: [天气]
    version: v1
    owner: agent-platform
    status: hidden
    disabled_reason: 测试禁用
    context_dependencies: [weather_location]
    operations:
      query_forecast:
        risk: read
        legacy_aliases: [weather]
  - name: manage_cost
    domain: finance
    capability: cost_management
    description: 成本管理。
    examples: [记账]
    anti_examples: [查天气]
    tags: [成本]
    version: v1
    owner: agent-platform
    status: active
    context_dependencies: [farm]
    operations:
      create_record:
        risk: write_confirm
        legacy_aliases: [create_cost_record]
""",
        aliases="""
aliases:
  - legacy_name: web_search
    capability: web_search
    operation: search
  - legacy_name: web_search
    capability: web_search
    operation: search
  - legacy_name: weather
    capability: weather
    operation: query_forecast
  - legacy_name: create_cost_record
    capability: manage_cost
    operation: create_record
""",
    )
    skills_dir = tmp_path / "skills"
    for tool_name in ("web_search", "weather", "create_cost_record"):
        skill_dir = skills_dir / tool_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.md").write_text(
            f"---\nname: {tool_name}\n---\n",
            encoding="utf-8",
        )

    issues = check_skill_registry(registry_dir=tmp_path, skills_dir=skills_dir)
    codes = {issue.code for issue in issues}

    assert "duplicate_alias" in codes
    assert "web_search_must_stay_disabled" in codes
    assert "web_search_missing_disabled_reason" in codes
    assert "web_search_invalid_risk" in codes
    assert "weather_must_stay_active" in codes
    assert "weather_invalid_risk" in codes


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
