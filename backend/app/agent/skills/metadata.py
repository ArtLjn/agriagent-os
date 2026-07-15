"""Skill runtime metadata。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from app.core.compat import StrEnum
from app.infra.pending_actions import WRITE_SKILLS, get_cache_groups_for_skill
from app.agent.skills.registry import load_skill_registry


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
    domain: str | None = None
    capability: str | None = None
    operation: str | None = None
    legacy_alias: str | None = None
    operation_risk: str | None = None
    alias_status: str | None = None
    context_dependencies: list[str] = Field(default_factory=list)
    cache_invalidation: list[str] = Field(default_factory=list)
    confirmation_schema: ConfirmationSchema = Field(default_factory=ConfirmationSchema)
    evaluation_tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    disabled_reason: str | None = None
    metadata_incomplete: bool = False


_DEFAULT_WRITE_CONFIRMATION = ConfirmationSchema(
    target_fields=["skill_name"],
    changed_fields=["params"],
    inferred_fields=["original_input"],
    editable_fields=["params"],
)

_EXTERNAL_NETWORK_SKILLS = frozenset({"web_search", "weather"})
_WEB_SEARCH_DISABLED_REASON = "SearXNG 引擎不稳定（CAPTCHA/限流），暂禁用"

_WRITE_CONFIRM_SKILLS = WRITE_SKILLS

_READ_SKILL_METADATA: dict[str, dict[str, Any]] = {
    "get_cost_analytics": {
        "context_dependencies": ["farm", "cost_records"],
        "evaluation_tags": ["read", "cost", "analytics"],
    },
    "get_cost_summary": {
        "context_dependencies": ["farm", "cost_records"],
        "evaluation_tags": ["read", "cost", "summary"],
    },
    "get_debt_summary": {
        "context_dependencies": ["farm", "cost_records"],
        "evaluation_tags": ["read", "debt", "summary"],
    },
    "get_crop_cycle_info": {
        "context_dependencies": ["farm", "active_cycles"],
        "evaluation_tags": ["read", "crop_cycle"],
    },
    "get_crop_cycles": {
        "context_dependencies": ["farm", "crop_cycles"],
        "evaluation_tags": ["read", "crop_cycle", "list"],
    },
    "get_recent_farm_logs": {
        "context_dependencies": ["farm", "farm_logs"],
        "evaluation_tags": ["read", "farm_logs"],
    },
    "get_farm_status": {
        "context_dependencies": ["farm"],
        "evaluation_tags": ["read", "farm_status"],
    },
    "get_labor_payables": {
        "context_dependencies": ["workers", "unpaid_labor", "crop_cycles"],
        "evaluation_tags": ["read", "labor", "payable"],
    },
    "get_workers": {
        "context_dependencies": ["workers", "unpaid_labor"],
        "evaluation_tags": ["read", "worker", "labor"],
    },
    "get_cost_categories": {
        "context_dependencies": ["cost_categories"],
        "evaluation_tags": ["read", "cost_category"],
    },
    "get_planting_units": {
        "context_dependencies": ["farm", "crop_cycles", "planting_units"],
        "evaluation_tags": ["read", "planting_unit"],
    },
    "get_crop_templates": {
        "context_dependencies": ["farm", "crop_templates"],
        "evaluation_tags": ["read", "crop_template"],
    },
    "get_operation_work_orders": {
        "context_dependencies": ["crop_cycles", "planting_units", "workers"],
        "evaluation_tags": ["read", "operation_work_order", "labor"],
    },
}

_WRITE_SKILL_METADATA: dict[str, dict[str, Any]] = {
    "create_cost_record": {
        "context_dependencies": ["farm", "cost_categories"],
        "evaluation_tags": ["write", "cost", "record"],
    },
    "create_crop_cycle": {
        "context_dependencies": ["farm", "crop_templates"],
        "evaluation_tags": ["write", "crop_cycle"],
    },
    "create_crop_template": {
        "context_dependencies": ["farm"],
        "evaluation_tags": ["write", "crop_template"],
    },
    "create_operation_work_order": {
        "context_dependencies": ["farm", "crop_cycles", "planting_units", "workers"],
        "evaluation_tags": ["write", "operation_work_order", "labor"],
    },
    "log_farm_activity": {
        "context_dependencies": ["farm", "active_cycles"],
        "evaluation_tags": ["write", "farm_logs"],
    },
    "manage_workers": {
        "context_dependencies": ["workers", "unpaid_labor"],
        "evaluation_tags": ["write", "worker", "labor"],
    },
    "manage_wages": {
        "context_dependencies": ["workers", "crop_cycles", "unpaid_labor"],
        "evaluation_tags": ["write", "labor", "wage"],
    },
    "delete_cost_record": {
        "context_dependencies": ["cost_records"],
        "evaluation_tags": ["write", "cost", "delete"],
    },
    "manage_cost_categories": {
        "context_dependencies": ["cost_categories"],
        "evaluation_tags": ["write", "cost_category"],
    },
    "manage_planting_units": {
        "context_dependencies": ["crop_cycles", "planting_units"],
        "evaluation_tags": ["write", "planting_unit"],
    },
    "manage_crop_templates": {
        "context_dependencies": ["crop_templates", "crop_cycles"],
        "risk_level": SkillRiskLevel.HIGH,
        "evaluation_tags": ["write", "crop_template"],
    },
    "manage_farm_logs": {
        "context_dependencies": ["farm_logs", "crop_cycles"],
        "evaluation_tags": ["write", "farm_logs"],
    },
    "delete_crop_cycle": {
        "context_dependencies": ["crop_cycles", "farm_logs", "cost_records"],
        "risk_level": SkillRiskLevel.HIGH,
        "evaluation_tags": ["write", "crop_cycle", "delete"],
    },
    "manage_user_settings": {
        "context_dependencies": ["user"],
        "evaluation_tags": ["write", "user_settings"],
    },
    "settle_debt": {
        "context_dependencies": ["farm", "cost_records"],
        "evaluation_tags": ["write", "debt", "settlement"],
    },
    "settle_labor_payment": {
        "context_dependencies": ["workers", "unpaid_labor", "operation_work_orders"],
        "evaluation_tags": ["write", "labor", "settlement"],
    },
    "update_crop_cycle": {
        "context_dependencies": ["farm", "active_cycles"],
        "evaluation_tags": ["write", "crop_cycle", "date_update"],
    },
    "update_crop_stage": {
        "context_dependencies": ["farm", "active_cycles"],
        "evaluation_tags": ["write", "crop_stage"],
    },
    "update_operation_work_order": {
        "context_dependencies": ["operation_work_orders", "planting_units", "workers"],
        "evaluation_tags": ["write", "operation_work_order", "labor"],
    },
}

_EXTERNAL_NETWORK_SKILL_METADATA: dict[str, dict[str, Any]] = {
    "weather": {
        "context_dependencies": ["farm", "weather_location"],
        "evaluation_tags": ["read", "weather", "external_network"],
        "enabled": True,
    },
    "web_search": {
        "context_dependencies": ["external_search"],
        "evaluation_tags": ["read", "search", "external_network"],
        "enabled": False,
        "disabled_reason": _WEB_SEARCH_DISABLED_REASON,
    },
}

_RUNTIME_ENABLEMENT_OVERRIDES: dict[str, dict[str, Any]] = {}
_USER_SETTINGS_WRITE_FIELDS = (
    "display_name",
    "default_city",
    "default_lat",
    "default_lon",
    "assistant_role",
)
_REGISTRY_RISK_TO_METADATA: dict[str, tuple[SkillPermissionLevel, SkillRiskLevel]] = {
    "read": (SkillPermissionLevel.READ, SkillRiskLevel.LOW),
    "write_confirm": (SkillPermissionLevel.WRITE_CONFIRM, SkillRiskLevel.MEDIUM),
    "write_high": (SkillPermissionLevel.WRITE_CONFIRM, SkillRiskLevel.HIGH),
    "external_network": (SkillPermissionLevel.EXTERNAL_NETWORK, SkillRiskLevel.LOW),
}


def get_skill_metadata(skill: Any) -> SkillMetadata:
    """从 Skill 读取 metadata，缺失时提供兼容默认值。"""
    skill_name = _get_skill_name(skill)
    default_metadata = _get_known_default_metadata(skill_name)
    raw_metadata = _call_metadata(skill)
    if raw_metadata is not None:
        return _metadata_from_explicit(skill_name, raw_metadata, default_metadata)

    if default_metadata is not None:
        return SkillMetadata.model_validate(
            _apply_runtime_enablement(skill_name, default_metadata)
        )

    if skill_name in WRITE_SKILLS:
        return _metadata_from_legacy_write(skill_name)

    return _metadata_from_legacy_read(skill_name)


def _metadata_from_explicit(
    skill_name: str,
    raw_metadata: Any,
    default_metadata: dict[str, Any] | None,
) -> SkillMetadata:
    if default_metadata is not None and isinstance(raw_metadata, Mapping):
        raw_metadata = {**default_metadata, **raw_metadata}
        if skill_name in _WRITE_CONFIRM_SKILLS:
            raw_metadata["cache_invalidation"] = get_cache_groups_for_skill(skill_name)
    raw_metadata = _apply_runtime_enablement(skill_name, raw_metadata)
    metadata = SkillMetadata.model_validate(raw_metadata)
    metadata.metadata_incomplete = False
    return metadata


def _metadata_from_legacy_write(skill_name: str) -> SkillMetadata:
    return SkillMetadata.model_validate(
        _apply_runtime_enablement(
            skill_name,
            {
                "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
                "risk_level": SkillRiskLevel.MEDIUM,
                "cache_invalidation": get_cache_groups_for_skill(skill_name),
                "confirmation_schema": _DEFAULT_WRITE_CONFIRMATION,
                "evaluation_tags": ["write"],
                "metadata_incomplete": True,
            },
        )
    )


def _metadata_from_legacy_read(skill_name: str) -> SkillMetadata:
    permission_level = (
        SkillPermissionLevel.EXTERNAL_NETWORK
        if skill_name in _EXTERNAL_NETWORK_SKILLS
        else SkillPermissionLevel.READ
    )
    return SkillMetadata.model_validate(
        _apply_runtime_enablement(
            skill_name,
            {
                "permission_level": permission_level,
                "risk_level": SkillRiskLevel.LOW,
                "evaluation_tags": ["read"],
                "metadata_incomplete": True,
            },
        )
    )


def get_skill_call_metadata(skill: Any, params: Mapping[str, Any]) -> SkillMetadata:
    skill_name = _get_skill_name(skill)
    metadata = get_skill_metadata(skill)
    operation_name = _operation_name_from_params(skill_name, params)
    registry_metadata = (
        resolve_skill_capability_metadata(skill_name, operation_name)
        if operation_name is not None
        else None
    )
    if registry_metadata is None:
        return metadata
    payload = metadata.model_dump(mode="python")
    payload.update(registry_metadata)
    return SkillMetadata.model_validate(_apply_runtime_enablement(skill_name, payload))


def _operation_name_from_params(skill_name: str, params: Mapping[str, Any] | None):
    if not isinstance(params, Mapping):
        return None
    operation = params.get("operation")
    if operation:
        operation_name = str(operation)
        if skill_name == "manage_cost_categories" and operation_name in {
            "create_category",
            "delete_category",
            "manage_category",
        }:
            return "manage_category"
        return operation_name
    if skill_name == "manage_cost_categories":
        action = params.get("action")
        if action in {"create", "delete"}:
            return "manage_category"
        if action == "query":
            return "query_categories"
        return None
    if skill_name == "manage_planting_units":
        action = params.get("action")
        if action in {"create", "update", "delete"}:
            return "manage_units"
        if action == "query":
            return "query_units"
        return None
    if skill_name != "manage_user_settings":
        return None
    return (
        "update_settings"
        if any(params.get(key) is not None for key in _USER_SETTINGS_WRITE_FIELDS)
        else "query_settings"
    )


def set_skill_enabled_state(
    skill_name: str, *, enabled: bool, disabled_reason: str | None = None
) -> SkillMetadata:
    """设置运行时 Skill 启用状态。"""
    if enabled:
        _RUNTIME_ENABLEMENT_OVERRIDES[skill_name] = {
            "enabled": True,
            "disabled_reason": None,
        }
    else:
        _RUNTIME_ENABLEMENT_OVERRIDES[skill_name] = {
            "enabled": False,
            "disabled_reason": disabled_reason or "管理员手动禁用",
        }
    return get_skill_metadata(
        type("_SkillRef", (), {"name": lambda _self: skill_name})()
    )


def clear_skill_enabled_state(skill_name: str | None = None) -> None:
    """清除运行时 Skill 启用状态覆盖。"""
    if skill_name is None:
        _RUNTIME_ENABLEMENT_OVERRIDES.clear()
        return
    _RUNTIME_ENABLEMENT_OVERRIDES.pop(skill_name, None)


def _apply_runtime_enablement(
    skill_name: str, metadata: Mapping[str, Any]
) -> dict[str, Any]:
    merged = dict(metadata)
    override = _RUNTIME_ENABLEMENT_OVERRIDES.get(skill_name)
    if override:
        merged.update(override)
    return merged


def _get_known_default_metadata(skill_name: str) -> dict[str, Any] | None:
    registry_metadata = resolve_skill_capability_metadata(skill_name)
    if skill_name in _WRITE_CONFIRM_SKILLS:
        metadata = {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "cache_invalidation": get_cache_groups_for_skill(skill_name),
            "confirmation_schema": _DEFAULT_WRITE_CONFIRMATION,
            "metadata_incomplete": False,
        }
        metadata.update(_WRITE_SKILL_METADATA.get(skill_name, {}))
        if registry_metadata is not None:
            metadata.update(registry_metadata)
        return metadata

    if skill_name in _READ_SKILL_METADATA:
        metadata = {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "metadata_incomplete": False,
            **_READ_SKILL_METADATA[skill_name],
        }
        if registry_metadata is not None:
            metadata.update(registry_metadata)
        return metadata

    if skill_name in _EXTERNAL_NETWORK_SKILL_METADATA:
        metadata = {
            "permission_level": SkillPermissionLevel.EXTERNAL_NETWORK,
            "risk_level": SkillRiskLevel.LOW,
            "metadata_incomplete": False,
            **_EXTERNAL_NETWORK_SKILL_METADATA[skill_name],
        }
        if registry_metadata is not None:
            metadata.update(registry_metadata)
        return metadata

    return registry_metadata


def resolve_skill_capability_metadata(
    skill_name: str,
    operation_name: str | None = None,
) -> dict[str, Any] | None:
    """从 Registry 解析 legacy alias 或 canonical capability metadata。"""
    try:
        registry = load_skill_registry()
    except (OSError, ValueError):
        return None
    alias = registry.resolve_alias(skill_name)
    alias_operation = (
        registry.get_operation(alias.capability, operation_name)
        if alias is not None and operation_name is not None
        else None
    )
    if alias is not None and alias_operation is None:
        capability_name = alias.capability
        resolved_operation = alias.operation
        legacy_alias = alias.legacy_name
        alias_status = alias.status
    elif alias is not None and alias_operation is not None:
        capability_name = alias.capability
        resolved_operation = operation_name
        legacy_alias = None
        alias_status = None
    else:
        capability_name = skill_name
        resolved_operation = operation_name
        legacy_alias = None
        alias_status = None
    capability = registry.capabilities.get(capability_name)
    if capability is None:
        return None
    operation = (
        registry.get_operation(capability_name, resolved_operation)
        if resolved_operation
        else None
    )
    permission_level, risk_level = _REGISTRY_RISK_TO_METADATA.get(
        operation.risk if operation is not None else "read",
        (SkillPermissionLevel.READ, SkillRiskLevel.LOW),
    )
    cache_invalidation = list(capability.cache_invalidation)
    if operation is not None and operation.cache_invalidation:
        cache_invalidation = list(operation.cache_invalidation)
    return {
        "permission_level": permission_level,
        "risk_level": risk_level,
        "domain": capability.domain,
        "capability": capability.name,
        "operation": operation.name if operation is not None else None,
        "legacy_alias": legacy_alias,
        "operation_risk": operation.risk if operation is not None else None,
        "alias_status": alias_status,
        "context_dependencies": list(capability.context_dependencies),
        "cache_invalidation": cache_invalidation,
        "evaluation_tags": list(capability.tags),
        "enabled": capability.status == "active",
        "disabled_reason": (
            capability.disabled_reason if capability.status != "active" else None
        ),
        "metadata_incomplete": False,
    }


def metadata_to_dict(skill: Any) -> dict[str, Any]:
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
