"""管理员业务目录与进程内切换接口。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from shared.roles import Permission

from agent import prompts
from agent.api import api_router
from agent.auth import parse_identity, require_identity_permission
from agent.config import settings
from agent.domains.harness.tools import loader as skill_loader
from agent.domains.harness.tools.loader import SkillLoadError
from agent.domains.harness.tools.registry import SkillRegistryError
from agent.plugins import (
    PluginError,
    PluginManifest,
    PluginScan,
    list_plugins,
    load_manifest,
)

logger = logging.getLogger(__name__)


class SwitchBusinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9-]*$")


@api_router.get("/admin/businesses")
def list_admin_businesses(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """返回已安装业务的清单状态和当前进程启用的业务。"""
    require_identity_permission(parse_identity(authorization), Permission.ADMIN_DEBUG)

    try:
        scans = list_plugins(settings.plugins.root)
    except (PluginError, OSError, UnicodeError) as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "business_catalog_unavailable",
                "message": "业务目录不可用",
            },
        ) from exc

    items = [_serialize_scan(scan) for scan in scans]
    return {
        "items": items,
        "total": len(items),
        "active": settings.plugins.active or None,
    }


@api_router.put("/admin/businesses/active")
def switch_admin_business(
    request: SwitchBusinessRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """在当前 Agent 进程内切换业务插件；重启后恢复部署配置。"""
    require_identity_permission(parse_identity(authorization), Permission.ADMIN_DEBUG)

    manifest = _load_switch_target(request.name)
    _validate_switch_target(manifest)
    settings.plugins.manifest = manifest
    prompts.reload()
    logger.info("active business switched in-process: %s", manifest.name)
    return _active_payload(manifest)


def _load_switch_target(name: str) -> PluginManifest:
    plugin_dir = settings.plugins.root / name
    if not plugin_dir.is_dir():
        raise HTTPException(
            status_code=404,
            detail={"code": "business_not_found", "message": "业务不存在"},
        )
    try:
        return load_manifest(plugin_dir)
    except PluginError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "business_manifest_invalid",
                "message": "业务清单不可用",
                "meta": {"error_code": exc.code},
            },
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "business_manifest_invalid",
                "message": "业务清单不可用",
                "meta": {"error_code": "plugin_manifest_unreadable"},
            },
        ) from exc


def _validate_switch_target(manifest: PluginManifest) -> None:
    try:
        skill_loader.load_registry([
            skill_loader.core_skills_dir(),
            manifest.skills_dir,
        ])
        manifest.system_prompt_path.read_text(encoding="utf-8")
    except (SkillLoadError, SkillRegistryError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "business_skills_invalid",
                "message": "业务技能加载失败",
                "meta": {"error_code": exc.code},
            },
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "business_prompt_invalid",
                "message": "业务提示词不可读",
            },
        ) from exc


def _active_payload(manifest: PluginManifest) -> dict[str, Any]:
    return {
        "active": manifest.name,
        "display_name": manifest.display_name,
        "skill_count": len(manifest.skill_paths),
    }


def _serialize_scan(scan: PluginScan) -> dict[str, Any]:
    if scan.manifest is None:
        return {
            "name": scan.name,
            "display_name": None,
            "description": None,
            "skill_count": 0,
            "error_code": scan.error_code,
        }
    return {
        "name": scan.name,
        "display_name": scan.manifest.display_name,
        "description": scan.manifest.description,
        "skill_count": len(scan.manifest.skill_paths),
        "error_code": None,
    }
