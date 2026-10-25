"""管理员查看运行中的提示词，源文件通过版本控制维护。"""

from pathlib import Path

from fastapi import Depends, Header, HTTPException, Query
from shared.roles import Permission

from agent import prompts
from agent.api import api_router
from agent.auth import parse_identity, require_identity_permission
from agent.config import settings
from agent.plugins import PluginError, list_plugins


def admin_identity(authorization: str | None = Header(default=None)):
    """提示词内容和重新加载仅向管理调试权限开放。"""
    return require_identity_permission(
        parse_identity(authorization), Permission.ADMIN_DEBUG
    )


def _resolve_prompt_business(
    business: str | None,
) -> tuple[str | None, Path | None, bool]:
    """解析要查看的业务；仅当前启用业务允许重新加载。"""
    active = settings.plugins.active or None
    requested = business.strip() if business else None
    if requested is None:
        if active is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "prompt_unavailable",
                    "message": "当前进程没有启用业务",
                },
            )
        return active, None, True
    if requested == active:
        return active, None, True

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

    entry = next((scan for scan in scans if scan.name == requested), None)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "business_not_found", "message": "业务不存在"},
        )
    if entry.manifest is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "business_manifest_invalid",
                "message": "业务清单不可用",
                "meta": {"error_code": entry.error_code},
            },
        )
    return entry.name, entry.manifest.system_prompt_path, False


@api_router.get("/admin/prompts", dependencies=[Depends(admin_identity)])
def list_admin_prompts(business: str | None = Query(default=None)):
    """返回运行时缓存中的模板，可预览其他业务的 system prompt。"""
    selected, system_prompt_path, is_active = _resolve_prompt_business(business)
    items = prompts.inspect_prompts(
        system_prompt_path,
        business=selected,
        system_active=is_active,
    )
    return {
        "items": items,
        "total": len(items),
        "business": selected,
        "active_business": settings.plugins.active or None,
    }


@api_router.post("/admin/prompts/reload", dependencies=[Depends(admin_identity)])
def reload_admin_prompts(business: str | None = Query(default=None)):
    """重新读取当前启用业务的模板；不承诺更新已启动对话或其他进程。"""
    selected, _system_prompt_path, is_active = _resolve_prompt_business(business)
    if not is_active:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "business_not_active",
                "message": "只能重新加载当前启用业务的提示词",
            },
        )
    prompts.reload()
    prompts.inspect_prompts()
    label = f"「{selected}」" if selected else ""
    return {
        "status": "ok",
        "message": f"当前 Agent 进程已重新加载{label}模板，新建上下文时生效",
    }
