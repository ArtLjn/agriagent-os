"""认证路由：注册与登录。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import Field

from business.api.schemas import StrictRequest
from business.db import session_scope
from business.services import farm_crud_service
from business.services.auth_service import login, register

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(StrictRequest):
    phone: str = Field(pattern=r"^\+?\d{11,20}$")
    password: str = Field(min_length=6, max_length=72)


class RegisterRequest(LoginRequest):
    nickname: str = Field(default="农友", min_length=1, max_length=50)


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
def register_endpoint(request: RegisterRequest) -> dict:
    """注册用户并创建默认农场。"""
    try:
        user, token = register(request.phone, request.password, request.nickname)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _auth_response(user, token)
