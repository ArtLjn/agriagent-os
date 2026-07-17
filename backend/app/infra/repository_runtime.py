"""Repository 运行时选择与 sync/async 桥接。"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from collections.abc import Coroutine
from typing import Any

from sqlalchemy import inspect as sa_inspect
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
from app.platforms.shared.repository_selector import (
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

DOCUMENT_TABLES = {
    "trace": "trace_records",
    "case_drafts": "agent_case_drafts",
    "repair_packs": "agent_repair_packs",
    "review_issue_chains": "agent_review_issue_chains",
    "prelabels": "agent_data_flywheel_prelabels",
    "conversation_messages": "conversation_messages",
    "agent_records": "agent_records",
    "guardrails_logs": "guardrails_logs",
}

logger = logging.getLogger(__name__)
_main_event_loop: asyncio.AbstractEventLoop | None = None
_missing_table_cache: set[str] = set()


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
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        main_loop = get_main_event_loop()
        if main_loop is not None and main_loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                _as_coroutine(value),
                main_loop,
            ).result()
        return asyncio.run(value)
    main_loop = get_main_event_loop()
    if (
        main_loop is not None
        and main_loop.is_running()
        and running_loop is not main_loop
    ):
        return asyncio.run_coroutine_threadsafe(
            _as_coroutine(value),
            main_loop,
        ).result()
    return _run_awaitable_in_thread(_as_coroutine(value))


def set_main_event_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    """注册 FastAPI 主事件循环，供同步线程安全调用 async Repository。"""
    global _main_event_loop
    _main_event_loop = loop


def get_main_event_loop() -> asyncio.AbstractEventLoop | None:
    """返回已注册的 FastAPI 主事件循环。"""
    if _main_event_loop is None or _main_event_loop.is_closed():
        return None
    return _main_event_loop


def get_trace_repository(db: Session) -> Any:
    """按配置创建 Trace Repository，默认 mysql 不依赖 Mongo。"""
    backend = _effective_backend(settings.storage.trace, db, "trace")
    collection = _collection_for_backend(backend, "trace")
    return build_trace_repository(
        backend,
        db,
        collection=collection,
        on_secondary_failure=MongoCompensationRecorder(db).record_failure,
    )


def get_data_flywheel_repository(db: Session, object_name: str) -> Any:
    """按配置创建 Data Flywheel 文档 Repository，默认 mysql 不依赖 Mongo。"""
    backend = _effective_backend(
        getattr(settings.storage, object_name), db, object_name
    )
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
    backend = _effective_backend(
        settings.storage.conversation_messages,
        db,
        "conversation_messages",
    )
    collection = _collection_for_backend(backend, "conversation_messages")
    return build_conversation_message_repository(
        backend,
        db,
        collection=collection,
        hook=MongoCompensationRecorder(db).record_failure,
    )


def get_agent_record_repository(db: Session) -> Any:
    """按配置创建 AgentRecord Repository。"""
    backend = _effective_backend(settings.storage.agent_records, db, "agent_records")
    collection = _collection_for_backend(backend, "agent_records")
    return build_agent_record_repository(
        backend,
        db,
        collection=collection,
        hook=MongoCompensationRecorder(db).record_failure,
    )


def get_guardrails_log_repository(db: Session) -> Any:
    """按配置创建 GuardrailsLog Repository。"""
    backend = _effective_backend(
        settings.storage.guardrails_logs,
        db,
        "guardrails_logs",
    )
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


def _effective_backend(configured: str, db: Session, object_name: str) -> str:
    if configured == "mongo":
        return configured
    table_name = DOCUMENT_TABLES.get(object_name)
    if table_name is None:
        return configured
    if table_name in _missing_table_cache:
        return "mongo"
    if _mysql_table_exists(db, table_name):
        if configured in {"dual", "mongo-read"} and get_mongo_database() is None:
            logger.debug(
                "Mongo 未初始化，文档仓储回退 MySQL | code=document_mongo_unavailable_use_mysql object=%s table=%s configured=%s",
                object_name,
                table_name,
                configured,
            )
            return "mysql"
        return configured
    _missing_table_cache.add(table_name)
    logger.warning(
        "MySQL 文档表不存在，强制切换 Mongo 仓储 | code=document_table_missing_use_mongo object=%s table=%s configured=%s",
        object_name,
        table_name,
        configured,
    )
    return "mongo"


def _mysql_table_exists(db: Session, table_name: str) -> bool:
    try:
        bind = db.get_bind()
    except Exception:
        bind = getattr(db, "bind", None)
    if bind is None:
        return True
    try:
        return bool(sa_inspect(bind).has_table(table_name))
    except Exception as exc:
        logger.debug(
            "MySQL 表存在性检查跳过 | code=document_table_check_skipped table=%s error=%s",
            table_name,
            exc,
        )
        return True


def clear_missing_table_cache() -> None:
    """清理缺表缓存，供测试或迁移后显式刷新。"""
    _missing_table_cache.clear()


async def _as_coroutine(awaitable: Any) -> Any:
    return await awaitable


def _run_awaitable_in_thread(awaitable: Coroutine[Any, Any, Any]) -> Any:
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
    "get_agent_record_repository",
    "get_conversation_message_repository",
    "get_guardrails_log_repository",
    "get_main_event_loop",
    "get_trace_repository",
    "resolve_maybe_awaitable",
    "run_maybe_awaitable",
    "clear_missing_table_cache",
    "set_main_event_loop",
]
