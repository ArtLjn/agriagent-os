"""Chat history store — MongoDB 实现。

聊天记录每条消息落库，沿用 archive 的 conversationMessages collection 字段命名：
  {
    farmId: 1,                      # 默认农场
    conversationId: <int or str>,   # 对话 session id
    sessionId: <str>,               # 同 conversationId
    role: "user" | "assistant",
    content: <str>,
    createdAt: "YYYY-MM-DD HH:MM:SS.ffffff",
    turnId: <int>,                   # 可选，archive 旧数据用
  }

只做单条消息追加 + 简单查询；不做 trace/agent_records，那些 v2 MVP 暂不落库。
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
        # 索引：按 conversationId 倒序查最近消息（archive 也是这样查）。
        # 不在启动时阻塞建索引，第一次写入时 MongoDB 自动建（如已有则跳过）。
        try:
            _collection.create_index(
                [("conversationId", -1), ("_id", -1)], background=True
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("create_index failed (non-fatal): %s", exc)
    return _collection


async def append_message(
    *,
    conversation_id: str,
    role: str,
    content: str,
    turn_id: int | None = None,
    meta: dict[str, Any] | None = None,
) -> str | None:
    """Insert one message document. Returns MongoDB _id as string, or None if disabled."""
    coll = get_collection()
    if coll is None:
        return None
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    doc: dict[str, Any] = {
        "farmId": _DEFAULT_FARM_ID,
        "conversationId": conversation_id,
        "sessionId": conversation_id,  # archive 习惯，sessionId = conversationId
        "role": role,
        "content": content,
        "createdAt": now,
    }
    if turn_id is not None:
        doc["turnId"] = turn_id
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
) -> list[dict[str, Any]]:
    """Return recent N messages for a conversation, oldest first."""
    coll = get_collection()
    if coll is None:
        return []
    try:
        cursor = (
            coll.find(
                {"conversationId": conversation_id},
                projection={"_id": 0, "role": 1, "content": 1, "createdAt": 1},
            )
            .sort("_id", -1)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        docs.reverse()  # oldest first
        return [
            {"role": d["role"], "content": d["content"], "createdAt": d.get("createdAt")}
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
    global _client, _collection
    if _client is not None:
        _client.close()
    _client = None
    _collection = None


async def list_conversations(
    limit: int = 20,
    cursor: str | None = None,
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
    pipeline: list[dict[str, Any]] = [
        {"$match": {"farmId": _DEFAULT_FARM_ID}},
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
        return {"conversation_id": conversation_id, "items": [], "count": 0, "has_more": False}

    filter_doc: dict[str, Any] = {"conversationId": conversation_id}
    if before:
        filter_doc["createdAt"] = {"$lt": before}

    try:
        cursor = (
            coll.find(
                filter_doc,
                projection={"_id": 0, "role": 1, "content": 1, "createdAt": 1},
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
        return {"conversation_id": conversation_id, "items": [], "count": 0, "has_more": False}
