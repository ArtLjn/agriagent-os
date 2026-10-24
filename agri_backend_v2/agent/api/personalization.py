"""认证用户的个性化与明确记忆管理 API。"""

from typing import Annotated, Literal

from fastapi import Depends, Header, HTTPException, Path, Query, Response
from pymongo.errors import PyMongoError

from agent.api import api_router
from agent.application.question_recommendations import (
    RecommendationRequest,
    RecommendationResponse,
    recommend,
)
from agent.auth import parse_identity, require_identity_permission
from agent.domains.harness.memory.personalization import (
    MemoryCategory,
    MemoryCreate,
    MemoryError,
    MemoryPatch,
    SettingsPatch,
    public_settings,
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
    return public_settings(await store.load(user["user_id"], memory_ids=[]))


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
    category: MemoryCategory | None = None,
    status: Literal["candidate", "active", "superseded", "expired", "deleted"]
    | None = None,
):
    """分页前执行可信范围过滤，删除记录不作为可读内容返回。"""
    return await store.page_memories(
        user["user_id"],
        user["farm_uid"],
        page=page,
        page_size=page_size,
        scope=scope,
        kind=kind,
        category=category,
        status=status,
    )


@api_router.get("/me/memory-learning/{turn_id}")
async def get_memory_learning_status(
    turn_id: Annotated[str, Path(min_length=1, max_length=128)],
    user: CurrentUser,
    response: Response,
):
    """后台学习可能晚于聊天 SSE 完成，独立查询真实提交结果且禁止共享缓存。"""
    from agent.domains.harness.memory.learning import learning_status

    response.headers["Cache-Control"] = "no-store"
    try:
        return await learning_status(user["user_id"], user["farm_uid"], turn_id)
    except PyMongoError as exc:
        raise MemoryError("memory_status_unavailable", "学习状态暂不可用", 503) from exc


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
