"""认证路由：注册与登录。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field

from business.api.deps import get_optional_current_user
from business.api.schemas import StrictRequest
from business.db import session_scope
from business.services import farm_crud_service
from business.services.auth_service import login, register
from shared.roles import UserRole, is_admin_role

router = APIRouter(prefix="/auth", tags=["auth"])
PHONE_PATTERN = r"^1[3-9]\d{9}$"


class LoginRequest(StrictRequest):
    phone: str = Field(pattern=r"^\+?\d{11,20}$")
    password: str = Field(min_length=6, max_length=72)


class RegisterRequest(LoginRequest):
    phone: str = Field(pattern=PHONE_PATTERN)
    nickname: str = Field(default="农友", min_length=1, max_length=50)
    role: UserRole = Field(default=UserRole.USER)


def _auth_response(user, token: str) -> dict:
    with session_scope() as db:
        farm = farm_crud_service.get_farm_by_user_id(db, user_id=user.id)
    if farm is None:
        raise HTTPException(status_code=500, detail="用户注册后未创建默认农场")
    return {
        "access_token": token,
        "token_type": "Bearer",
        "user": {
            "id": user.id,
            "phone": user.phone,
            "nickname": user.nickname,
            "role": user.role,
        },
        "user_id": user.id,
        "phone": user.phone,
        "nickname": user.nickname,
        "role": user.role,
        "farm_uid": farm.uid,
        "farm_id": farm.id,
        "token": token,
    }


@router.post("/login")
def login_endpoint(request: LoginRequest) -> dict:
    """使用手机号和密码登录并签发 JWT。"""
    try:
        result = login(request.phone, request.password)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    user, token = result
    return _auth_response(user, token)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_endpoint(
    request: RegisterRequest,
    current_user: dict | None = Depends(get_optional_current_user),
) -> dict:
    """注册用户；admin 可在已认证请求中选择 admin/user/dev。"""
    if request.role is not UserRole.USER and not is_admin_role(
        current_user.get("role") if current_user else None
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "role_assignment_forbidden",
                "message": "只有管理员可以创建 admin 或 dev 用户",
            },
        )
    try:
        user, token = register(
            request.phone,
            request.password,
            request.nickname,
            role=request.role,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _auth_response(user, token)
