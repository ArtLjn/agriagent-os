from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.models.cycle import CropCycle
from app.models.log import FarmLog
from app.schemas.log import FarmLogCreate


def create_log(db: Session, log: FarmLogCreate) -> FarmLog:
    """创建一条农事日志记录。"""
    cycle = db.query(CropCycle).filter(CropCycle.id == log.cycle_id).first()
    if not cycle:
        raise ValueError("Crop cycle not found")

    db_log = FarmLog(
        cycle_id=log.cycle_id,
        operation_type=log.operation_type,
        operation_date=log.operation_date,
        operation_time=log.operation_time,
        note=log.note,
        photo_urls=log.photo_urls,
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


def get_logs(
    db: Session, cycle_id: int | None = None, operation_type: str | None = None
) -> list[FarmLog]:
    """获取农事日志列表，支持按周期 ID 和操作类型筛选。"""
    query = db.query(FarmLog)
    if cycle_id is not None:
        query = query.filter(FarmLog.cycle_id == cycle_id)
    if operation_type is not None:
        query = query.filter(FarmLog.operation_type == operation_type)
    return query.order_by(FarmLog.operation_date.desc()).all()


def get_logs_by_date(db: Session, year: int, month: int) -> list[FarmLog]:
    """按年月获取农事日志。"""
    return (
        db.query(FarmLog)
        .filter(extract("year", FarmLog.operation_date) == year)
        .filter(extract("month", FarmLog.operation_date) == month)
        .order_by(FarmLog.operation_date.desc())
        .all()
    )


__all__ = ["create_log", "get_logs", "get_logs_by_date"]
