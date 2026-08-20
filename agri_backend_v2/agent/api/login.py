"""POST /api/agri_backend_v2/auth/login：同源代理 Business 用户登录。"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from agent.api import api_router
from agent.config import settings


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(pattern=r"^\+?\d{11,20}$")
    password: str = Field(min_length=6, max_length=72)


def _business_login_url() -> str:
    return f"{settings.business_mcp.api_url.rstrip('/')}/auth/login"


def _is_loopback(url: str) -> bool:
    hostname = urlparse(url).hostname
    return hostname in {"127.0.0.1", "localhost", "::1"}


@api_router.post("/auth/login")
async def login(req: LoginRequest) -> dict:
    """转发登录凭据到内网 Business，并返回用户 Access JWT。"""
    login_url = _business_login_url()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0), trust_env=not _is_loopback(login_url)
        ) as client:
            response = await client.post(login_url, json=req.model_dump())
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "auth_provider_unavailable",
                "message": "登录服务暂时不可用",
            },
        ) from exc

    if response.status_code == 401:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_credentials", "message": "手机号或密码错误"},
        )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=503,
            detail={"code": "auth_provider_error", "message": "登录服务返回错误"},
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "auth_provider_error", "message": "登录服务响应无效"},
        ) from exc

    access_token = data.get("access_token") or data.get("token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(
            status_code=503,
            detail={"code": "auth_provider_error", "message": "登录服务未返回令牌"},
        )
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "user": data.get("user")
        or {
            "id": data.get("user_id"),
            "phone": data.get("phone"),
            "nickname": data.get("nickname"),
            "role": data.get("role"),
        },
        "farm_uid": data.get("farm_uid"),
    }
