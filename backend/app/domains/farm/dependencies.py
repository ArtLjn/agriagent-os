"""Farm FastAPI 依赖。"""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.domains.farm.models import Farm
from app.domains.users.models import User
from app.domains.users.context import AuthContext
from app.domains.users.dependencies import (
    get_current_user,
    require_auth_context,
    require_effective_user_context,
)


def get_current_farm(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Farm:
    """通过当前用户解析关联农场。"""
    return resolve_farm_for_user_id(db, user.id)


def get_auth_context_farm(
    context: AuthContext = Depends(require_auth_context),
    db: Session = Depends(get_db),
) -> Farm:
    """通过当前登录用户上下文解析关联农场。"""
    return resolve_farm_for_user_id(db, context.effective_user_id)


def get_effective_auth_context_farm(
    context: AuthContext = Depends(require_effective_user_context),
    db: Session = Depends(get_db),
) -> Farm:
    """通过允许模拟的生效用户上下文解析关联农场。"""
    return resolve_farm_for_user_id(db, context.effective_user_id)


def resolve_farm_for_user_id(db: Session, user_id: str) -> Farm:
    """按 Users 域解析出的 user_id 获取 Farm。"""
    farm = db.query(Farm).filter(Farm.user_id == user_id).first()
    if farm is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "FARM_NOT_FOUND", "detail": "未找到关联农场"},
        )
    return farm


def verify_resource_owner(resource_farm_id: int, current_farm: Farm) -> None:
    """校验资源是否属于当前用户的农场。"""
    if resource_farm_id != current_farm.id:
        raise HTTPException(
            status_code=403,
            detail={"code": "FARM_RESOURCE_FORBIDDEN", "detail": "无权访问此资源"},
        )
