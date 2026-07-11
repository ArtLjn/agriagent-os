"""Skill Capability Registry 结构化校验。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.agent.skills.registry.loader import SkillRegistry


REQUIRED_CAPABILITY_FIELDS = (
    "name",
    "domain",
    "capability",
    "description",
    "examples",
    "anti_examples",
    "tags",
    "version",
    "owner",
    "status",
    "operations",
    "context_dependencies",
)

DISABLED_STATUSES = frozenset({"hidden", "removed"})


@dataclass(frozen=True)
class RegistryValidationIssue:
    """Registry 校验问题，方便测试和脚本输出。"""

    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "location": self.location,
            "message": self.message,
        }


def validate_skill_registry(
    registry: SkillRegistry,
    *,
    expected_aliases: Iterable[str] | None = None,
) -> list[RegistryValidationIssue]:
    """校验 registry 结构和 alias 可解析性。"""
    issues: list[RegistryValidationIssue] = []
    issues.extend(_validate_domains(registry))
    issues.extend(_validate_capabilities(registry))
    issues.extend(_validate_aliases(registry))
    if expected_aliases is not None:
        issues.extend(_validate_expected_aliases(registry, expected_aliases))
    return issues


def _validate_domains(registry: SkillRegistry) -> list[RegistryValidationIssue]:
    issues = []
    for name, domain in registry.domains.items():
        if not name:
            issues.append(
                _issue("missing_required_field", "domains.<empty>.name", "缺少 domain 名称")
            )
        if not domain.owner:
            issues.append(
                _issue("missing_owner", f"domains.{name}.owner", "domain 缺少 owner")
            )
    return issues


def _validate_capabilities(registry: SkillRegistry) -> list[RegistryValidationIssue]:
    issues = []
    for name, capability in registry.capabilities.items():
        for field_name in REQUIRED_CAPABILITY_FIELDS:
            value = getattr(capability, field_name)
            if not value:
                issues.append(
                    _issue(
                        "missing_required_field",
                        f"capabilities.{name}.{field_name}",
                        f"capability 缺少必填字段 {field_name}",
                    )
                )
        if capability.domain and capability.domain not in registry.domains:
            issues.append(
                _issue(
                    "invalid_domain",
                    f"capabilities.{name}.domain",
                    f"domain 不存在：{capability.domain}",
                )
            )
        if not capability.owner:
            issues.append(
                _issue("missing_owner", f"capabilities.{name}.owner", "缺少 owner")
            )
        if not capability.anti_examples:
            issues.append(
                _issue(
                    "missing_anti_examples",
                    f"capabilities.{name}.anti_examples",
                    "缺少 anti_examples",
                )
            )
        if capability.status in DISABLED_STATUSES and not capability.disabled_reason:
            issues.append(
                _issue(
                    "missing_disabled_reason",
                    f"capabilities.{name}.disabled_reason",
                    "禁用 capability 缺少 disabled_reason",
                )
            )
        if capability.status == "active" and capability.disabled_reason:
            issues.append(
                _issue(
                    "active_capability_has_disabled_reason",
                    f"capabilities.{name}.disabled_reason",
                    "active capability 不应声明 disabled_reason",
                )
            )
        for operation_name, operation in capability.operations.items():
            if not operation.risk:
                issues.append(
                    _issue(
                        "operation_missing_risk",
                        f"capabilities.{name}.operations.{operation_name}.risk",
                        "operation 缺少 risk",
                    )
                )
            if not operation.legacy_aliases:
                issues.append(
                    _issue(
                        "operation_missing_legacy_aliases",
                        f"capabilities.{name}.operations.{operation_name}.legacy_aliases",
                        "operation 缺少 legacy_aliases",
                    )
                )
    return issues


def _validate_aliases(registry: SkillRegistry) -> list[RegistryValidationIssue]:
    issues = []
    for legacy_name, alias in registry.aliases.items():
        operation = registry.get_operation(alias.capability, alias.operation)
        if operation is None:
            issues.append(
                _issue(
                    "invalid_alias_target",
                    f"aliases.{legacy_name}",
                    f"alias 指向不存在目标：{alias.target}",
                )
            )
            continue
        if legacy_name not in operation.legacy_aliases:
            issues.append(
                _issue(
                    "alias_not_declared_on_operation",
                    f"aliases.{legacy_name}",
                    f"operation {alias.target} 未声明 legacy_aliases 包含 {legacy_name}",
                )
            )
    return issues


def _validate_expected_aliases(
    registry: SkillRegistry,
    expected_aliases: Iterable[str],
) -> list[RegistryValidationIssue]:
    issues = []
    for legacy_name in sorted(set(expected_aliases)):
        if legacy_name not in registry.aliases:
            issues.append(
                _issue(
                    "missing_alias",
                    f"aliases.{legacy_name}",
                    f"缺少 legacy tool alias：{legacy_name}",
                )
            )
    return issues


def _issue(code: str, location: str, message: str) -> RegistryValidationIssue:
    return RegistryValidationIssue(code=code, location=location, message=message)
