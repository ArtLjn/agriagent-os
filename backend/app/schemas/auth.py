"""认证相关 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator
import re


class RegisterRequest(BaseModel):
    """用户注册请求。"""

    phone: str = Field(..., min_length=11, max_length=11)
    password: str = Field(..., min_length=8, max_length=64)
    nickname: str = Field(default="农友", max_length=50)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v


class LoginRequest(BaseModel):
    """用户登录请求。"""

    phone: str = Field(..., min_length=11, max_length=11)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """用户信息响应。"""

    id: str
    phone: str
    nickname: str
    avatar_url: str | None = None
    role: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """登录成功响应（含 token）。"""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UpdateProfileRequest(BaseModel):
    """更新用户信息请求。"""

    nickname: str | None = Field(None, max_length=50)
    avatar_url: str | None = Field(None, max_length=500)
