"""Agent 用户身份和 MCP 委托凭证处理。"""

from __future__ import annotations

import time
import uuid
from typing import Any

import jwt
from fastapi import HTTPException

from agent.config import settings
from shared.roles import (
    Permission,
    UserRole,
    has_permission,
    normalize_user_role,
    scope_for_role,
)


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "missing_authorization", "message": "未提供认证令牌"},
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_authorization", "message": "Bearer 令牌为空"},
        )
    return token


def parse_identity(authorization: str | None) -> dict[str, Any]:
    """严格解析 User JWT，不再回退到默认用户或默认农场。"""
    if not settings.auth.jwt_secret:
        raise HTTPException(
            status_code=503,
            detail={"code": "auth_unavailable", "message": "JWT_SECRET 未配置"},
        )
    token = _bearer_token(authorization)
    try:
        payload = jwt.decode(
            token,
            settings.auth.jwt_secret,
            algorithms=[settings.auth.jwt_algorithm],
            issuer=settings.auth.jwt_issuer,
            audience=settings.auth.jwt_audience,
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "token_expired", "message": "令牌已过期"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_token", "message": "无效的认证令牌"},
        ) from exc

    user_id = str(payload.get("sub") or "")
    farm_uid = str(payload.get("farm_uid") or "")
    if payload.get("type") != "access" or not user_id or not farm_uid:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_token",
                "message": "令牌缺少用户或农场身份",
            },
        )
    try:
        role = normalize_user_role(payload.get("role") or UserRole.USER)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_token", "message": "令牌角色无效"},
        ) from exc
    return {
        "user_id": user_id,
        "farm_uid": farm_uid,
        # 迁移期读取旧 claim；新链路的可信农场标识是 farm_uid。
        "farm_id": int(payload.get("farm_id") or 0),
        "role": role.value,
        "scope": payload.get("scope", ""),
        "token_id": str(payload.get("jti") or ""),
        "user_token": token,
        "agent_token": settings.auth.agent_service_token,
    }


def ensure_mcp_credentials() -> None:
    """确认 Agent 能够代表用户访问 Business MCP。"""
    if not settings.auth.agent_service_token:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "service_auth_unavailable",
                "message": "AGENT_SERVICE_TOKEN 未配置",
            },
        )

    if not settings.auth.delegation_secret:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "delegation_auth_unavailable",
                "message": "AGENT_DELEGATION_SECRET 未配置",
            },
        )


def require_identity_permission(
    identity: dict[str, Any], permission: Permission
) -> dict[str, Any]:
    """在 JWT 认证后校验路由权限，拒绝窄 scope Token 越权调用。"""
    if not has_permission(identity.get("role"), identity.get("scope"), permission):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "permission_denied",
                "message": "当前身份没有所需权限",
                "meta": {"permission": permission.value},
            },
        )
    return identity


def create_delegation_token(
    identity: dict[str, Any], *, conversation_id: str, turn_id: str
) -> str:
    """为一次 Agent turn 创建短时用户委托 JWT。"""
    secret = settings.auth.delegation_secret
    if not secret:
        raise RuntimeError("AGENT_DELEGATION_SECRET 未配置")
    now = int(time.time())
    source_scope = str(identity.get("scope") or "farm:read")
    source_scope_items = set(source_scope.split())
    # 旧登录 Token 只有 farm:*；确认它是旧版完整 scope 后补齐新权限，
    # 但不扩大真正的窄 scope，避免委托链路绕过最小权限。
    if source_scope_items in (
        {"farm:read", "farm:write"},
        {"farm:read", "farm:write", "admin:*"},
    ):
        source_scope = scope_for_role(identity.get("role", UserRole.USER.value))
    payload = {
        "iss": settings.auth.delegation_issuer,
        "aud": settings.auth.delegation_audience,
        "sub": identity["user_id"],
        "act": {"sub": "agent", "type": "service"},
        "type": "delegation",
        "farm_uid": identity["farm_uid"],
        "role": identity.get("role", UserRole.USER.value),
        "scope": " ".join(
            filter(
                None,
                [Permission.MCP_INVOKE.value, source_scope],
            )
        ),
        "source_jti": identity.get("token_id", ""),
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "iat": now,
        "nbf": now,
        "exp": now + 300,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, secret, algorithm=settings.auth.jwt_algorithm)
