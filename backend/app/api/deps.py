from typing import Generator

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.farm import Farm


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话，用于 FastAPI 依赖注入。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_farm(db: Session = Depends(get_db)) -> Farm:
    """获取当前默认农场实例。"""
    farm = db.query(Farm).filter(Farm.id == 1).first()
    if not farm:
        raise HTTPException(status_code=404, detail="No default farm found")
    return farm
