from sqlalchemy.orm import Session

from app.models.farm import Farm


def seed_default_farm(db: Session) -> None:
    """向数据库插入默认农场记录（如不存在）。"""
    existing = db.query(Farm).filter(Farm.id == 1).first()
    if existing:
        return
    db.add(Farm(id=1, name="默认农场", owner_name="默认农户"))
    db.commit()
