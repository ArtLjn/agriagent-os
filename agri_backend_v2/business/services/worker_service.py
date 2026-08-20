"""工人档案 Service（从 archive planting/service.py + labor_service.py 复用）。

提供：
  - create_worker / list_workers / get_worker / update_worker / delete_worker（停用）
  - find_or_create_worker_by_name（从 archive labor_service 迁入，供 labor_service 复用）
  - _get_worker / _find_worker_by_name 内部辅助

改造点（相比 archive）：
  - 导入改为 business.models / business.context_runtime
  - 移除 pydantic schema 依赖，create/update 接受显式关键字参数
  - 返回 dict（不返回 ORM 对象），Decimal → float
  - 保留 db: Session 第一参数；db.commit()/rollback() 改 db.flush()，由外层 session_scope 统一提交
  - invalidate_farm_context 调用保留
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from business.context_runtime import invalidate_farm_context
from business.models import Worker

logger = logging.getLogger(__name__)


def _worker_to_dict(worker: Worker) -> dict[str, Any]:
    """ORM Worker → dict（Decimal 转 float，便于 JSON 序列化）。"""
    return {
        "id": worker.id,
        "farm_id": worker.farm_id,
        "name": worker.name,
        "phone": worker.phone,
        "default_pay_type": worker.default_pay_type,
        "default_unit_price": float(worker.default_unit_price)
        if worker.default_unit_price is not None
        else None,
        "note": worker.note,
        "status": worker.status,
        "created_at": worker.created_at.isoformat()
        if worker.created_at
        else None,
    }


def create_worker(
    db: Session,
    *,
    farm_id: int,
    name: str,
    phone: str | None = None,
    default_pay_type: str = "daily",
    default_unit_price: Decimal | float | None = None,
    note: str | None = None,
    status: str = "active",
) -> dict[str, Any]:
    """创建工人档案；同名工人已存在则直接返回（幂等）。"""
    existing = _find_worker_by_name(db, name, farm_id)
    if existing:
        return _worker_to_dict(existing)
    worker = Worker(
        farm_id=farm_id,
        name=name,
        phone=phone,
        default_pay_type=default_pay_type,
        default_unit_price=default_unit_price,
        note=note,
        status=status,
    )
    db.add(worker)
    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(worker)
    return _worker_to_dict(worker)


def list_workers(
    db: Session, farm_id: int, active_only: bool = False
) -> list[dict[str, Any]]:
    """查询工人档案列表。"""
    query = db.query(Worker).filter(Worker.farm_id == farm_id)
    if active_only:
        query = query.filter(Worker.status == "active")
    workers = query.order_by(Worker.id).all()
    return [_worker_to_dict(w) for w in workers]


def get_worker(
    db: Session, worker_id: int, farm_id: int
) -> dict[str, Any] | None:
    """查询单个工人档案；不存在返回 None。"""
    worker = (
        db.query(Worker)
        .filter(Worker.id == worker_id, Worker.farm_id == farm_id)
        .first()
    )
    return _worker_to_dict(worker) if worker else None


def update_worker(
    db: Session,
    worker_id: int,
    *,
    farm_id: int,
    name: str | None = None,
    phone: str | None = None,
    default_pay_type: str | None = None,
    default_unit_price: Decimal | float | None = None,
    note: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """更新工人档案；只更新传入的字段。"""
    worker = _get_worker(db, worker_id, farm_id)
    if name is not None:
        worker.name = name
    if phone is not None:
        worker.phone = phone
    if default_pay_type is not None:
        worker.default_pay_type = default_pay_type
    if default_unit_price is not None:
        worker.default_unit_price = default_unit_price
    if note is not None:
        worker.note = note
    if status is not None:
        worker.status = status
    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(worker)
    return _worker_to_dict(worker)


def delete_worker(db: Session, worker_id: int, farm_id: int) -> dict[str, Any]:
    """停用工人档案（保留历史用工，不物理删除）。"""
    worker = _get_worker(db, worker_id, farm_id)
    worker.status = "inactive"
    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(worker)
    return _worker_to_dict(worker)


def find_or_create_worker_by_name(
    db: Session,
    farm_id: int,
    name: str,
    default_unit_price: Decimal | float | None = None,
) -> Worker:
    """按农场和姓名复用工人，不存在时创建轻档案。

    返回 ORM Worker（供 labor_service 内部继续操作，避免反复 refresh）。
    """
    worker = _find_worker_by_name(db, name, farm_id)
    if worker:
        return worker
    worker = Worker(
        farm_id=farm_id,
        name=name.strip(),
        default_pay_type="daily",
        default_unit_price=default_unit_price,
        status="active",
    )
    db.add(worker)
    db.flush()
    return worker


def _get_worker(db: Session, worker_id: int, farm_id: int) -> Worker:
    worker = (
        db.query(Worker)
        .filter(Worker.id == worker_id, Worker.farm_id == farm_id)
        .first()
    )
    if not worker:
        raise ValueError("工人不存在")
    return worker


def _find_worker_by_name(
    db: Session, name: str, farm_id: int
) -> Worker | None:
    normalized = name.strip()
    return (
        db.query(Worker)
        .filter(Worker.farm_id == farm_id, Worker.name == normalized)
        .order_by(Worker.id)
        .first()
    )


__all__ = [
    "create_worker",
    "list_workers",
    "get_worker",
    "update_worker",
    "delete_worker",
    "find_or_create_worker_by_name",
]
