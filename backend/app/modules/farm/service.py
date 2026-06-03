"""Farm 模块服务。"""

from sqlalchemy.orm import Session

from app.models.farm import Farm


def create_default_farm(db: Session, user_id: str, nickname: str) -> Farm:
    """为新用户创建默认农场。"""
    farm = Farm(name=f"{nickname}的农场", user_id=user_id)
    db.add(farm)
    return farm


def get_farm_by_user_id(db: Session, user_id: str) -> Farm | None:
    """通过用户 ID 获取关联农场。"""
    return db.query(Farm).filter(Farm.user_id == user_id).first()
