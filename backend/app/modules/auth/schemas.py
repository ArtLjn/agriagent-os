"""Auth schema 兼容入口。"""

from app.schemas.auth import (
    FarmProfileResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateFarmLocationRequest,
    UpdateProfileRequest,
    UserProfileResponse,
    UserResponse,
)

__all__ = [
    "FarmProfileResponse",
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UpdateFarmLocationRequest",
    "UpdateProfileRequest",
    "UserProfileResponse",
    "UserResponse",
]
