"""Farm log service — SQL 实现。

CRUD on farm_logs + farm_log_workers，沿用 archive 表结构。
对 agent 暴露的接口跟旧 JSON 版完全一致，只是后端从文件改 MySQL。

改造点（相比 agri_backend_v2 早期版本）：
  - 接受 farm_id 参数，移除 DEFAULT_FARM_ID 全局变量依赖
  - 补充 update_log、count_logs（复用 archive log_service.py 的逻辑）
  - _resolve_worker_ids 只解析已有工人；姓名多候选或不存在时返回结构化业务错误
  - 接受 operation_type 过滤参数
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from business.db import DEFAULT_FARM_ID, session_scope
from business.models import CropCycle, FarmLog, FarmLogWorker, Worker
from business.services.worker_service import (
    WorkerIdentityError,
    normalize_worker_name,
)


def _parse_date(value: str | None) -> date:
    """解析日期字符串，失败回退到今天。"""
    if not value:
        return date.today()
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return date.today()


def _resolve_worker_ids(
    db,
    farm_id: int,
    worker_ids: list[int] | None = None,
    worker_names: list[str] | None = None,
) -> list[int]:
    """解析已存在的工人引用，拒绝缺失或多候选姓名。

    姓名只保留兼容查询入口；日志落库前始终转换为明确的 worker_id，
    不再因一次日志输入自动创建工人档案。
    """
    if worker_ids is not None:
        unique_ids = list(dict.fromkeys(int(worker_id) for worker_id in worker_ids))
        workers = (
            db.query(Worker)
            .filter(Worker.farm_id == farm_id, Worker.id.in_(unique_ids))
            .all()
        )
        workers_by_id = {worker.id: worker for worker in workers}
        missing_ids = [
            worker_id for worker_id in unique_ids if worker_id not in workers_by_id
        ]
        if missing_ids:
            raise WorkerIdentityError(
                "worker_not_found",
                "存在不属于当前农场的工人",
                candidate_ids=missing_ids,
            )
        return unique_ids

    if not worker_names:
        return []
    normalized_names = [normalize_worker_name(name) for name in worker_names]
    existing = db.scalars(
        select(Worker).where(
            Worker.farm_id == farm_id,
            Worker.name.in_(normalized_names),
        )
    ).all()
    by_name: dict[str, list[Worker]] = {}
    for worker in existing:
        by_name.setdefault(normalize_worker_name(worker.name), []).append(worker)

    resolved_ids: list[int] = []
    for name in normalized_names:
        candidates = by_name.get(name, [])
        if not candidates:
            raise WorkerIdentityError(
                "worker_not_found",
                "未找到该工人，请先创建工人档案",
                name=name,
            )
        if len(candidates) > 1:
            raise WorkerIdentityError(
                "worker_identity_ambiguous",
                "同名工人不止一人，请提供 worker_id 或电话号码",
                name=name,
                candidate_ids=[worker.id for worker in candidates],
            )
        if candidates[0].id not in resolved_ids:
            resolved_ids.append(candidates[0].id)
    return resolved_ids


def query_logs(
    *,
    farm_id: int | None = None,
    cycle_id: int | None = None,
    operation_type: str | None = None,
    days: int = 7,
    start_date: date | None = None,
    end_date: date | None = None,
    offset: int = 0,
    limit: int = 20,
) -> dict:
    """Return recent logs, optionally filtered by cycle and within N days.

    Args:
        farm_id: 农场 ID（必填，隔离维度）。None 时回退到 DEFAULT_FARM_ID（向后兼容）
        cycle_id: 按茬口 ID 过滤（可选）
        operation_type: 按作业类型过滤（可选）
        days: 回溯天数（默认 7）
        limit: 返回最大条数（默认 20）
    """
    if farm_id is None:
        farm_id = DEFAULT_FARM_ID
    cutoff = start_date or (date.today() - timedelta(days=max(1, days)))
    with session_scope() as db:
        stmt = (
            select(FarmLog)
            .options(
                selectinload(FarmLog.worker_links).selectinload(FarmLogWorker.worker)
            )
            .where(
                FarmLog.farm_id == farm_id,
                FarmLog.operation_date >= cutoff,
            )
            .order_by(FarmLog.operation_date.desc(), FarmLog.id.desc())
            .offset(max(0, offset))
            .limit(max(1, min(limit, 100)))
        )
        if end_date is not None:
            stmt = stmt.where(FarmLog.operation_date <= end_date)
        if cycle_id is not None:
            stmt = stmt.where(FarmLog.cycle_id == int(cycle_id))
        if operation_type:
            stmt = stmt.where(FarmLog.operation_type == operation_type)
        logs = db.scalars(stmt).unique().all()
        return {
            "count": len(logs),
            "logs": [_log_to_dict(log) for log in logs],
            "filter": {
                "farm_id": farm_id,
                "cycle_id": cycle_id,
                "operation_type": operation_type,
                "days": days,
                "limit": limit,
            },
        }


def count_logs(
    *,
    farm_id: int | None = None,
    cycle_id: int | None = None,
    operation_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> int:
    """获取农事日志总数，支持按 cycle_id 和 operation_type 筛选。"""
    if farm_id is None:
        farm_id = DEFAULT_FARM_ID
    with session_scope() as db:
        query = db.query(FarmLog).filter(FarmLog.farm_id == farm_id)
        if cycle_id is not None:
            query = query.filter(FarmLog.cycle_id == cycle_id)
        if operation_type:
            query = query.filter(FarmLog.operation_type == operation_type)
        if start_date is not None:
            query = query.filter(FarmLog.operation_date >= start_date)
        if end_date is not None:
            query = query.filter(FarmLog.operation_date <= end_date)
        return query.count()


def get_log(db: Session, *, farm_id: int, log_id: int) -> dict | None:
    """按农场与日志 ID 查询单条农事日志。"""
    log = (
        db.query(FarmLog)
        .filter(FarmLog.id == log_id, FarmLog.farm_id == farm_id)
        .first()
    )
    return _log_to_dict(log) if log else None


def create_log(
    *,
    farm_id: int | None = None,
    cycle_id: int,
    operation_type: str,
    operation_date: str | None = None,
    operation_time: datetime | None = None,
    note: str | None = None,
    worker_names: list[str] | None = None,
    worker_ids: list[int] | None = None,
) -> dict:
    """Append a new farm log entry. Returns the created log dict.

    Args:
        farm_id: 农场 ID（None 时回退到 DEFAULT_FARM_ID）
        cycle_id: 茬口 ID（必填）
        operation_type: 作业类型（必填，如"浇水"、"施肥"）
        operation_date: YYYY-MM-DD（不传默认今天）
        operation_time: 用户选择的实际作业时刻，未提供时使用当前时间
        note: 备注
        worker_names: 兼容的参与工人姓名列表，必须能唯一匹配已有档案
        worker_ids: 已确认的参与工人 ID 列表
    """
    if farm_id is None:
        farm_id = DEFAULT_FARM_ID
    if not operation_type:
        raise ValueError("operation_type is required")
    if not cycle_id:
        raise ValueError("cycle_id is required")

    op_date = _parse_date(operation_date)
    with session_scope() as db:
        # 校验 cycle 属于当前 farm
        cycle = db.get(CropCycle, int(cycle_id))
        if cycle is None or cycle.farm_id != farm_id:
            raise ValueError(f"cycle_id={cycle_id} 不属于当前农场")

        log = FarmLog(
            farm_id=farm_id,
            cycle_id=int(cycle_id),
            operation_type=operation_type,
            operation_date=op_date,
            operation_time=operation_time or datetime.now(),
            note=note or "",
        )
        db.add(log)
        db.flush()  # 拿到 log.id

        resolved_worker_ids = _resolve_worker_ids(
            db, farm_id, worker_ids=worker_ids, worker_names=worker_names
        )
        for wid in resolved_worker_ids:
            db.add(FarmLogWorker(farm_log_id=log.id, worker_id=wid))

        db.flush()
        # 重新加载 worker 关联
        db.refresh(log, attribute_names=["worker_links"])
        for link in log.worker_links:
            db.refresh(link, attribute_names=["worker"])
        return _log_to_dict(log)


def update_log(
    *,
    farm_id: int | None = None,
    log_id: int,
    cycle_id: int | None = None,
    operation_type: str | None = None,
    operation_date: str | None = None,
    operation_time: datetime | None = None,
    note: str | None = None,
    worker_names: list[str] | None = None,
    worker_ids: list[int] | None = None,
) -> dict:
    """更新农事日志。可部分更新字段。

    Args:
        farm_id: 农场 ID（None 时回退到 DEFAULT_FARM_ID）
        log_id: 日志 ID（必填）
        cycle_id: 新茬口 ID（可选，需属于当前农场）
        operation_type: 新作业类型（可选）
        operation_date: 新日期（可选）
        note: 新备注（可选）
        worker_names: 兼容的工人姓名列表（可选，传入则全量替换）
        worker_ids: 已确认的工人 ID 列表（可选，传入则全量替换）
    """
    if farm_id is None:
        farm_id = DEFAULT_FARM_ID
    with session_scope() as db:
        log = (
            db.query(FarmLog)
            .filter(FarmLog.id == log_id, FarmLog.farm_id == farm_id)
            .first()
        )
        if log is None:
            raise ValueError(f"日志 {log_id} 不存在")

        if cycle_id is not None:
            cycle = db.get(CropCycle, int(cycle_id))
            if cycle is None or cycle.farm_id != farm_id:
                raise ValueError(f"cycle_id={cycle_id} 不属于当前农场")
            log.cycle_id = int(cycle_id)
        if operation_type is not None:
            log.operation_type = operation_type
        if operation_date is not None:
            log.operation_date = _parse_date(operation_date)
        if operation_time is not None:
            log.operation_time = operation_time
        if note is not None:
            log.note = note

        if worker_names is not None or worker_ids is not None:
            # 全量替换 worker_links
            for link in list(log.worker_links):
                db.delete(link)
            db.flush()
            resolved_worker_ids = _resolve_worker_ids(
                db, farm_id, worker_ids=worker_ids, worker_names=worker_names
            )
            for wid in resolved_worker_ids:
                db.add(FarmLogWorker(farm_log_id=log.id, worker_id=wid))

        db.flush()
        db.refresh(log, attribute_names=["worker_links"])
        for link in log.worker_links:
            db.refresh(link, attribute_names=["worker"])
        return _log_to_dict(log)


def delete_log(*, farm_id: int | None = None, log_id: int) -> dict:
    """Remove a log entry by id (cascade deletes farm_log_workers).

    Args:
        farm_id: 农场 ID（None 时回退到 DEFAULT_FARM_ID）
        log_id: 日志 ID（必填）
    """
    if farm_id is None:
        farm_id = DEFAULT_FARM_ID
    with session_scope() as db:
        log = (
            db.query(FarmLog)
            .filter(FarmLog.id == int(log_id), FarmLog.farm_id == farm_id)
            .first()
        )
        if log is None:
            raise ValueError(f"log_id={log_id} 不存在或不属于当前农场")
        db.delete(log)
        return {"deleted": int(log_id)}


def _log_to_dict(log: FarmLog) -> dict[str, Any]:
    """ORM FarmLog → dict（含 worker_names）。"""
    return {
        "id": log.id,
        "farm_id": log.farm_id,
        "cycle_id": log.cycle_id,
        "operation_type": log.operation_type,
        "operation_date": log.operation_date.isoformat()
        if log.operation_date
        else None,
        "operation_time": log.operation_time.isoformat()
        if log.operation_time
        else None,
        "note": log.note or "",
        "worker_names": log.worker_names,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


__all__ = [
    "query_logs",
    "count_logs",
    "create_log",
    "update_log",
    "delete_log",
]
