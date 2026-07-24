"""Users 域鉴权上下文解析器。"""

from fastapi import Request
from sqlalchemy.orm import Session

from app.domains.users.context import AuthContext
from app.domains.users.errors import (
    admin_required_error,
    expired_token_error,
    invalid_token_error,
    missing_token_error,
    simulated_user_disabled_error,
    simulated_user_not_found_error,
    user_disabled_error,
    user_not_found_error,
)
from app.domains.users.models import User
from app.domains.users.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    decode_access_token,
)

SIMULATE_USER_HEADER = "X-Simulate-User-Id"


def resolve_current_user(
    request: Request,
    db: Session,
    *,
    required: bool = True,
) -> User | None:
    """从请求 token 解析当前用户。"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        if required:
            raise missing_token_error()
        return None
    if not auth_header.startswith("Bearer "):
        raise missing_token_error()

    token = auth_header[7:]
    try:
        payload = decode_access_token(token)
    except TokenExpiredError:
        raise expired_token_error()
    except TokenInvalidError:
        raise invalid_token_error()

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if user is None:
        raise user_not_found_error()
    if user.status != "active":
        raise user_disabled_error()
    return user


def resolve_auth_context(
    request: Request,
    db: Session,
    *,
    required: bool = True,
    allow_simulation: bool = False,
    simulate_user_id_override: str | None = None,
) -> AuthContext | None:
    """解析当前用户，并在允许时解析管理员模拟用户。"""
    current_user = resolve_current_user(request, db, required=required)
    if current_user is None:
        return None

    effective_user = current_user
    simulate_user_id = (
        _resolve_simulate_user_id(request, simulate_user_id_override)
        if allow_simulation
        else None
    )
    if simulate_user_id:
        if current_user.role != "admin":
            raise admin_required_error()
        effective_user = _get_active_simulated_user(db, simulate_user_id)

    return AuthContext(
        current_user=current_user,
        effective_user=effective_user,
    )


def resolve_simulated_auth_context(
    db: Session,
    context: AuthContext,
    simulate_user_id: str | None,
) -> AuthContext:
    """基于已认证上下文解析显式模拟目标用户。"""
    if not simulate_user_id:
        return context
    if not context.is_admin:
        raise admin_required_error()
    return AuthContext(
        current_user=context.current_user,
        effective_user=_get_active_simulated_user(db, simulate_user_id),
    )


def _resolve_simulate_user_id(
    request: Request,
    simulate_user_id_override: str | None = None,
) -> str | None:
    if simulate_user_id_override:
        return simulate_user_id_override
    if "simulate_user_id" in request.query_params:
        return request.query_params.get("simulate_user_id") or None
    header_value = request.headers.get(SIMULATE_USER_HEADER)
    return header_value or None


def _get_active_simulated_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise simulated_user_not_found_error()
    if user.status != "active":
        raise simulated_user_disabled_error()
    return user
