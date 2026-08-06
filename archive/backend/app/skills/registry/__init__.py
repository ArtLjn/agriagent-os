"""Skill Capability Registry 加载入口。"""

from app.skills.registry.loader import (
    AliasDefinition,
    CapabilityDefinition,
    DomainDefinition,
    OperationDefinition,
    SkillRegistry,
    load_skill_registry,
)
from app.skills.registry.validation import (
    RegistryValidationIssue,
    validate_skill_registry,
)

__all__ = [
    "AliasDefinition",
    "CapabilityDefinition",
    "DomainDefinition",
    "OperationDefinition",
    "RegistryValidationIssue",
    "SkillRegistry",
    "load_skill_registry",
    "validate_skill_registry",
]
