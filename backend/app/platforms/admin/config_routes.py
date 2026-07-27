"""Admin 配置管理 API — Skills/Prompts/Config/Cache。"""

from dataclasses import asdict
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.domains.users.dependencies import require_admin
from app.application.admin_config_use_case import (
    list_prompt_templates,
    reload_prompt_templates,
)
from app.skills import clear_skill_cache, get_skill_manager
from app.skills.metadata import (
    SkillPermissionLevel,
    metadata_to_dict,
    set_skill_enabled_state,
)
from app.ops.skill_route_eval import (
    active_eval_tools,
    default_route_cases_path,
    evaluate_route_recall,
    load_route_cases,
    preview_route_recall,
)
from app.shared.config import settings
from app.infra.skill_cache import clear_cache

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["admin-config"],
    dependencies=[Depends(require_admin)],
)


class SkillEnablementRequest(BaseModel):
    """Skill 启用状态变更请求。"""

    enabled: bool
    disabled_reason: str | None = Field(default=None, max_length=200)


class SkillRouteRecallRequest(BaseModel):
    """Skill 召回单条预览请求。"""

    message: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class SkillRouteRecallEvalRequest(BaseModel):
    """Skill 召回 JSON 测试集评测请求。"""

    top_k: int = Field(default=5, ge=1, le=20)


@router.get("/skills")
def list_skills() -> dict:
    """列出所有注册的 Skill。"""
    manager = get_skill_manager()
    skills = []
    for skill_def in manager.list_skills():
        skill = manager.get_skill(skill_def.name)
        if skill:
            metadata = metadata_to_dict(skill)
            skills.append(
                {
                    "name": skill.name(),
                    "description": skill.description(),
                    "parameters_schema": skill.parameters_schema(),
                    "metadata": metadata,
                    "status": _skill_status(metadata),
                }
            )
    summary = _build_skill_summary(skills)
    return {"items": skills, "total": len(skills), "summary": summary}


@router.post("/skills/route-recall")
def preview_skill_route_recall(request: SkillRouteRecallRequest) -> dict:
    """预览单条业务输入的 Skill 候选召回。"""
    candidates = preview_route_recall(
        request.message,
        active_eval_tools(),
        top_k=request.top_k,
    )
    return {
        "message": request.message,
        "top_k": request.top_k,
        "candidates": [asdict(candidate) for candidate in candidates],
    }


@router.get("/skills/route-recall/dataset")
def get_skill_route_recall_dataset() -> dict:
    """读取 JSON 维护的 Skill 召回测试集。"""
    path = default_route_cases_path()
    cases = load_route_cases(path)
    return {
        "dataset": {
            "path": path.name,
            "format": path.suffix.removeprefix("."),
            "total": len(cases),
        },
        "items": [asdict(case) for case in cases],
    }


@router.post("/skills/route-recall/evaluate")
def evaluate_skill_route_recall_dataset(
    request: SkillRouteRecallEvalRequest,
) -> dict:
    """批量评测 JSON 测试集的 Skill 候选召回率。"""
    path = default_route_cases_path()
    cases = load_route_cases(path)
    report = evaluate_route_recall(cases, active_eval_tools(), top_k=request.top_k)
    return {
        "dataset": {
            "path": path.name,
            "format": path.suffix.removeprefix("."),
            "total": len(cases),
        },
        "top_k": request.top_k,
        "report": asdict(report),
    }


@router.put("/skills/{skill_name}/enabled")
def update_skill_enabled(skill_name: str, request: SkillEnablementRequest) -> dict:
    """启用或禁用指定 Skill。"""
    manager = get_skill_manager()
    skill = manager.get_skill(skill_name)
    if skill is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SKILL_NOT_FOUND", "detail": "Skill 不存在"},
        )

    metadata = set_skill_enabled_state(
        skill_name,
        enabled=request.enabled,
        disabled_reason=request.disabled_reason,
    ).model_dump(mode="json")
    clear_skill_cache()
    logger.info(
        "Admin 更新 Skill 启用状态 | skill=%s | enabled=%s",
        skill_name,
        request.enabled,
    )
    return {
        "name": skill.name(),
        "description": skill.description(),
        "parameters_schema": skill.parameters_schema(),
        "metadata": metadata,
        "status": _skill_status(metadata),
    }


def _build_skill_summary(skills: list[dict]) -> dict[str, int]:
    total = len(skills)
    disabled = sum(1 for item in skills if item["status"] == "disabled")
    admin_only = sum(1 for item in skills if item["status"] == "admin_only")
    return {
        "total": total,
        "enabled": total - disabled,
        "disabled": disabled,
        "admin_only": admin_only,
    }


def _skill_status(metadata: dict) -> str:
    if metadata.get("enabled") is False:
        return "disabled"
    if metadata.get("permission_level") == SkillPermissionLevel.ADMIN.value:
        return "admin_only"
    return "active"


@router.get("/prompts")
def list_prompts() -> dict:
    """列出所有 Prompt 模板。"""
    return list_prompt_templates()


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
            "enable_session_summary": settings.ai.enable_session_summary,
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
    from app.skills import clear_skill_cache

    clear_skill_cache()
    cache_count = clear_cache()
    logger.info("Admin 清空缓存 | ttl_cache=%d", cache_count)
    return {"cleared": {"skill_cache": 0, "ttl_cache": cache_count}}


@router.post("/prompts/reload")
def reload_prompts() -> dict:
    """热加载 Prompt 模板。"""
    return reload_prompt_templates(settings.prompts_dir)


__all__ = ["router"]
