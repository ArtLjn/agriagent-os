"""当前用户资料与设置路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field

from business.api.auth import PHONE_PATTERN
from business.api.deps import get_current_admin, get_current_user
from business.api.schemas import StrictRequest
from business.services import auth_service
from business.services import user_service
from shared.roles import UserRole

router = APIRouter(prefix="/users", tags=["users"])
admin_router = APIRouter(prefix="/admin/users", tags=["admin-users"])


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


class AdminCreateUserRequest(StrictRequest):
    """管理端创建账户时复用注册接口的公开字段。"""

    phone: str = Field(pattern=PHONE_PATTERN)
    password: str = Field(min_length=6, max_length=72)
    nickname: str = Field(default="农友", min_length=1, max_length=50)
    role: UserRole = Field(default=UserRole.USER)


@admin_router.get("")
def list_admin_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(
        default=None, alias="status", pattern="^(active|disabled)$"
    ),
    role: UserRole | None = Query(default=None),
    phone_keyword: str | None = Query(default=None, max_length=50),
    _admin: dict = Depends(get_current_admin),
) -> dict:
    """管理员：分页查询用户列表，支持状态、角色和手机号/昵称搜索。"""
    return user_service.list_users(
        page=page,
        size=page_size,
        status=status_filter,
        role=role,
        keyword=phone_keyword,
    )


@admin_router.post("", status_code=status.HTTP_201_CREATED)
def create_admin_user(
    request: AdminCreateUserRequest,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    """管理员：复用注册事务创建普通用户，不向管理端返回新用户令牌。"""
    try:
        user, _token = auth_service.register(
            request.phone,
            request.password,
            request.nickname,
            role=request.role,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    result = user_service.get_admin_user_detail(user.id)
    if result is None:
        raise HTTPException(status_code=500, detail="用户创建后读取资料失败")
    return result


@admin_router.get("/{user_id}")
def get_admin_user(user_id: str, _admin: dict = Depends(get_current_admin)) -> dict:
    """管理员：读取单个用户资料。"""
    result = user_service.get_admin_user_detail(user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return result
