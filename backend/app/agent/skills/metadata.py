"""Skill runtime metadata。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from app.core.compat import StrEnum
from app.infra.pending_actions import WRITE_SKILLS, get_cache_groups_for_skill


class SkillPermissionLevel(StrEnum):
    """Skill 执行权限等级。"""

    READ = "read"
    WRITE_CONFIRM = "write_confirm"
    ADMIN = "admin"
    EXTERNAL_NETWORK = "external_network"


class SkillRiskLevel(StrEnum):
    """Skill 风险等级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConfirmationSchema(BaseModel):
    """写操作确认展示字段。"""

    target_fields: list[str] = Field(default_factory=list)
    changed_fields: list[str] = Field(default_factory=list)
    inferred_fields: list[str] = Field(default_factory=list)
    editable_fields: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class SkillMetadata(BaseModel):
    """Skill runtime metadata。"""

    permission_level: SkillPermissionLevel = SkillPermissionLevel.READ
    risk_level: SkillRiskLevel = SkillRiskLevel.LOW
    context_dependencies: list[str] = Field(default_factory=list)
    cache_invalidation: list[str] = Field(default_factory=list)
    confirmation_schema: ConfirmationSchema = Field(default_factory=ConfirmationSchema)
    evaluation_tags: list[str] = Field(default_factory=list)
    metadata_incomplete: bool = False


_DEFAULT_WRITE_CONFIRMATION = ConfirmationSchema(
    target_fields=["skill_name"],
    changed_fields=["params"],
    inferred_fields=["original_input"],
    editable_fields=["params"],
)

_EXTERNAL_NETWORK_SKILLS = frozenset({"web_search", "get_weather_forecast"})


def get_skill_metadata(skill: Any) -> SkillMetadata:
    """从 Skill 读取 metadata，缺失时提供兼容默认值。"""
    raw_metadata = _call_metadata(skill)
    if raw_metadata is not None:
        metadata = SkillMetadata.model_validate(raw_metadata)
        metadata.metadata_incomplete = False
        return metadata

    skill_name = _get_skill_name(skill)
    if skill_name in WRITE_SKILLS:
        return SkillMetadata(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM,
            risk_level=SkillRiskLevel.MEDIUM,
            cache_invalidation=get_cache_groups_for_skill(skill_name),
            confirmation_schema=_DEFAULT_WRITE_CONFIRMATION,
            evaluation_tags=["write"],
            metadata_incomplete=True,
        )

    permission_level = (
        SkillPermissionLevel.EXTERNAL_NETWORK
        if skill_name in _EXTERNAL_NETWORK_SKILLS
        else SkillPermissionLevel.READ
    )
    return SkillMetadata(
        permission_level=permission_level,
        risk_level=SkillRiskLevel.LOW,
        evaluation_tags=["read"],
        metadata_incomplete=True,
    )


def metadata_to_dict(skill: Any) -> dict[str, Any]:
    """返回可序列化 metadata。"""
    return get_skill_metadata(skill).model_dump(mode="json")


def _call_metadata(skill: Any) -> Any | None:
    metadata_attr = getattr(skill, "metadata", None)
    raw_metadata = metadata_attr() if callable(metadata_attr) else metadata_attr
    if raw_metadata is None:
        return None
    if isinstance(raw_metadata, Mapping):
        return dict(raw_metadata)
    return raw_metadata


def _get_skill_name(skill: Any) -> str:
    name_attr = getattr(skill, "name", None)
    if callable(name_attr):
        return str(name_attr())
    return str(name_attr or "")


__all__ = [
    "ConfirmationSchema",
    "SkillMetadata",
    "SkillPermissionLevel",
    "SkillRiskLevel",
    "get_skill_metadata",
    "metadata_to_dict",
]
