"""Skill Capability Registry YAML loader。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


REGISTRY_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class DomainDefinition:
    """业务 domain 治理定义。"""

    name: str
    owner: str
    description: str = ""
    default_context_dependencies: tuple[str, ...] = ()
    default_policy: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationDefinition:
    """Capability 内的 operation 定义。"""

    name: str
    risk: str
    legacy_aliases: tuple[str, ...] = ()
    description: str = ""
    confirmation: str | None = None
    cache_invalidation: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityDefinition:
    """业务能力定义。"""

    name: str
    domain: str
    capability: str
    description: str
    examples: tuple[str, ...]
    anti_examples: tuple[str, ...]
    tags: tuple[str, ...]
    version: str
    owner: str
    status: str
    operations: dict[str, OperationDefinition]
    context_dependencies: tuple[str, ...] = ()
    cache_invalidation: tuple[str, ...] = ()
    disabled_reason: str | None = None


@dataclass(frozen=True)
class AliasDefinition:
    """旧 tool name 到 capability operation 的兼容映射。"""

    legacy_name: str
    capability: str
    operation: str
    status: str = "active"
    reason: str = ""

    @property
    def target(self) -> str:
        return f"{self.capability}.{self.operation}"


@dataclass(frozen=True)
class SkillRegistry:
    """加载后的 Skill Capability Registry。"""

    domains: dict[str, DomainDefinition]
    capabilities: dict[str, CapabilityDefinition]
    aliases: dict[str, AliasDefinition]

    def resolve_alias(self, legacy_name: str) -> AliasDefinition | None:
        return self.aliases.get(legacy_name)

    def get_operation(
        self, capability_name: str, operation_name: str
    ) -> OperationDefinition | None:
        capability = self.capabilities.get(capability_name)
        if capability is None:
            return None
        return capability.operations.get(operation_name)


def load_skill_registry(registry_dir: Path | str | None = None) -> SkillRegistry:
    """从 registry 目录加载 domains、skills 和 aliases。"""
    base_dir = Path(registry_dir) if registry_dir is not None else REGISTRY_DIR
    return SkillRegistry(
        domains=_load_domains(base_dir / "domains.yaml"),
        capabilities=_load_capabilities(base_dir / "skills.yaml"),
        aliases=_load_aliases(base_dir / "aliases.yaml"),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} 顶层必须是 mapping")
    return payload


def _load_domains(path: Path) -> dict[str, DomainDefinition]:
    domains = {}
    for item in _as_list(_load_yaml(path).get("domains")):
        name = str(item.get("name", ""))
        domains[name] = DomainDefinition(
            name=name,
            owner=str(item.get("owner", "")),
            description=str(item.get("description", "")),
            default_context_dependencies=tuple(
                _as_str_list(item.get("default_context_dependencies"))
            ),
            default_policy=dict(item.get("default_policy") or {}),
        )
    return domains


def _load_capabilities(path: Path) -> dict[str, CapabilityDefinition]:
    capabilities = {}
    for item in _as_list(_load_yaml(path).get("capabilities")):
        operations = {
            name: OperationDefinition(
                name=name,
                risk=str(operation.get("risk", "")),
                legacy_aliases=tuple(_as_str_list(operation.get("legacy_aliases"))),
                description=str(operation.get("description", "")),
                confirmation=operation.get("confirmation"),
                cache_invalidation=tuple(
                    _as_str_list(operation.get("cache_invalidation"))
                ),
            )
            for name, operation in dict(item.get("operations") or {}).items()
        }
        name = str(item.get("name", ""))
        capabilities[name] = CapabilityDefinition(
            name=name,
            domain=str(item.get("domain", "")),
            capability=str(item.get("capability", "")),
            description=str(item.get("description", "")),
            examples=tuple(_as_str_list(item.get("examples"))),
            anti_examples=tuple(_as_str_list(item.get("anti_examples"))),
            tags=tuple(_as_str_list(item.get("tags"))),
            version=str(item.get("version", "")),
            owner=str(item.get("owner", "")),
            status=str(item.get("status", "")),
            operations=operations,
            context_dependencies=tuple(
                _as_str_list(item.get("context_dependencies"))
            ),
            cache_invalidation=tuple(_as_str_list(item.get("cache_invalidation"))),
            disabled_reason=item.get("disabled_reason"),
        )
    return capabilities


def _load_aliases(path: Path) -> dict[str, AliasDefinition]:
    aliases = {}
    for item in _as_list(_load_yaml(path).get("aliases")):
        legacy_name = str(item.get("legacy_name", ""))
        aliases[legacy_name] = AliasDefinition(
            legacy_name=legacy_name,
            capability=str(item.get("capability", "")),
            operation=str(item.get("operation", "")),
            status=str(item.get("status", "active")),
            reason=str(item.get("reason", "")),
        )
    return aliases


def _as_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Registry 列表字段必须是 list")
    return [dict(item) for item in value]


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
