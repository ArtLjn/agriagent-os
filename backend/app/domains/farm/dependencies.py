"""Farm FastAPI 依赖。"""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.domains.farm.models import Farm
from app.domains.users.models import User
from app.domains.users.dependencies import get_current_user


def get_current_farm(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Farm:
    """通过当前用户解析关联农场。"""
    farm = db.query(Farm).filter(Farm.user_id == user.id).first()
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
