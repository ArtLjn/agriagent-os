from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.models.cycle import CropCycle
from app.models.log import FarmLog
from app.schemas.log import FarmLogCreate


def create_log(db: Session, log: FarmLogCreate, farm_id: int) -> FarmLog:
    """创建一条农事日志记录。"""
    cycle = db.query(CropCycle).filter(CropCycle.id == log.cycle_id).first()
    if not cycle:
        raise ValueError("Crop cycle not found")

    db_log = FarmLog(
        farm_id=farm_id,
        cycle_id=log.cycle_id,
        operation_type=log.operation_type,
        operation_date=log.operation_date,
        operation_time=log.operation_time,
        note=log.note,
        photo_urls=log.photo_urls,
    )
    db.add(db_log)
    try:
        db.commit()
        db.refresh(db_log)
    except Exception:
        db.rollback()
        raise
    return db_log


def get_logs(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    operation_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[FarmLog]:
    """获取农事日志列表，支持按周期 ID 和操作类型筛选（分页）。"""
    query = db.query(FarmLog).filter(FarmLog.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(FarmLog.cycle_id == cycle_id)
    if operation_type is not None:
        query = query.filter(FarmLog.operation_type == operation_type)
    return query.order_by(FarmLog.operation_date.desc()).offset(skip).limit(limit).all()


def count_logs(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    operation_type: str | None = None,
) -> int:
    """获取农事日志总数，支持按周期 ID 和操作类型筛选。"""
    query = db.query(FarmLog).filter(FarmLog.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(FarmLog.cycle_id == cycle_id)
    if operation_type is not None:
        query = query.filter(FarmLog.operation_type == operation_type)
    return query.count()


def get_logs_by_date(db: Session, year: int, month: int) -> list[FarmLog]:
    """按年月获取农事日志。"""
    return (
        db.query(FarmLog)
        .filter(extract("year", FarmLog.operation_date) == year)
        .filter(extract("month", FarmLog.operation_date) == month)
        .order_by(FarmLog.operation_date.desc())
        .all()
    )


def update_log(
    db: Session, log_id: int, update: FarmLogCreate, farm_id: int
) -> FarmLog:
    """更新农事日志。"""
    db_log = (
        db.query(FarmLog)
        .filter(FarmLog.id == log_id, FarmLog.farm_id == farm_id)
        .first()
    )
    if not db_log:
        raise ValueError(f"日志 {log_id} 不存在")

    cycle = db.query(CropCycle).filter(CropCycle.id == update.cycle_id).first()
    if not cycle:
        raise ValueError("Crop cycle not found")

    db_log.cycle_id = update.cycle_id
    db_log.operation_type = update.operation_type
    db_log.operation_date = update.operation_date
    db_log.operation_time = update.operation_time
    db_log.note = update.note
    db_log.photo_urls = update.photo_urls

    try:
        db.commit()
        db.refresh(db_log)
    except Exception:
        db.rollback()
        raise
    return db_log


def delete_log(db: Session, log_id: int, farm_id: int) -> None:
    """删除农事日志。"""
    db_log = (
        db.query(FarmLog)
        .filter(FarmLog.id == log_id, FarmLog.farm_id == farm_id)
        .first()
    )
    if not db_log:
        raise ValueError(f"日志 {log_id} 不存在")

    db.delete(db_log)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


__all__ = [
    "create_log",
    "get_logs",
    "count_logs",
    "get_logs_by_date",
    "update_log",
    "delete_log",
]
