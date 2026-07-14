"""Skill Registry 治理检查入口。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from app.agent.skills.registry.loader import REGISTRY_DIR, SkillRegistry
from app.agent.skills.registry.loader import load_skill_registry
from app.agent.skills.registry.validation import validate_skill_registry


@dataclass(frozen=True)
class GovernanceIssue:
    """治理检查问题，供脚本输出和测试断言复用。"""

    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "location": self.location,
            "message": self.message,
        }


def check_skill_registry(
    *,
    registry_dir: Path | str | None = None,
    skills_dir: Path | str | None = None,
) -> list[GovernanceIssue]:
    """运行 Registry 结构、alias 覆盖和关键治理 guardrail 检查。"""
    base_dir = Path(registry_dir) if registry_dir is not None else REGISTRY_DIR
    skill_docs_dir = Path(skills_dir) if skills_dir is not None else REGISTRY_DIR.parent
    try:
        registry = load_skill_registry(base_dir)
    except (OSError, ValueError) as exc:
        return [
            GovernanceIssue(
                code="registry_load_failed",
                location=str(base_dir),
                message=f"Registry YAML 加载失败：{exc}",
            )
        ]

    skill_doc_names = skill_doc_tool_names(skill_docs_dir)
    expected_aliases = {
        name for name in skill_doc_names if name not in registry.capabilities
    }
    issues = [
        GovernanceIssue(issue.code, issue.location, issue.message)
        for issue in validate_skill_registry(
            registry,
            expected_aliases=expected_aliases,
        )
    ]
    issues.extend(_duplicate_alias_issues(base_dir / "aliases.yaml"))
    issues.extend(_alias_skill_doc_issues(registry, skill_doc_names))
    issues.extend(_key_guardrail_issues(registry))
    return issues


def skill_doc_tool_names(skills_dir: Path | str) -> set[str]:
    """读取所有 skill.md 声明的 legacy tool name。"""
    base_dir = Path(skills_dir)
    tool_names: set[str] = set()
    for skill_doc in sorted(base_dir.glob("*/skill.md")):
        metadata = _skill_doc_frontmatter(skill_doc)
        tool_name = metadata.get("tool_name") or metadata.get("name")
        if tool_name:
            tool_names.add(str(tool_name))
    return tool_names


def _skill_doc_frontmatter(skill_doc: Path) -> dict:
    parts = skill_doc.read_text(encoding="utf-8").split("---", 2)
    if len(parts) < 3:
        return {}
    payload = yaml.safe_load(parts[1]) or {}
    return dict(payload) if isinstance(payload, dict) else {}


def _duplicate_alias_issues(path: Path) -> list[GovernanceIssue]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    aliases = payload.get("aliases") or []
    names = [str(item.get("legacy_name", "")) for item in aliases if item]
    return [
        GovernanceIssue(
            code="duplicate_alias",
            location=f"{path}:aliases.{name}",
            message=f"legacy alias 重复声明：{name}",
        )
        for name, count in sorted(Counter(names).items())
        if name and count > 1
    ]


def _alias_skill_doc_issues(
    registry: SkillRegistry,
    skill_doc_names: Iterable[str],
) -> list[GovernanceIssue]:
    known_docs = set(skill_doc_names)
    documented_capabilities = {
        alias.capability
        for legacy_name, alias in registry.aliases.items()
        if legacy_name in known_docs
    }
    return [
        GovernanceIssue(
            code="alias_without_skill_doc",
            location=f"aliases.{legacy_name}",
            message=f"Registry alias 找不到对应 skill.md：{legacy_name}",
        )
        for legacy_name, alias in sorted(registry.aliases.items())
        if legacy_name not in known_docs
        and alias.capability not in known_docs
        and alias.capability not in documented_capabilities
    ]


def _key_guardrail_issues(registry: SkillRegistry) -> list[GovernanceIssue]:
    issues: list[GovernanceIssue] = []
    issues.extend(_web_search_guardrail(registry))
    issues.extend(_weather_guardrail(registry))
    return issues


def _web_search_guardrail(registry: SkillRegistry) -> list[GovernanceIssue]:
    alias = registry.resolve_alias("web_search")
    capability = registry.capabilities.get("web_search")
    operation = registry.get_operation("web_search", "search")
    issues: list[GovernanceIssue] = []
    if alias is None:
        issues.append(
            _guardrail_issue("web_search_missing_alias", "aliases.web_search")
        )
    if capability is None:
        issues.append(
            _guardrail_issue("web_search_missing_capability", "capabilities.web_search")
        )
        return issues
    if capability.status == "active":
        issues.append(
            _guardrail_issue(
                "web_search_must_stay_disabled",
                "capabilities.web_search.status",
                "web_search 必须保持 hidden/disabled，避免误暴露不稳定外部搜索。",
            )
        )
    if not capability.disabled_reason:
        issues.append(
            _guardrail_issue(
                "web_search_missing_disabled_reason",
                "capabilities.web_search.disabled_reason",
            )
        )
    if operation is None or operation.risk != "external_network":
        issues.append(
            _guardrail_issue(
                "web_search_invalid_risk",
                "capabilities.web_search.operations.search.risk",
                "web_search.search 必须声明 external_network 风险。",
            )
        )
    return issues


def _weather_guardrail(registry: SkillRegistry) -> list[GovernanceIssue]:
    alias = registry.resolve_alias("get_weather_forecast")
    capability = registry.capabilities.get("get_weather_forecast")
    operation = registry.get_operation("get_weather_forecast", "query_forecast")
    issues: list[GovernanceIssue] = []
    if alias is None:
        issues.append(
            _guardrail_issue(
                "weather_missing_alias",
                "aliases.get_weather_forecast",
            )
        )
    if capability is None:
        issues.append(
            _guardrail_issue(
                "weather_missing_capability",
                "capabilities.get_weather_forecast",
            )
        )
        return issues
    if capability.status != "active":
        issues.append(
            _guardrail_issue(
                "weather_must_stay_active",
                "capabilities.get_weather_forecast.status",
                "get_weather_forecast 必须保持 active，作为可用 external_network 正例。",
            )
        )
    if operation is None or operation.risk != "external_network":
        issues.append(
            _guardrail_issue(
                "weather_invalid_risk",
                "capabilities.get_weather_forecast.operations.query_forecast.risk",
                "get_weather_forecast.query_forecast 必须声明 external_network 风险。",
            )
        )
    return issues


def _guardrail_issue(
    code: str,
    location: str,
    message: str | None = None,
) -> GovernanceIssue:
    return GovernanceIssue(
        code=code,
        location=location,
        message=message or f"关键 Registry guardrail 失败：{code}",
    )


def main() -> int:
    """命令行入口：输出简洁检查结果。"""
    issues = check_skill_registry()
    if not issues:
        print("OK: Skill Registry 治理检查通过。")
        return 0
    print("ERROR: Skill Registry 治理检查失败：")
    for issue in issues:
        print(f"- [{issue.code}] {issue.location}: {issue.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
