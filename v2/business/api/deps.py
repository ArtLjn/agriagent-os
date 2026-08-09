"""REST API 共享依赖。

JWT 解析 → get_current_user：从 Bearer token 提取 user_id 和 farm_id。
"""

from __future__ import annotations

from fastapi import Header, HTTPException

from business.services import auth_service, farm_crud_service
from business.services.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    decode_access_token,
)


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """解析 JWT，并确认用户及其农场仍处于可访问状态。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    token = authorization[7:]
    try:
        payload = decode_access_token(token)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TokenExpiredError as exc:
        raise HTTPException(status_code=401, detail="令牌已过期") from exc
    except TokenInvalidError as exc:
        raise HTTPException(status_code=401, detail="无效的认证令牌") from exc

    user_id = str(payload.get("sub") or "")
    user = auth_service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="用户已被禁用")

    from business.db import session_scope

    with session_scope() as db:
        farm = farm_crud_service.get_farm_by_user_id(db, user_id=user_id)
    if farm is None:
        raise HTTPException(status_code=403, detail="用户未关联农场")
    token_farm_id = payload.get("farm_id")
    if token_farm_id is not None and int(token_farm_id) != farm.id:
        raise HTTPException(status_code=403, detail="令牌农场与用户归属不一致")
    return {"user_id": user_id, "farm_id": farm.id, "role": user.role}
