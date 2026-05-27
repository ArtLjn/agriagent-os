"""FastAPI 依赖注入 — 数据库会话 + 三层权限过滤器。

Layer 1: get_current_user  — JWT → User, 失败 401
Layer 2: get_current_farm  — User → Farm(user_id=user.id), 失败 404
Layer 3a: verify_resource_owner — 资源归属校验, 失败 403
"""

from typing import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import verify_token
from app.models.farm import Farm
from app.models.user import User


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """Layer 1: 从 JWT 解析 user_id → 查询 User → 校验 status。"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证信息")

    token = auth_header[7:]
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="token 无效或已过期")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.status != "active":
        raise HTTPException(status_code=401, detail="用户已被禁用")
    return user


def get_current_farm(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Farm:
    """Layer 2: User → Farm(user_id=user.id)。"""
    farm = db.query(Farm).filter(Farm.user_id == user.id).first()
    if farm is None:
        raise HTTPException(status_code=404, detail="未找到关联农场")
    return farm


def verify_resource_owner(resource_farm_id: int, current_farm: Farm) -> None:
    """Layer 3a: 校验资源是否属于当前用户的农场。"""
    if resource_farm_id != current_farm.id:
        raise HTTPException(status_code=403, detail="无权访问此资源")
