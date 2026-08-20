"""当前用户资料与设置路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from business.api.deps import get_current_user
from business.api.schemas import StrictRequest
from business.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


class UpdateProfileRequest(StrictRequest):
    nickname: str | None = Field(default=None, min_length=1, max_length=50)
    avatar_url: str | None = Field(default=None, max_length=500)


class UpdateSettingsRequest(StrictRequest):
    default_city: str | None = Field(default=None, max_length=50)
    default_lat: float | None = Field(default=None, ge=-90, le=90)
    default_lon: float | None = Field(default=None, ge=-180, le=180)
    assistant_role: str | None = Field(
        default=None, pattern="^(warm|professional|concise)$"
    )


@router.get("/me")
def get_my_profile(user: dict = Depends(get_current_user)) -> dict:
    profile = user_service.get_user_profile(user["user_id"])
    if profile is None:
        raise HTTPException(status_code=404, detail="用户资料不存在")
    return profile


@router.patch("/me")
def update_my_profile(
    request: UpdateProfileRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    updated = user_service.update_user_profile(
        user["user_id"],
        nickname=request.nickname,
        avatar_url=request.avatar_url,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="用户资料不存在")
    return updated


@router.get("/me/settings")
def get_my_settings(user: dict = Depends(get_current_user)) -> dict:
    return user_service.get_user_settings(user["user_id"]) or {}


@router.patch("/me/settings")
def update_my_settings(
    request: UpdateSettingsRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    updated = user_service.update_user_settings(
        user["user_id"],
        default_city=request.default_city,
        default_lat=request.default_lat,
        default_lon=request.default_lon,
        assistant_role=request.assistant_role,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="用户设置不存在")
    return updated
