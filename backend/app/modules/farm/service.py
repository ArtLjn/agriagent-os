"""Farm 模块服务。"""

from sqlalchemy.orm import Session

from app.models.farm import Farm


def create_default_farm(db: Session, user_id: str, nickname: str) -> Farm:
    """为新用户创建默认农场。"""
    farm = Farm(name=f"{nickname}的农场", user_id=user_id)
    db.add(farm)
    return farm
