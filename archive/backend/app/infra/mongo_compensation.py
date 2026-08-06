"""Mongo 双写失败补偿任务存储与重放服务。"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.shared.mongo_compensation_models import MongoCompensationTask

logger = logging.getLogger(__name__)

PENDING_STATUSES = ("pending",)
TERMINAL_STATUS = "completed"
DEFAULT_OPERATION = "create"
ERROR_MAX_LENGTH = 1000


class MongoCompensationRecorder:
    """将双写失败 payload 记录为 MySQL 补偿任务。"""

    def __init__(self, db: Session) -> None:
        self._db = db

    def record_failure(self, payload: dict[str, Any]) -> MongoCompensationTask:
        task = MongoCompensationTask(
            object_type=str(payload["object_type"]),
            farm_id=int(payload["farm_id"]),
            business_id=_optional_str(payload.get("business_id")),
            mysql_id=payload.get("mysql_id"),
            operation=str(payload.get("operation") or DEFAULT_OPERATION),
            status="pending",
            attempts=0,
            last_error=redact_error(payload.get("error")),
            next_retry_at=datetime.now(),
        )
        self._db.add(task)
        self._db.commit()
        self._db.refresh(task)
        return task

    def list_pending(self, *, limit: int = 100) -> list[MongoCompensationTask]:
        now = datetime.now()
        return (
            self._db.query(MongoCompensationTask)
            .filter(
                MongoCompensationTask.status.in_(PENDING_STATUSES),
                (
                    (MongoCompensationTask.next_retry_at.is_(None))
                    | (MongoCompensationTask.next_retry_at <= now)
                ),
            )
            .order_by(
                MongoCompensationTask.next_retry_at.asc(),
                MongoCompensationTask.id.asc(),
            )
            .limit(max(limit, 0))
            .all()
        )


class MongoCompensationReplayService:
    """从 MySQL source of truth 重新加载对象并幂等写入 Mongo。"""

    def __init__(
        self,
        db: Session,
        *,
        mysql_repositories: dict[str, Any],
        mongo_repositories: dict[str, Any],
        max_attempts: int = 3,
        retry_delay_seconds: int = 60,
    ) -> None:
        self._db = db
        self._mysql_repositories = mysql_repositories
        self._mongo_repositories = mongo_repositories
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds

    async def replay_once(self, task_id: int) -> bool:
        task = self._db.get(MongoCompensationTask, task_id)
        if task is None or task.status == TERMINAL_STATUS:
            return False

        task.status = "running"
        task.updated_at = datetime.now()
        self._db.commit()

        try:
            row = self._load_mysql_row(task)
            if row is None:
                raise LookupError("not_found")
            await self._write_mongo(task, row)
        except Exception as exc:
            self._mark_failed(task, exc)
            return False

        self._mark_completed(task)
        return True

    async def replay_pending(self, *, limit: int = 100) -> int:
        recorder = MongoCompensationRecorder(self._db)
        count = 0
        for task in recorder.list_pending(limit=limit):
            if await self.replay_once(task.id):
                count += 1
        return count

    def _load_mysql_row(self, task: MongoCompensationTask) -> Any | None:
        repo = self._mysql_repositories[task.object_type]
        if task.object_type == "trace":
            rows = repo.get_by_request_id(
                farm_id=task.farm_id,
                request_id=str(task.business_id),
            )
            return _match_mysql_id(rows, task.mysql_id)
        if task.object_type == "prelabel":
            return repo.get_by_id_and_sample(
                farm_id=task.farm_id,
                prelabel_id=task.mysql_id,
                sample_id=str(task.business_id),
            )
        if task.object_type == "case_draft":
            return repo.get_by_draft_id(
                farm_id=task.farm_id,
                draft_id=str(task.business_id),
            )
        if task.object_type == "repair_pack":
            return repo.get_by_pack_id(
                farm_id=task.farm_id,
                pack_id=str(task.business_id),
            )
        if task.object_type == "review_issue_chain":
            return repo.get_by_chain_id(
                farm_id=task.farm_id,
                chain_id=str(task.business_id),
            )
        if task.object_type == "conversation_message":
            if task.mysql_id is None:
                return None
            return repo.get_by_mysql_id(farm_id=task.farm_id, mysql_id=task.mysql_id)
        if task.object_type == "agent_record":
            rows = repo.list_advice_history(farm_id=task.farm_id, limit=1000)
            row = _match_mysql_id(rows, task.mysql_id)
            if row is not None:
                return row
            rows = repo.list_report_history(farm_id=task.farm_id, limit=1000)
            return _match_mysql_id(rows, task.mysql_id)
        if task.object_type == "guardrails_log":
            page = repo.list_admin_page(trigger_type=None, page=1, size=1000)
            return _match_mysql_id(page.items, task.mysql_id)
        raise ValueError(f"unsupported_object_type:{task.object_type}")

    async def _write_mongo(self, task: MongoCompensationTask, row: Any) -> None:
        repo = self._mongo_repositories[task.object_type]
        operation = task.operation or DEFAULT_OPERATION
        method_name = "save" if task.object_type == "review_issue_chain" else operation
        if task.object_type == "conversation_message" and method_name == "create":
            method_name = "save_one"
        method = getattr(repo, method_name)
        await method(row)

    def _mark_completed(self, task: MongoCompensationTask) -> None:
        task.status = TERMINAL_STATUS
        task.completed_at = datetime.now()
        task.updated_at = task.completed_at
        task.next_retry_at = None
        self._db.commit()
        logger.info(
            "Mongo 补偿重放成功 | code=mongo_compensation_replay_succeeded "
            "object_type=%s farm_id=%s business_id=%s mysql_id=%s attempts=%s",
            task.object_type,
            task.farm_id,
            task.business_id,
            task.mysql_id,
            task.attempts,
        )

    def _mark_failed(self, task: MongoCompensationTask, exc: Exception) -> None:
        task.attempts += 1
        task.last_error = redact_error(exc)
        task.status = "failed" if task.attempts >= self._max_attempts else "pending"
        task.next_retry_at = datetime.now() + timedelta(
            seconds=self._retry_delay_seconds
        )
        task.updated_at = datetime.now()
        self._db.commit()
        logger.warning(
            "Mongo 补偿重放失败 | code=mongo_compensation_replay_failed "
            "object_type=%s farm_id=%s business_id=%s mysql_id=%s attempts=%s error=%s",
            task.object_type,
            task.farm_id,
            task.business_id,
            task.mysql_id,
            task.attempts,
            task.last_error,
        )


def redact_error(error: Any) -> str:
    """脱敏 Mongo URI 密码并截断错误摘要。"""
    text = str(error or "")
    text = re.sub(
        r"(mongodb(?:\+srv)?://[^:/\s@]+:)[^@\s]+@",
        r"\1***@",
        text,
    )
    return text[:ERROR_MAX_LENGTH]


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _match_mysql_id(rows: list[Any], mysql_id: int | None) -> Any | None:
    if mysql_id is None:
        return rows[0] if rows else None
    for row in rows:
        if getattr(row, "id", None) == mysql_id:
            return row
    return None


__all__ = [
    "MongoCompensationRecorder",
    "MongoCompensationReplayService",
    "MongoCompensationTask",
    "redact_error",
]
