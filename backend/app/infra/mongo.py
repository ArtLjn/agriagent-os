"""MongoDB client 生命周期与健康检查。"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import MongoConfig
from app.core.logger import get_logger

logger = get_logger(__name__)

_mongo_client: AsyncIOMotorClient | None = None
_mongo_database_name: str | None = None


def redact_mongo_uri(uri: str) -> str:
    """脱敏 MongoDB 连接串中的密码。"""
    if not uri:
        return uri
    try:
        parts = urlsplit(uri)
    except ValueError:
        return re.sub(r"(mongodb(?:\+srv)?://[^:/@]+:)[^@]+@", r"\1***@", uri)

    if "@" not in parts.netloc:
        return uri

    credentials, hosts = parts.netloc.rsplit("@", 1)
    if ":" not in credentials:
        return uri

    username, _password = credentials.rsplit(":", 1)
    netloc = f"{username}:***@{hosts}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _redact_text(text: str) -> str:
    return re.sub(
        r"(mongodb(?:\+srv)?://[^:/\s@]+:)[^@\s]+@",
        r"\1***@",
        text,
    )


def create_mongo_client(config: MongoConfig) -> AsyncIOMotorClient:
    """按配置创建异步 MongoDB client。"""
    if not config.uri:
        raise ValueError("MongoDB URI 未配置")

    return AsyncIOMotorClient(
        config.uri,
        tls=config.tls,
        connectTimeoutMS=config.connect_timeout_ms,
        serverSelectionTimeoutMS=config.server_selection_timeout_ms,
        maxPoolSize=config.max_pool_size,
    )


def set_mongo_client(
    client: AsyncIOMotorClient | None,
    database_name: str | None = None,
) -> None:
    """设置共享 MongoDB client，便于 lifespan 和测试注入。"""
    global _mongo_client, _mongo_database_name

    _mongo_client = client
    _mongo_database_name = database_name


def get_mongo_client() -> AsyncIOMotorClient | None:
    """返回共享 MongoDB client。"""
    return _mongo_client


def get_mongo_database() -> AsyncIOMotorDatabase | None:
    """返回共享 MongoDB database；未初始化时返回 None。"""
    if _mongo_client is None or _mongo_database_name is None:
        return None
    return _mongo_client[_mongo_database_name]


def init_mongo_client(config: MongoConfig) -> AsyncIOMotorClient | None:
    """应用启动时初始化共享 MongoDB client。"""
    if not config.enabled:
        set_mongo_client(None)
        logger.info("MongoDB 未启用 | code=mongo_disabled")
        return None

    client = create_mongo_client(config)
    set_mongo_client(client, config.database)
    logger.info(
        "MongoDB client 已初始化 | code=mongo_client_initialized uri=%s database=%s",
        redact_mongo_uri(config.uri),
        config.database,
    )
    return client


async def close_mongo_client() -> None:
    """关闭共享 MongoDB client。"""
    client = get_mongo_client()
    if client is None:
        return

    client.close()
    set_mongo_client(None)
    logger.info("MongoDB client 已关闭 | code=mongo_client_closed")


async def check_mongo_health(
    database: AsyncIOMotorDatabase | None = None,
) -> dict[str, Any]:
    """执行 MongoDB ping 并返回可序列化健康状态。"""
    db = database if database is not None else get_mongo_database()
    if db is None:
        return {
            "status": "disabled",
            "database": None,
            "code": "mongo_not_configured",
        }

    database_name = getattr(db, "name", None)
    try:
        await db.client.admin.command("ping")
    except Exception as exc:
        error = _redact_text(str(exc))
        logger.warning(
            "MongoDB ping 失败 | code=mongo_ping_failed database=%s error=%s",
            database_name,
            error,
        )
        return {
            "status": "error",
            "database": database_name,
            "code": "mongo_ping_failed",
            "context": {"error": error},
        }

    return {
        "status": "ok",
        "database": database_name,
        "code": "mongo_ping_ok",
    }
