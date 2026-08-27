"""REST API 共享认证依赖。

用户 JWT 使用 ``sub=users.id`` 和 ``farm_uid=farms.uid``；内部业务继续使用
``farm_id=farms.id``，但该值只能由已验证的 farm_uid 解析得到。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from business.services import auth_service, farm_crud_service
from business.services.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    decode_access_token,
)
from shared.roles import Permission, has_permission, is_admin_role


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """解析 JWT，并确认用户及其农场仍处于可访问状态。"""
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
    try:
        payload = decode_access_token(token)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "auth_unavailable", "message": str(exc)},
        ) from exc
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "token_expired", "message": "令牌已过期"},
        ) from exc
    except TokenInvalidError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_token", "message": "无效的认证令牌"},
        ) from exc

    user_id = str(payload.get("sub") or "")
    user = auth_service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "user_inactive", "message": "用户不存在"},
        )
    if user.status != "active":
        raise HTTPException(
            status_code=403,
            detail={"code": "user_inactive", "message": "用户已被禁用"},
        )

    from business.db import session_scope

    with session_scope() as db:
        farm = farm_crud_service.get_farm_by_user_id(db, user_id=user_id)
    if farm is None:
        raise HTTPException(
            status_code=403,
            detail={"code": "farm_forbidden", "message": "用户未关联农场"},
        )
    token_farm_uid = payload.get("farm_uid")
    if token_farm_uid:
        if str(token_farm_uid) != str(farm.uid):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "farm_forbidden",
                    "message": "令牌农场与用户归属不一致",
                },
            )
    elif payload.get("farm_id") is not None:
        # 兼容旧 token，但不允许旧 farm_id 覆盖数据库归属。
        if int(payload["farm_id"]) != farm.id:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "farm_forbidden",
                    "message": "旧令牌农场与用户归属不一致",
                },
            )
    else:
        raise HTTPException(
            status_code=403,
            detail={"code": "farm_forbidden", "message": "令牌缺少农场上下文"},
        )
    return {
        "user_id": user_id,
        "farm_uid": farm.uid,
        "farm_id": farm.id,
        "role": user.role,
        "scope": payload.get("scope") or "",
        "token_id": str(payload.get("jti") or ""),
    }


def get_optional_current_user(
    authorization: str | None = Header(default=None),
) -> dict | None:
    """允许公开注册读取可选管理员身份，但不放宽无 Token 请求。"""
    if not authorization or not authorization.strip():
        return None
    return get_current_user(authorization)


def get_current_admin(user: dict = Depends(get_current_user)) -> dict:
    """确认当前主体具备管理员权限，供管理端资源复用。"""
    if not is_admin_role(user.get("role")):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "admin_required",
                "message": "只有管理员可以访问该资源",
            },
        )
    return user


def get_current_principal(user: dict = Depends(get_current_user)) -> dict:
    """以统一 Principal 名称暴露已完成 Business 身份校验的用户。"""
    return user


CurrentPrincipal = Annotated[dict, Depends(get_current_principal)]


def require_permission(permission: Permission):
    """创建 FastAPI 权限依赖，资源归属校验仍由具体 service 负责。"""

    def check(principal: CurrentPrincipal) -> dict:
        if not has_permission(
            principal.get("role"), principal.get("scope"), permission
        ):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "permission_denied",
                    "message": "当前身份没有所需权限",
                    "meta": {"permission": permission.value},
                },
            )
        return principal

    return check
