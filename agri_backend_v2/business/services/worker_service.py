"""工人档案 Service（从 archive planting/service.py + labor_service.py 复用）。

提供：
  - create_worker / list_workers / get_worker / update_worker / delete_worker（停用）
  - resolve_worker_by_name（仅解析已有且唯一的工人，供 labor_service 复用）
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
import re
import unicodedata
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from business.context_runtime import invalidate_farm_context
from business.models import Worker

logger = logging.getLogger(__name__)


class WorkerIdentityError(ValueError):
    """工人身份无法唯一确定或违反农场内唯一约束。"""

    def __init__(self, code: str, message: str, **meta: object) -> None:
        super().__init__(message)
        self.code = code
        self.meta = meta


def normalize_worker_name(value: str) -> str:
    """统一姓名的兼容字符和空白，避免展示输入差异造成错误重复。"""
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", "", normalized).strip()


def normalize_worker_phone(value: str | None) -> str | None:
    """规范化电话；空字符串视为未知电话，保留国际区号符号。"""
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", str(value))
    normalized = re.sub(r"[\s()\-]", "", normalized)
    return normalized or None


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
        "created_at": worker.created_at.isoformat() if worker.created_at else None,
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
    """创建工人档案；姓名可重复，电话在农场内必须唯一。"""
    normalized_name = normalize_worker_name(name)
    if not normalized_name:
        raise ValueError("工人姓名不能为空")
    normalized_phone = normalize_worker_phone(phone)
    if normalized_phone is not None:
        existing = _find_worker_by_phone(db, normalized_phone, farm_id)
        if existing is not None:
            raise WorkerIdentityError(
                "duplicate_worker_phone",
                "该电话号码已绑定其他工人",
                existing_id=existing.id,
                field="phone",
            )
    elif _find_workers_by_name(db, normalized_name, farm_id):
        raise WorkerIdentityError(
            "worker_identity_ambiguous",
            "同名工人已存在，请提供电话号码或选择已有工人",
            field="name",
            name=normalized_name,
        )
    worker = Worker(
        farm_id=farm_id,
        name=normalized_name,
        phone=normalized_phone,
        default_pay_type=default_pay_type,
        default_unit_price=default_unit_price,
        note=note,
        status=status,
    )
    db.add(worker)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        if normalized_phone is not None:
            existing = _find_worker_by_phone(db, normalized_phone, farm_id)
            if existing is not None:
                raise WorkerIdentityError(
                    "duplicate_worker_phone",
                    "该电话号码已绑定其他工人",
                    existing_id=existing.id,
                    field="phone",
                ) from exc
        raise
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


def get_worker(db: Session, worker_id: int, farm_id: int) -> dict[str, Any] | None:
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
        normalized_name = normalize_worker_name(name)
        if not normalized_name:
            raise ValueError("工人姓名不能为空")
        worker.name = normalized_name
    if phone is not None:
        normalized_phone = normalize_worker_phone(phone)
        if normalized_phone is not None:
            existing = _find_worker_by_phone(db, normalized_phone, farm_id)
            if existing is not None and existing.id != worker_id:
                raise WorkerIdentityError(
                    "duplicate_worker_phone",
                    "该电话号码已绑定其他工人",
                    existing_id=existing.id,
                    field="phone",
                )
        worker.phone = normalized_phone
    if default_pay_type is not None:
        worker.default_pay_type = default_pay_type
    if default_unit_price is not None:
        worker.default_unit_price = default_unit_price
    if note is not None:
        worker.note = note
    if status is not None:
        worker.status = status
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise WorkerIdentityError(
            "duplicate_worker_phone",
            "该电话号码已绑定其他工人",
            field="phone",
        ) from exc
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


def resolve_worker_by_name(
    db: Session,
    farm_id: int,
    name: str,
) -> Worker:
    """按姓名解析已有工人；缺失或多条时拒绝猜测。"""
    normalized_name = normalize_worker_name(name)
    workers = _find_workers_by_name(db, normalized_name, farm_id)
    if not workers:
        raise WorkerIdentityError(
            "worker_not_found",
            "未找到该工人，请先创建工人档案",
            name=normalized_name,
        )
    if len(workers) > 1:
        raise WorkerIdentityError(
            "worker_identity_ambiguous",
            "同名工人不止一人，请提供 worker_id 或电话号码",
            name=normalized_name,
            candidate_ids=[worker.id for worker in workers],
        )
    return workers[0]


def _get_worker(db: Session, worker_id: int, farm_id: int) -> Worker:
    worker = (
        db.query(Worker)
        .filter(Worker.id == worker_id, Worker.farm_id == farm_id)
        .first()
    )
    if not worker:
        raise ValueError("工人不存在")
    return worker


def _find_workers_by_name(db: Session, name: str, farm_id: int) -> list[Worker]:
    # 旧数据可能保留输入空白；在应用层按规范化姓名比对，避免绕过同名歧义检查。
    workers = (
        db.query(Worker).filter(Worker.farm_id == farm_id).order_by(Worker.id).all()
    )
    return [worker for worker in workers if normalize_worker_name(worker.name) == name]


def _find_worker_by_phone(db: Session, phone: str, farm_id: int) -> Worker | None:
    return (
        db.query(Worker)
        .filter(Worker.farm_id == farm_id, Worker.phone == phone)
        .order_by(Worker.id)
        .first()
    )


__all__ = [
    "create_worker",
    "list_workers",
    "get_worker",
    "update_worker",
    "delete_worker",
    "resolve_worker_by_name",
    "WorkerIdentityError",
    "normalize_worker_name",
    "normalize_worker_phone",
]
