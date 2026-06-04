"""Admin 配置管理 API — Skills/Prompts/Config/Cache。"""

import logging

from fastapi import APIRouter

from app.core.config import settings
from app.agent.prompt_registry import get_registry
from app.infra.skill_cache import clear_cache
from app.agent.skills import get_skill_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-config"])


@router.get("/skills")
def list_skills() -> dict:
    """列出所有注册的 Skill。"""
    manager = get_skill_manager()
    skills = []
    for skill_def in manager.list_skills():
        skill = manager.get_skill(skill_def.name)
        if skill:
            skills.append(
                {
                    "name": skill.name(),
                    "description": skill.description(),
                    "parameters_schema": skill.parameters_schema(),
                    "status": "active",
                }
            )
    return {"items": skills, "total": len(skills)}


@router.get("/prompts")
def list_prompts() -> dict:
    """列出所有 Prompt 模板。"""
    registry = get_registry()
    items = []
    for name in registry.list_names():
        content = registry.get(name)
        versions = registry.list_versions(name)
        items.append(
            {
                "name": name,
                "version": versions[0] if versions else "unknown",
                "active": True,
                "content_length": len(content),
                "content": content,
            }
        )
    return {"items": items, "total": len(items)}


@router.get("/config")
def get_config() -> dict:
    """运行时配置查看（敏感字段脱敏）。"""

    def _mask_key(key: str) -> str:
        if not key or len(key) <= 8:
            return "***"
        return key[:4] + "***" + key[-4:]

    return {
        "ai": {
            "model": settings.ai.model,
            "base_url": settings.ai_base_url,
            "api_key": _mask_key(settings.ai_api_key),
            "enable_thinking": settings.ai.enable_thinking,
        },
        "trace": {
            "batch_size": settings.trace.batch_size,
            "flush_interval": settings.trace.flush_interval,
            "trace_ttl_days": settings.trace.trace_ttl_days,
        },
        "token_quota": {
            "monthly_limit": settings.token_quota.monthly_limit,
            "weekly_limit": settings.token_quota.weekly_limit,
            "over_quota_action": settings.token_quota.over_quota_action,
        },
        "langsmith": {
            "enabled": settings.langsmith_config.enabled,
            "project": settings.langsmith_config.project_name,
        },
    }


@router.post("/cache/clear")
def clear_all_cache() -> dict:
    """清空所有 Skill 缓存。"""
    from app.agent.skills import clear_skill_cache

    clear_skill_cache()
    cache_count = clear_cache()
    logger.info("Admin 清空缓存 | ttl_cache=%d", cache_count)
    return {"cleared": {"skill_cache": 0, "ttl_cache": cache_count}}


@router.post("/prompts/reload")
def reload_prompts() -> dict:
    """热加载 Prompt 模板。"""
    registry = get_registry()
    registry.reload(settings.prompts_dir)
    return {"status": "ok", "message": "模板已重新加载"}


__all__ = ["router"]
