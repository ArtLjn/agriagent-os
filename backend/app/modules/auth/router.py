"""认证 API 路由 — 注册、登录、用户信息。"""

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.errors import invalid_credentials_error, register_failed_error
from app.modules.auth.schemas import (
    FarmProfileResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateFarmLocationRequest,
    UpdateProfileRequest,
    UserProfileResponse,
    UserResponse,
)
from app.modules.auth.service import login as auth_login
from app.modules.auth.service import register as auth_register
from app.modules.farm.service import (
    backfill_default_farm_location_from_settings,
    update_default_farm_location,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """用户注册（手机号 + 密码）。"""
    try:
        user, token = auth_register(db, req.phone, req.password, req.nickname)
    except IntegrityError:
        db.rollback()
        raise register_failed_error()
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """用户登录。"""
    result = auth_login(db, req.phone, req.password)
    if result is None:
        raise invalid_credentials_error()
    user, token = result
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


def _build_user_profile(db: Session, user: User) -> UserProfileResponse:
    """构建包含默认农场的当前用户资料。"""
    farm = backfill_default_farm_location_from_settings(db, user_id=user.id)
    if farm and farm.location:
        db.commit()
        db.refresh(farm)
    profile = UserProfileResponse.model_validate(user)
    profile.farm = FarmProfileResponse.model_validate(farm) if farm else None
    return profile


@router.get("/me", response_model=UserProfileResponse)
def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """获取当前用户信息。"""
    return _build_user_profile(db, user)


@router.put("/me", response_model=UserProfileResponse)
def update_me(
    req: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """更新当前用户信息。"""
    if req.nickname is not None:
        user.nickname = req.nickname
    if req.avatar_url is not None:
        user.avatar_url = req.avatar_url
    db.commit()
    db.refresh(user)
    return _build_user_profile(db, user)


@router.put("/me/farm-location", response_model=UserProfileResponse)
def update_me_farm_location(
    req: UpdateFarmLocationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """更新当前用户默认农场经营地区。"""
    update_default_farm_location(
        db,
        user_id=user.id,
        location=req.location,
        farm_id=req.farm_id,
    )
    db.refresh(user)
    return _build_user_profile(db, user)
