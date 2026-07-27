"""Agent Task Context 持久化模型与存储。"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta
from types import ModuleType
from typing import Any

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, or_
from sqlalchemy.orm import Session

from app.shared.compatibility import StrEnum
from app.shared.database import Base


class AgentTaskState(Base):
    """每个会话最近一个可恢复任务状态。"""

    __tablename__ = "agent_task_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=False, unique=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    task_type = Column(String(64), nullable=False, index=True)
    goal = Column(Text, nullable=False)
    entities_json = Column(JSON, nullable=False, default=dict)
    observations_json = Column(JSON, nullable=False, default=list)
    missing_information_json = Column(JSON, nullable=False, default=list)
    next_action = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class TaskStateStatus(StrEnum):
    """Task state 最小生命周期状态。"""

    ACTIVE = "active"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


ACTIVE_STATUSES = (TaskStateStatus.ACTIVE.value, TaskStateStatus.WAITING_USER.value)
DEFAULT_TTL = timedelta(hours=24)


class AgentTaskStateStore:
    """提供每个 farm/user/session 最近任务状态的最小读写接口。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_active_task(
        self,
        *,
        farm_id: int,
        user_id: str,
        session_id: str,
        task_type: str,
        goal: str,
        entities: dict[str, Any] | None = None,
        observations: list[str] | None = None,
        missing_information: list[str] | None = None,
        next_action: str | None = None,
        status: TaskStateStatus | str = TaskStateStatus.ACTIVE,
        expires_at: datetime | None = None,
    ) -> AgentTaskState:
        """创建或更新当前会话最近一个 active/waiting_user 任务。"""
        normalized_status = self._normalize_status(status)
        task = self.get_active_task(
            farm_id=farm_id,
            user_id=user_id,
            session_id=session_id,
        )
        if task is None:
            task = AgentTaskState(
                task_id=uuid.uuid4().hex,
                farm_id=farm_id,
                user_id=user_id,
                session_id=session_id,
            )
            self.db.add(task)

        task.task_type = task_type
        task.goal = goal
        task.entities_json = dict(entities or {})
        task.observations_json = list(observations or [])
        task.missing_information_json = list(missing_information or [])
        task.next_action = next_action
        task.status = normalized_status
        task.expires_at = expires_at or (datetime.now() + DEFAULT_TTL)
        task.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_active_task(
        self,
        *,
        farm_id: int,
        user_id: str | None,
        session_id: str | None,
    ) -> AgentTaskState | None:
        """读取同 farm/user/session 最近一个未过期 active/waiting_user 任务。"""
        if not user_id or not session_id:
            return None
        now = datetime.now()
        return (
            self.db.query(AgentTaskState)
            .filter(
                AgentTaskState.farm_id == farm_id,
                AgentTaskState.user_id == user_id,
                AgentTaskState.session_id == session_id,
                AgentTaskState.status.in_(ACTIVE_STATUSES),
                or_(
                    AgentTaskState.expires_at.is_(None), AgentTaskState.expires_at > now
                ),
            )
            .order_by(AgentTaskState.updated_at.desc(), AgentTaskState.id.desc())
            .first()
        )

    def mark_completed(
        self,
        *,
        farm_id: int,
        user_id: str,
        session_id: str,
        task_id: str,
    ) -> AgentTaskState | None:
        """将任务标记为已完成。"""
        return self._mark_status(
            farm_id=farm_id,
            user_id=user_id,
            session_id=session_id,
            task_id=task_id,
            status=TaskStateStatus.COMPLETED,
        )

    def mark_cancelled(
        self,
        *,
        farm_id: int,
        user_id: str,
        session_id: str,
        task_id: str,
    ) -> AgentTaskState | None:
        """将任务标记为已取消。"""
        return self._mark_status(
            farm_id=farm_id,
            user_id=user_id,
            session_id=session_id,
            task_id=task_id,
            status=TaskStateStatus.CANCELLED,
        )

    def _mark_status(
        self,
        *,
        farm_id: int,
        user_id: str,
        session_id: str,
        task_id: str,
        status: TaskStateStatus,
    ) -> AgentTaskState | None:
        task = (
            self.db.query(AgentTaskState)
            .filter(
                AgentTaskState.farm_id == farm_id,
                AgentTaskState.user_id == user_id,
                AgentTaskState.session_id == session_id,
                AgentTaskState.task_id == task_id,
            )
            .first()
        )
        if task is None:
            return None
        task.status = status.value
        task.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(task)
        return task

    @staticmethod
    def _normalize_status(status: TaskStateStatus | str) -> str:
        value = status.value if isinstance(status, TaskStateStatus) else str(status)
        allowed = {item.value for item in TaskStateStatus}
        if value not in allowed:
            raise ValueError(f"不支持的 task state status: {value}")
        return value


def _install_legacy_task_state_modules() -> None:
    legacy_modules = {
        "models": ("AgentTaskState",),
        "store": ("AgentTaskStateStore", "TaskStateStatus"),
    }
    for module_name, exported_names in legacy_modules.items():
        module = ModuleType(f"{__name__}.{module_name}")
        module.__doc__ = "兼容入口；实际维护点是 app.context.task_state。"
        for exported_name in exported_names:
            setattr(module, exported_name, globals()[exported_name])
        module.__all__ = list(exported_names)
        sys.modules[module.__name__] = module
        setattr(sys.modules[__name__], module_name, module)


__all__ = [
    "AgentTaskState",
    "AgentTaskStateStore",
    "TaskStateStatus",
]

_install_legacy_task_state_modules()
