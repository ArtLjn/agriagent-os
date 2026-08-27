"""管理员 Skill 注册表接口。"""

from __future__ import annotations

from typing import Any

from fastapi import Header

from agent.api import api_router
from agent.auth import parse_identity, require_identity_permission
from agent.domains.harness.tools import loader
from shared.roles import Permission


@api_router.get("/admin/skills")
def list_admin_skills(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """管理员查看 Agent 侧已注册的一级 Skill 及其参数契约。"""
    require_identity_permission(parse_identity(authorization), Permission.ADMIN_DEBUG)

    items = [_serialize_skill(skill) for skill in loader.load_aggregate_skills()]
    items.sort(key=lambda item: item["name"])
    summary = _build_summary(items)
    return {"items": items, "total": len(items), "summary": summary}


def _serialize_skill(skill: Any) -> dict[str, Any]:
    """将运行时 Skill 投影为管理页契约，并为旧元数据补齐安全默认值。"""
    raw_permission = skill._meta.get("permission_level")
    permission_level = raw_permission or _permission_for_skill(skill)
    enabled = skill._meta.get("enabled", True) is not False
    disabled_reason = skill._meta.get("disabled_reason")
    status = (
        "disabled"
        if not enabled
        else ("admin_only" if permission_level == "admin" else "active")
    )
    return {
        "name": skill.name,
        "description": skill.description,
        "parameters_schema": skill.parameters_schema,
        "metadata": {
            "enabled": enabled,
            "disabled_reason": disabled_reason,
            "permission_level": permission_level,
            "risk_level": _risk_for_skill(skill),
            "context_dependencies": list(skill.context_dependencies),
            "cache_invalidation": _list_metadata(skill, "cache_invalidation"),
            "confirmation_schema": _dict_metadata(skill, "confirmation_schema"),
            "evaluation_tags": _list_metadata(skill, "evaluation_tags"),
            "metadata_incomplete": not _has_complete_metadata(skill),
        },
        "status": status,
    }


def _permission_for_skill(skill: Any) -> str:
    """根据 Skill 文档的风险声明推导页面所需的权限标签。"""
    if skill.kind == "local" and skill.name == "web_search":
        return "external_network"
    if skill.risk_level == "mixed":
        return "write_confirm"
    return "read"


def _risk_for_skill(skill: Any) -> str:
    """将运行时风险映射为管理页兼容的风险等级。"""
    if skill.risk_level == "mixed":
        return "medium"
    if skill.risk_level in {"write_high", "high"}:
        return "high"
    return "low"


def _list_metadata(skill: Any, field: str) -> list[Any]:
    value = skill._meta.get(field)
    return list(value) if isinstance(value, list) else []


def _dict_metadata(skill: Any, field: str) -> dict[str, Any]:
    value = skill._meta.get(field)
    return dict(value) if isinstance(value, dict) else {}


def _has_complete_metadata(skill: Any) -> bool:
    required = {
        "permission_level",
        "risk_level",
        "context_dependencies",
        "cache_invalidation",
        "confirmation_schema",
        "evaluation_tags",
    }
    return required.issubset(skill._meta)


def _build_summary(items: list[dict[str, Any]]) -> dict[str, int]:
    disabled = sum(item["status"] == "disabled" for item in items)
    admin_only = sum(item["status"] == "admin_only" for item in items)
    return {
        "total": len(items),
        "enabled": len(items) - disabled,
        "disabled": disabled,
        "admin_only": admin_only,
    }
