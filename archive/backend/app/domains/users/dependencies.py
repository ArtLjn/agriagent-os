"""Auth FastAPI 依赖。"""

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.domains.users.auth_resolver import resolve_auth_context, resolve_current_user
from app.domains.users.context import AuthContext
from app.domains.users.models import User
from app.domains.users.errors import admin_required_error, missing_token_error


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """从 JWT 解析当前用户。"""
    user = resolve_current_user(request, db)
    if user is None:
        raise missing_token_error()
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """校验当前用户是否为管理员。"""
    if user.role != "admin":
        raise admin_required_error()
    return user


def require_auth_context(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthContext:
    """要求有效登录，并返回统一鉴权上下文。"""
    context = resolve_auth_context(request, db)
    if context is None:
        raise missing_token_error()
    return context


def require_admin_context(
    context: AuthContext = Depends(require_auth_context),
) -> AuthContext:
    """要求当前登录用户为管理员。"""
    if not context.is_admin:
        raise admin_required_error()
    return context


def require_effective_user_context(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthContext:
    """要求有效登录，并允许管理员切换生效用户。"""
    context = resolve_auth_context(request, db, allow_simulation=True)
    if context is None:
        raise missing_token_error()
    return context


def optional_auth_context(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthContext | None:
    """没有 token 时返回 None；有 token 时返回统一鉴权上下文。"""
    return resolve_auth_context(request, db, required=False)
