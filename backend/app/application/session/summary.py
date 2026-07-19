"""会话摘要后台任务调度。"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from sqlalchemy.orm import Session

from app.shared.database import SessionLocal

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]
CreateTask = Callable[[Awaitable[None]], Any]
MemoryServiceProvider = Callable[[], Any]


def schedule_session_summary(
    *,
    conversation_id: int | None,
    farm_id: int,
    session_id: str | None,
    memory_service: Any | None = None,
    memory_service_provider: MemoryServiceProvider | None = None,
    session_factory: SessionFactory = SessionLocal,
    create_task: CreateTask = asyncio.create_task,
    timeout_seconds: float = 30.0,
) -> Any | None:
    """在聊天完成后调度会话摘要任务。"""
    if conversation_id is None or not session_id:
        return None

    task_coro = run_session_summary_task(
        conversation_id=conversation_id,
        farm_id=farm_id,
        session_id=session_id,
        memory_service=memory_service,
        memory_service_provider=memory_service_provider,
        session_factory=session_factory,
        timeout_seconds=timeout_seconds,
    )
    try:
        return create_task(task_coro)
    except Exception:
        task_coro.close()
        logger.exception(
            "会话摘要后台任务调度失败",
            extra={
                "code": "SESSION_SUMMARY_TASK_SCHEDULE_FAILED",
                "farm_id": farm_id,
                "session_id": session_id,
                "conversation_id": conversation_id,
            },
        )
        return None


async def run_session_summary_task(
    *,
    conversation_id: int,
    farm_id: int,
    session_id: str | None,
    memory_service: Any | None = None,
    memory_service_provider: MemoryServiceProvider | None = None,
    session_factory: SessionFactory = SessionLocal,
    timeout_seconds: float = 30.0,
) -> None:
    """使用独立 DB session 触发会话摘要，失败不影响聊天主流程。"""
    fresh_db = session_factory()
    try:
        service = memory_service
        if service is None and memory_service_provider is not None:
            service = memory_service_provider()
        if service is None:
            logger.warning(
                "会话摘要后台任务缺少 memory_service",
                extra={
                    "code": "SESSION_SUMMARY_TASK_NO_SERVICE",
                    "farm_id": farm_id,
                    "session_id": session_id,
                    "conversation_id": conversation_id,
                },
            )
            return
        await asyncio.wait_for(
            service.maybe_summarize(
                fresh_db,
                conversation_id,
                farm_id,
                session_id,
                messages=None,
            ),
            timeout=timeout_seconds,
        )
    except asyncio.CancelledError:
        with suppress(Exception):
            fresh_db.rollback()
        raise
    except TimeoutError:
        logger.warning(
            "会话摘要后台任务超时",
            extra={
                "code": "SESSION_SUMMARY_TASK_TIMEOUT",
                "farm_id": farm_id,
                "session_id": session_id,
                "conversation_id": conversation_id,
                "timeout_seconds": timeout_seconds,
            },
        )
    except Exception:
        logger.exception(
            "会话摘要后台任务失败",
            extra={
                "code": "SESSION_SUMMARY_TASK_FAILED",
                "farm_id": farm_id,
                "session_id": session_id,
                "conversation_id": conversation_id,
            },
        )
    finally:
        fresh_db.close()
