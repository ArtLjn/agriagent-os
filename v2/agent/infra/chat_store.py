"""Chat history store — MongoDB 实现。

聊天记录每条消息落库，沿用 archive 的 conversationMessages collection 字段命名：
  {
    farmId: 1,                      # 默认农场
    conversationId: <int or str>,   # 对话 session id
    sessionId: <str>,               # 同 conversationId
    role: "user" | "assistant",
    content: <str>,
    createdAt: "YYYY-MM-DD HH:MM:SS.ffffff",
    turnId: <str>,                   # v2 Turn 关联
    traceId: <str>,                  # v2 Trace 关联
    messageKind: <str>,              # prompt | final_answer | error_answer
  }

只做单条消息追加 + 简单查询；Trace 节点和 SSE 事件由独立集合负责。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from agent.config import settings

logger = logging.getLogger(__name__)


# 默认 farm_id（与 business 一致，archive 的 farms 表第 1 行）。
_DEFAULT_FARM_ID = 1


_client: AsyncIOMotorClient | None = None
_collection: AsyncIOMotorCollection | None = None
_indexes_initialized = False


def _collection_name() -> str:
    return settings.mongodb.collections.get(
        "conversation_messages", "conversationMessages"
    )


def get_collection() -> AsyncIOMotorCollection | None:
    """Get (lazy-init) the conversation messages collection.

    Returns None if MongoDB is disabled in config — callers should treat None
    as "no persistence" and skip silently.
    """
    global _client, _collection
    if not settings.mongodb.enabled:
        return None
    if _collection is None:
        if not settings.mongodb.uri or not settings.mongodb.database:
            logger.warning("mongodb enabled but uri/database missing; skip persistence")
            return None
        _client = AsyncIOMotorClient(
            settings.mongodb.uri,
            tls=settings.mongodb.tls,
            connectTimeoutMS=settings.mongodb.connect_timeout_ms,
            serverSelectionTimeoutMS=settings.mongodb.server_selection_timeout_ms,
            maxPoolSize=settings.mongodb.max_pool_size,
        )
        db = _client[settings.mongodb.database]
        _collection = db[_collection_name()]
    return _collection


async def ensure_indexes() -> None:
    """异步初始化消息集合索引，避免在同步连接初始化中遗留协程。"""
    global _indexes_initialized
    if _indexes_initialized:
        return
    coll = get_collection()
    if coll is None:
        return
    try:
        await coll.create_index(
            [("farmId", 1), ("conversationId", 1), ("createdAt", 1), ("_id", 1)],
            name="idx_messages_conversation_created",
        )
        await coll.create_index(
            [("conversationId", 1), ("turnId", 1), ("createdAt", 1)],
            name="idx_messages_turn_created",
        )
        _indexes_initialized = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("conversation message index init failed (non-fatal): %s", exc)


async def append_message(
    *,
    conversation_id: str,
    role: str,
    content: str,
    turn_id: str | None = None,
    trace_id: str | None = None,
    message_kind: str | None = None,
    meta: dict[str, Any] | None = None,
    user_id: str | None = None,
    farm_id: int | None = None,
) -> str | None:
    """Insert one message document. Returns MongoDB _id as string, or None if disabled."""
    coll = get_collection()
    if coll is None:
        return None
    await ensure_indexes()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    doc: dict[str, Any] = {
        "farmId": farm_id if farm_id is not None else _DEFAULT_FARM_ID,
        "conversationId": conversation_id,
        "sessionId": conversation_id,  # archive 习惯，sessionId = conversationId
        "role": role,
        "content": content,
        "createdAt": now,
    }
    if user_id:
        doc["userId"] = user_id
    if turn_id is not None:
        doc["turnId"] = turn_id
    if trace_id is not None:
        doc["traceId"] = trace_id
    if message_kind is not None:
        doc["messageKind"] = message_kind
    if meta:
        doc["meta"] = meta
    try:
        result = await coll.insert_one(doc)
        return str(result.inserted_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mongo insert failed (non-fatal): %s", exc)
        return None


async def load_recent(
    conversation_id: str,
    limit: int = 20,
    *,
    user_id: str | None = None,
    farm_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return recent N messages for a conversation, oldest first."""
    coll = get_collection()
    if coll is None:
        return []
    await ensure_indexes()
    try:
        filter_doc: dict[str, Any] = {"conversationId": conversation_id}
        if farm_id is not None:
            filter_doc["farmId"] = farm_id
        if user_id:
            filter_doc["userId"] = user_id
        cursor = (
            coll.find(
                filter_doc,
                projection={
                    "_id": 0,
                    "role": 1,
                    "content": 1,
                    "createdAt": 1,
                    "turnId": 1,
                    "traceId": 1,
                    "messageKind": 1,
                },
            )
            .sort("_id", -1)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        docs.reverse()  # oldest first
        return [
            {
                "role": d["role"],
                "content": d["content"],
                "createdAt": d.get("createdAt"),
                "turn_id": d.get("turnId"),
                "trace_id": d.get("traceId"),
                "message_kind": d.get("messageKind"),
            }
            for d in docs
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("mongo load_recent failed (non-fatal): %s", exc)
        return []


async def check_connection() -> None:
    """Startup sanity check — log connection status, never crash."""
    coll = get_collection()
    if coll is None:
        logger.info("mongodb disabled in config; chat history will not persist")
        return
    try:
        await ensure_indexes()
        count = await coll.count_documents({"farmId": _DEFAULT_FARM_ID})
        logger.info(
            "mongodb connection ok: %s collection=%s existing_messages=%d",
            settings.mongodb.uri.split("@")[-1],
            _collection_name(),
            count,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("mongodb connection check failed (non-fatal): %s", exc)


async def close() -> None:
    global _client, _collection, _indexes_initialized
    if _client is not None:
        _client.close()
    _client = None
    _collection = None
    _indexes_initialized = False


async def list_conversations(
    limit: int = 20,
    cursor: str | None = None,
    *,
    user_id: str | None = None,
    farm_id: int | None = None,
) -> dict[str, Any]:
    """List conversations with pagination.

    Aggregates by conversationId, returns the last message per conversation.
    Cursor-based: pass the last conversation_id from the previous page.

    Returns:
        {
            "items": [ {conversation_id, last_message, last_role, last_at, message_count}, ... ],
            "next_cursor": str | null,
            "has_more": bool
        }
    """
    coll = get_collection()
    if coll is None:
        return {"items": [], "next_cursor": None, "has_more": False}

    # First get all distinct conversation_ids sorted by last message time
    match: dict[str, Any] = {
        "farmId": farm_id if farm_id is not None else _DEFAULT_FARM_ID
    }
    if user_id:
        match["userId"] = user_id
    pipeline: list[dict[str, Any]] = [
        {"$match": match},
        {
            "$group": {
                "_id": "$conversationId",
                "last_msg": {"$last": "$content"},
                "last_role": {"$last": "$role"},
                "last_at": {"$last": "$createdAt"},
                "message_count": {"$sum": 1},
            }
        },
        {"$sort": {"last_at": -1}},
    ]

    if cursor:
        # Skip conversations already seen (cursor-based)
        pipeline.append({"$match": {"_id": {"$ne": cursor}}})

    pipeline.append({"$limit": limit + 1})

    try:
        results = await coll.aggregate(pipeline).to_list(length=limit + 1)
    except Exception as exc:  # noqa: BLE001
        logger.warning("list_conversations aggregation failed: %s", exc)
        return {"items": [], "next_cursor": None, "has_more": False}

    has_more = len(results) > limit
    results = results[:limit]

    items = []
    for r in results:
        items.append(
            {
                "conversation_id": r["_id"],
                "last_message": (r.get("last_msg") or "")[:200],
                "last_role": r.get("last_role", "user"),
                "last_at": r.get("last_at"),
                "message_count": r.get("message_count", 0),
            }
        )

    next_cursor = items[-1]["conversation_id"] if has_more and items else None
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_conversation(
    conversation_id: str,
    limit: int = 100,
    before: str | None = None,
    *,
    user_id: str | None = None,
    farm_id: int | None = None,
) -> dict[str, Any]:
    """Get messages for a conversation, oldest first.

    Returns:
        {
            "conversation_id": str,
            "items": [{role, content, created_at}],
            "count": int,
            "has_more": bool
        }
    """
    coll = get_collection()
    if coll is None:
        return {
            "conversation_id": conversation_id,
            "items": [],
            "count": 0,
            "has_more": False,
        }
    await ensure_indexes()

    filter_doc: dict[str, Any] = {
        "conversationId": conversation_id,
        "farmId": farm_id if farm_id is not None else _DEFAULT_FARM_ID,
    }
    if user_id:
        filter_doc["userId"] = user_id
    if before:
        filter_doc["createdAt"] = {"$lt": before}

    try:
        cursor = (
            coll.find(
                filter_doc,
                projection={
                    "_id": 1,
                    "role": 1,
                    "content": 1,
                    "createdAt": 1,
                    "turnId": 1,
                    "traceId": 1,
                    "messageKind": 1,
                    "meta": 1,
                },
            )
            .sort("_id", 1)  # oldest first
            .limit(limit + 1)
        )
        docs = await cursor.to_list(length=limit + 1)
        has_more = len(docs) > limit
        docs = docs[:limit]

        items = [
            {
                "role": d["role"],
                "content": d["content"],
                "created_at": d.get("createdAt"),
                "message_id": str(d.get("_id")) if d.get("_id") is not None else None,
                "turn_id": d.get("turnId"),
                "trace_id": d.get("traceId"),
                "message_kind": d.get("messageKind"),
                "meta": d.get("meta") or {},
            }
            for d in docs
        ]
        return {
            "conversation_id": conversation_id,
            "items": items,
            "count": len(items),
            "has_more": has_more,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_conversation failed: %s", exc)
        return {
            "conversation_id": conversation_id,
            "items": [],
            "count": 0,
            "has_more": False,
        }
