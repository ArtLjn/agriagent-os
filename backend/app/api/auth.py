"""认证 API 路由 — 注册、登录、用户信息。"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.services.auth_service import login as auth_login
from app.services.auth_service import register as auth_register

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """用户注册（手机号 + 密码）。"""
    try:
        user, token = auth_register(db, req.phone, req.password, req.nickname)
    except Exception:
        raise HTTPException(status_code=400, detail="该手机号已注册")
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """用户登录。"""
    result = auth_login(db, req.phone, req.password)
    if result is None:
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    user, token = result
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)) -> UserResponse:
    """获取当前用户信息。"""
    return UserResponse.model_validate(user)


@router.put("/me", response_model=UserResponse)
def update_me(
    req: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """更新当前用户信息。"""
    if req.nickname is not None:
        user.nickname = req.nickname
    if req.avatar_url is not None:
        user.avatar_url = req.avatar_url
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
