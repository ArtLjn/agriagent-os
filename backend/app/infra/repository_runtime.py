"""Repository 运行时选择与 sync/async 桥接。"""

from __future__ import annotations

import asyncio
import inspect
import threading
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.infra.mongo import get_mongo_database
from app.infra.mongo_compensation import MongoCompensationRecorder
from app.infra.online_document_repositories import (
    build_agent_record_repository,
    build_conversation_message_repository,
    build_guardrails_log_repository,
)
from app.infra.trace_repository import build_trace_repository
from app.modules.data_flywheel.document_repositories import (
    build_data_flywheel_repository,
)

COLLECTION_NAMES = {
    "trace": "traceRecords",
    "case_drafts": "caseDrafts",
    "repair_packs": "repairPacks",
    "review_issue_chains": "reviewIssueChains",
    "prelabels": "prelabels",
    "conversation_messages": "conversationMessages",
    "agent_records": "agentRecords",
    "guardrails_logs": "guardrailsLogs",
}


async def resolve_maybe_awaitable(value: Any) -> Any:
    """在 async 路径中安全展开同步或异步 Repository 调用结果。"""
    if inspect.isawaitable(value):
        return await value
    return value


def run_maybe_awaitable(value: Any) -> Any:
    """在同步服务中执行可能返回 coroutine 的 Repository 方法。"""
    if not inspect.isawaitable(value):
        return value
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)
    return _run_awaitable_in_thread(value)


def get_trace_repository(db: Session) -> Any:
    """按配置创建 Trace Repository，默认 mysql 不依赖 Mongo。"""
    backend = settings.storage.trace
    collection = _collection_for_backend(backend, "trace")
    return build_trace_repository(
        backend,
        db,
        collection=collection,
        on_secondary_failure=MongoCompensationRecorder(db).record_failure,
    )


def get_data_flywheel_repository(db: Session, object_name: str) -> Any:
    """按配置创建 Data Flywheel 文档 Repository，默认 mysql 不依赖 Mongo。"""
    backend = getattr(settings.storage, object_name)
    collection = _collection_for_backend(backend, object_name)
    return build_data_flywheel_repository(
        object_name,
        backend,
        db,
        collection=collection,
        on_secondary_failure=MongoCompensationRecorder(db).record_failure,
    )


def get_conversation_message_repository(db: Session) -> Any:
    """按配置创建 ConversationMessage Repository。"""
    backend = settings.storage.conversation_messages
    collection = _collection_for_backend(backend, "conversation_messages")
    return build_conversation_message_repository(
        backend,
        db,
        collection=collection,
        hook=MongoCompensationRecorder(db).record_failure,
    )


def get_agent_record_repository(db: Session) -> Any:
    """按配置创建 AgentRecord Repository。"""
    backend = settings.storage.agent_records
    collection = _collection_for_backend(backend, "agent_records")
    return build_agent_record_repository(
        backend,
        db,
        collection=collection,
        hook=MongoCompensationRecorder(db).record_failure,
    )


def get_guardrails_log_repository(db: Session) -> Any:
    """按配置创建 GuardrailsLog Repository。"""
    backend = settings.storage.guardrails_logs
    collection = _collection_for_backend(backend, "guardrails_logs")
    return build_guardrails_log_repository(
        backend,
        db,
        collection=collection,
        hook=MongoCompensationRecorder(db).record_failure,
    )


def _collection_for_backend(backend: str, object_name: str) -> Any | None:
    if backend == "mysql":
        return None
    database = get_mongo_database()
    if database is None:
        raise RuntimeError(
            {
                "code": "MONGO_DATABASE_REQUIRED",
                "object": object_name,
                "backend": backend,
            }
        )
    return database[COLLECTION_NAMES[object_name]]


def _run_awaitable_in_thread(awaitable: Any) -> Any:
    result: dict[str, Any] = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(awaitable)
        except BaseException as exc:  # noqa: BLE001 - 需要跨线程原样抛回
            result["error"] = exc

    thread = threading.Thread(target=_runner)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


__all__ = [
    "get_data_flywheel_repository",
    "get_trace_repository",
    "resolve_maybe_awaitable",
    "run_maybe_awaitable",
]
