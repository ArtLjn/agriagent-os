"""Farm log service — SQL 实现。

CRUD on farm_logs + farm_log_workers，沿用 archive 表结构。
对 agent 暴露的接口跟旧 JSON 版完全一致，只是后端从文件改 MySQL。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from business.db import DEFAULT_FARM_ID, session_scope
from business.models import FarmLog, FarmLogWorker, Worker

logger = logging.getLogger(__name__)


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return date.today()


def _resolve_worker_ids(db, worker_names: list[str]) -> list[int]:
    """worker_names → worker_ids（farm_id 范围内）。

    - 名字匹配的 worker 直接用；不存在则自动建档（status=active）。
      archive 习惯是允许 agent 直接传工人名字而无需先建 worker 档案。
    """
    if not worker_names:
        return []
    existing = db.scalars(
        select(Worker).where(
            Worker.farm_id == DEFAULT_FARM_ID,
            Worker.name.in_(worker_names),
        )
    ).all()
    by_name = {w.name: w for w in existing}
    ids = [w.id for w in existing]
    # 自动建档缺失的工人
    for name in worker_names:
        if name in by_name:
            continue
        w = Worker(
            farm_id=DEFAULT_FARM_ID,
            name=name,
            default_pay_type="daily",
            status="active",
        )
        db.add(w)
        db.flush()
        ids.append(w.id)
        logger.info("auto-created worker: %s (id=%s)", name, w.id)
    return ids


def query_logs(
    *,
    cycle_id: int | None = None,
    days: int = 7,
    limit: int = 20,
) -> dict:
    """Return recent logs, optionally filtered by cycle and within N days."""
    cutoff = date.today() - timedelta(days=max(1, days))
    with session_scope() as db:
        stmt = (
            select(FarmLog)
            .options(selectinload(FarmLog.worker_links).selectinload(FarmLogWorker.worker))
            .where(
                FarmLog.farm_id == DEFAULT_FARM_ID,
                FarmLog.operation_date >= cutoff,
            )
            .order_by(FarmLog.operation_date.desc(), FarmLog.id.desc())
            .limit(max(1, min(limit, 100)))
        )
        if cycle_id is not None:
            stmt = stmt.where(FarmLog.cycle_id == int(cycle_id))
        logs = db.scalars(stmt).unique().all()
        return {
            "count": len(logs),
            "logs": [_log_to_dict(l) for l in logs],
            "filter": {"cycle_id": cycle_id, "days": days, "limit": limit},
        }


def create_log(
    *,
    cycle_id: int,
    operation_type: str,
    operation_date: str | None = None,
    note: str | None = None,
    worker_names: list[str] | None = None,
) -> dict:
    """Append a new farm log entry. Returns the created log dict."""
    if not operation_type:
        raise ValueError("operation_type is required")
    if not cycle_id:
        raise ValueError("cycle_id is required")

    op_date = _parse_date(operation_date)
    with session_scope() as db:
        log = FarmLog(
            farm_id=DEFAULT_FARM_ID,
            cycle_id=int(cycle_id),
            operation_type=operation_type,
            operation_date=op_date,
            operation_time=datetime.now(),
            note=note or "",
        )
        db.add(log)
        db.flush()  # 拿到 log.id

        worker_ids = _resolve_worker_ids(db, worker_names or [])
        for wid in worker_ids:
            db.add(FarmLogWorker(farm_log_id=log.id, worker_id=wid))

        db.flush()
        # 重新加载 worker 关联
        db.refresh(log, attribute_names=["worker_links"])
        for link in log.worker_links:
            db.refresh(link, attribute_names=["worker"])
        return _log_to_dict(log)


def delete_log(*, log_id: int) -> dict:
    """Remove a log entry by id (cascade deletes farm_log_workers)."""
    with session_scope() as db:
        log = db.get(FarmLog, int(log_id))
        if log is None:
            raise ValueError(f"log_id={log_id} not found")
        db.delete(log)
        return {"deleted": int(log_id)}


def _log_to_dict(log: FarmLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "cycle_id": log.cycle_id,
        "operation_type": log.operation_type,
        "operation_date": log.operation_date.isoformat() if log.operation_date else None,
        "operation_time": log.operation_time.isoformat() if log.operation_time else None,
        "note": log.note or "",
        "worker_names": log.worker_names,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }
