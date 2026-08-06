"""API 鉴权测试辅助函数。"""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.domains.users.dependencies import (
    get_current_user,
    optional_auth_context,
    require_admin_context,
    require_auth_context,
    require_effective_user_context,
)
from app.domains.farm.dependencies import (
    get_auth_context_farm,
    get_current_farm,
    get_effective_auth_context_farm,
)
from app.domains.users.tokens import create_access_token
from app.domains.farm.models import Farm
from app.domains.users.models import User


REGULAR_USER_ID = "auth-regular-001"
ADMIN_USER_ID = "auth-admin-001"


@contextmanager
def auth_override_scope(app: FastAPI) -> Iterator[None]:
    """只移除用户/farm override，保留测试数据库 override。"""
    original_overrides = dict(app.dependency_overrides)
    for dependency in (
        get_current_user,
        require_auth_context,
        require_admin_context,
        require_effective_user_context,
        optional_auth_context,
        get_current_farm,
        get_auth_context_farm,
        get_effective_auth_context_farm,
    ):
        app.dependency_overrides.pop(dependency, None)
    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def ensure_regular_user(db: Session) -> User:
    """确保普通用户和对应农场存在。"""
    user = db.query(User).filter(User.id == REGULAR_USER_ID).first()
    if user is None:
        user = User(
            id=REGULAR_USER_ID,
            phone="18800000001",
            password_hash="h",
            nickname="普通用户",
            role="user",
            status="active",
        )
        db.add(user)
        db.flush()
    _ensure_farm(db, user.id, "普通用户农场")
    db.commit()
    db.refresh(user)
    return user


def ensure_admin_user(db: Session) -> User:
    """确保管理员用户和对应农场存在。"""
    user = db.query(User).filter(User.id == ADMIN_USER_ID).first()
    if user is None:
        user = User(
            id=ADMIN_USER_ID,
            phone="18800000002",
            password_hash="h",
            nickname="管理员",
            role="admin",
            status="active",
        )
        db.add(user)
        db.flush()
    _ensure_farm(db, user.id, "管理员农场")
    db.commit()
    db.refresh(user)
    return user


def regular_headers() -> dict[str, str]:
    """普通用户 Bearer token 请求头。"""
    token = create_access_token(user_id=REGULAR_USER_ID)
    return {"Authorization": f"Bearer {token}"}


def admin_headers() -> dict[str, str]:
    """管理员 Bearer token 请求头。"""
    token = create_access_token(user_id=ADMIN_USER_ID)
    return {"Authorization": f"Bearer {token}"}


def _ensure_farm(db: Session, user_id: str, name: str) -> Farm:
    farm = db.query(Farm).filter(Farm.user_id == user_id).first()
    if farm is None:
        farm = Farm(name=name, user_id=user_id)
        db.add(farm)
        db.flush()
    return farm
