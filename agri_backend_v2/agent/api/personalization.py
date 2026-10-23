"""认证用户的个性化与明确记忆管理 API。"""

from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, Query, Response

from agent.api import api_router
from agent.application.question_recommendations import (
    RecommendationRequest,
    RecommendationResponse,
    recommend,
)
from agent.auth import parse_identity, require_identity_permission
from agent.domains.harness.memory.personalization import (
    MemoryCreate,
    MemoryError,
    MemoryPatch,
    SettingsPatch,
    public_settings,
    visible_memories,
)
from agent.platforms.persistence.mongo import personalization_store as store
from shared.roles import Permission


async def identity(authorization: str | None = Header(default=None)):
    """复用 Agent 身份权限，错误响应不暴露存储连接细节。"""
    principal = require_identity_permission(
        parse_identity(authorization), Permission.AGENT_INVOKE
    )
    try:
        yield principal
    except MemoryError as exc:
        raise HTTPException(
            exc.status, {"code": exc.code, "message": str(exc)}
        ) from exc


CurrentUser = Annotated[dict, Depends(identity)]


@api_router.get("/me/personalization")
async def get_settings(user: CurrentUser):
    return public_settings(await store.load(user["user_id"]))


@api_router.post("/me/question-recommendations", response_model=RecommendationResponse)
async def question_recommendations(
    body: RecommendationRequest, user: CurrentUser, response: Response
):
    """按 JWT 当前用户推荐；不允许请求体指定用户或农场身份。"""
    response.headers["Cache-Control"] = "no-store"
    return await recommend(user, body)


@api_router.patch("/me/personalization")
async def patch_settings(body: SettingsPatch, user: CurrentUser):
    return public_settings(await store.update_settings(user["user_id"], body))


@api_router.get("/me/memories")
async def list_memories(
    user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    scope: Literal["user", "user_farm"] | None = None,
    kind: Literal["preference", "habit", "episode"] | None = None,
    status: Literal["candidate", "active", "superseded", "expired", "deleted"]
    | None = None,
):
    """分页前执行可信范围过滤，删除记录不作为可读内容返回。"""
    records = visible_memories(await store.load(user["user_id"]), user["farm_uid"])
    records = [
        m
        for m in records
        if (scope is None or m["scope"] == scope)
        and (kind is None or m["kind"] == kind)
        and (status is None or m["status"] == status)
    ]
    records.sort(key=lambda item: item["updated_at"], reverse=True)
    start = (page - 1) * page_size
    return {
        "items": records[start : start + page_size],
        "total": len(records),
        "page": page,
        "page_size": page_size,
    }


@api_router.post("/me/memories")
async def create_memory(body: MemoryCreate, user: CurrentUser):
    return await store.create_memory(user["user_id"], user["farm_uid"], body)


@api_router.patch("/me/memories/{memory_id}")
async def patch_memory(memory_id: str, body: MemoryPatch, user: CurrentUser):
    return await store.modify_memory(user["user_id"], user["farm_uid"], memory_id, body)


@api_router.delete("/me/memories/{memory_id}")
async def delete_memory(memory_id: str, user: CurrentUser):
    await store.modify_memory(user["user_id"], user["farm_uid"], memory_id)
    return {"memory_id": memory_id, "deleted": True}


@api_router.post("/me/memories/clear")
async def clear_memories(user: CurrentUser):
    return await store.clear_memories(user["user_id"], user["farm_uid"])
