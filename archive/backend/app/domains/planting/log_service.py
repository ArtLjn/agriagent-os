from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.context.runtime import invalidate_farm_context
from app.domains.planting.cycle_models import CropCycle
from app.domains.planting.log_models import FarmLog, FarmLogWorker
from app.domains.planting.log_schemas import FarmLogCreate
from app.domains.planting.models import OperationWorkOrder, Worker


def create_log(db: Session, log: FarmLogCreate, farm_id: int) -> FarmLog:
    """创建一条农事日志记录。"""
    cycle = db.query(CropCycle).filter(CropCycle.id == log.cycle_id).first()
    if not cycle:
        raise ValueError("Crop cycle not found")
    _validate_log_links(db, log, farm_id)

    db_log = FarmLog(
        farm_id=farm_id,
        cycle_id=log.cycle_id,
        work_order_id=log.work_order_id,
        operation_type=log.operation_type,
        operation_date=log.operation_date,
        operation_time=log.operation_time,
        note=log.note,
        photo_urls=log.photo_urls,
    )
    db.add(db_log)
    db.flush()
    _replace_log_workers(db, db_log, _resolve_worker_ids(db, log, farm_id))
    try:
        db.commit()
        invalidate_farm_context(farm_id)
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
    _validate_log_links(db, update, farm_id)

    db_log.cycle_id = update.cycle_id
    db_log.work_order_id = update.work_order_id
    db_log.operation_type = update.operation_type
    db_log.operation_date = update.operation_date
    db_log.operation_time = update.operation_time
    db_log.note = update.note
    db_log.photo_urls = update.photo_urls
    _replace_log_workers(db, db_log, _resolve_worker_ids(db, update, farm_id))

    try:
        db.commit()
        invalidate_farm_context(farm_id)
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
        invalidate_farm_context(farm_id)
    except Exception:
        db.rollback()
        raise


def _validate_log_links(db: Session, log: FarmLogCreate, farm_id: int) -> None:
    if log.work_order_id is None:
        return
    work_order = (
        db.query(OperationWorkOrder)
        .filter(
            OperationWorkOrder.id == log.work_order_id,
            OperationWorkOrder.farm_id == farm_id,
        )
        .first()
    )
    if not work_order:
        raise ValueError("关联作业单不存在")
    if work_order.cycle_id is not None and work_order.cycle_id != log.cycle_id:
        raise ValueError("农事日志茬口与关联作业单不一致")


def _resolve_worker_ids(db: Session, log: FarmLogCreate, farm_id: int) -> list[int]:
    worker_ids = list(dict.fromkeys(log.worker_ids or []))
    if log.worker_names:
        worker_names = [name.strip() for name in log.worker_names if name.strip()]
        workers = (
            db.query(Worker)
            .filter(
                Worker.farm_id == farm_id,
                Worker.name.in_(worker_names),
            )
            .all()
        )
        if len(workers) != len(set(worker_names)):
            raise ValueError("存在不可访问的参与工人")
        worker_ids.extend(worker.id for worker in workers)
    worker_ids = list(dict.fromkeys(worker_ids))
    if not worker_ids:
        return []
    workers = (
        db.query(Worker)
        .filter(Worker.farm_id == farm_id, Worker.id.in_(worker_ids))
        .all()
    )
    if len(workers) != len(worker_ids):
        raise ValueError("存在不可访问的参与工人")
    return worker_ids


def _replace_log_workers(db: Session, log: FarmLog, worker_ids: list[int]) -> None:
    for link in list(log.worker_links):
        db.delete(link)
    db.flush()
    for worker_id in worker_ids:
        db.add(FarmLogWorker(farm_log_id=log.id, worker_id=worker_id))


__all__ = [
    "create_log",
    "get_logs",
    "count_logs",
    "get_logs_by_date",
    "update_log",
    "delete_log",
]
