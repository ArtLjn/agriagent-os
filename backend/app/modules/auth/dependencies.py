"""Auth FastAPI 依赖。"""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.user import User
from app.modules.auth.errors import (
    admin_required_error,
    expired_token_error,
    invalid_token_error,
    missing_token_error,
    user_disabled_error,
    user_not_found_error,
)
from app.modules.auth.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    decode_access_token,
)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """从 JWT 解析当前用户。"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise missing_token_error()

    token = auth_header[7:]
    try:
        payload = decode_access_token(token)
    except TokenExpiredError:
        raise expired_token_error()
    except TokenInvalidError:
        raise invalid_token_error()

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise user_not_found_error()
    if user.status != "active":
        raise user_disabled_error()
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """校验当前用户是否为管理员。"""
    if user.role != "admin":
        raise admin_required_error()
    return user
