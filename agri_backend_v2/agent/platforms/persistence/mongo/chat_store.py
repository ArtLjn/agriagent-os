"""Chat history store — MongoDB 实现。

聊天记录每条消息落库，沿用 archive 的 conversationMessages collection 字段命名：
  {
    farmId: 1,                      # 默认农场
    conversationId: <int or str>,   # 对话 session id
    sessionId: <str>,               # 同 conversationId
    role: "user" | "assistant",
    content: <str>,
    createdAt: "YYYY-MM-DD HH:MM:SS.ffffff",
    turnId: <str>,                   # agri_backend_v2 Turn 关联
    traceId: <str>,                  # agri_backend_v2 Trace 关联
    messageKind: <str>,              # prompt | final_answer | error_answer
  }

只做单条消息追加 + 简单查询；Trace 节点和 SSE 事件由独立集合负责。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from agent.config import settings
from agent.platforms.persistence.mongo.conversation_catalog import (
    list_conversations as list_conversations,  # noqa: PLC0414 -- 保留会话查询调用方的入口。
)
from agent.platforms.persistence.mongo.conversation_state import (
    _unavailable_result,
)
from agent.platforms.persistence.mongo.conversation_state import (
    claim_summary_generation as claim_summary_generation,  # noqa: PLC0414 -- 保留现有调用方使用的显式重导出。
)
from agent.platforms.persistence.mongo.conversation_state import (
    clear_expired_session_state as clear_expired_session_state,  # noqa: PLC0414 -- 保留现有调用方使用的显式重导出。
)
from agent.platforms.persistence.mongo.conversation_state import (
    get_conversation_state as get_conversation_state,  # noqa: PLC0414 -- 保留现有调用方使用的显式重导出。
)
from agent.platforms.persistence.mongo.conversation_state import (
    reset_conversation_state as reset_conversation_state,  # noqa: PLC0414 -- 保留现有调用方使用的显式重导出。
)
from agent.platforms.persistence.mongo.conversation_state import (
    save_conversation_state as save_conversation_state,  # noqa: PLC0414 -- 保留现有调用方使用的显式重导出。
)
from agent.platforms.persistence.mongo.conversation_state import (
    save_summary_result as save_summary_result,  # noqa: PLC0414 -- 保留现有调用方使用的显式重导出。
)

logger = logging.getLogger(__name__)


# 默认 farm_id（与 business 一致，archive 的 farms 表第 1 行）。
_DEFAULT_FARM_ID = 1
# 更换事实协议时同时更换事件字段，旧消费者只扫描旧字段，不能抢走新版任务。
MEMORY_LEARNING_EVENT = "memoryLearningV3"


_client: AsyncIOMotorClient | None = None
_collection: AsyncIOMotorCollection | None = None
_indexes_initialized = False
_state_collection: AsyncIOMotorCollection | None = None
_state_indexes_initialized = False
_observation_collection: AsyncIOMotorCollection | None = None
_observation_indexes_initialized = False
_CURSOR_VERSION = 1
_MESSAGE_KIND_ALIASES = {
    "user_input": "prompt",
    "assistant_answer": "final_answer",
    "error": "error_answer",
}
_PUBLIC_MESSAGE_KINDS = frozenset(
    {"prompt", "final_answer", "error_answer", "tool_summary"}
)
_PUBLIC_META_KEYS = frozenset(
    {
        "outcome",
        "tool_summary",
        "approval_summary",
        "business_result",
        "error_code",
        "error_message",
        "stop_reason",
        "status",
        "source_status",
        "evidence_status",
        "source",
    }
)
_MAX_MESSAGE_META_BYTES = 8192


class ConversationCursorError(ValueError):
    """历史消息 cursor 不可安全继续使用时返回的结构化错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _normalize_message_kind(value: Any) -> str | None:
    """统一历史消息类型，只保留公开消息类型，避免内部事件污染历史。"""
    if value is None:
        return None
    normalized = str(value).strip()
    canonical = _MESSAGE_KIND_ALIASES.get(normalized, normalized or None)
    return canonical if canonical in _PUBLIC_MESSAGE_KINDS else None


def _sanitize_message_meta(meta: Any) -> dict[str, Any]:
    """只返回脱敏摘要字段，避免工具参数或隐藏执行内容进入历史消息。"""
    if not isinstance(meta, dict):
        return {}
    selected = {key: meta[key] for key in _PUBLIC_META_KEYS if key in meta}
    try:
        encoded = json.dumps(selected, ensure_ascii=False, default=str)
        if len(encoded.encode("utf-8")) > _MAX_MESSAGE_META_BYTES:
            return {}
        return json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _cursor_secret() -> bytes:
    """使用 Agent JWT secret 签名 cursor，防止客户端篡改租户和分页锚点。"""
    secret = str(settings.auth.jwt_secret or "")
    if not secret:
        raise ConversationCursorError(
            "conversation_cursor_unavailable", "会话分页 cursor 签名密钥未配置"
        )
    return secret.encode("utf-8")


def _encode_conversation_cursor(payload: dict[str, Any]) -> str:
    """生成只允许向更早历史读取的 opaque cursor。"""
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    signature = hmac.new(_cursor_secret(), encoded.encode("ascii"), hashlib.sha256)
    return f"{encoded}.{signature.hexdigest()}"


def _decode_conversation_cursor(
    cursor: str,
    *,
    conversation_id: str,
    user_id: str | None,
    farm_id: int | None,
    snapshot_revision: int,
) -> dict[str, Any]:
    """校验 cursor 的签名、租户、会话和快照版本后返回分页锚点。"""
    try:
        encoded, signature = cursor.split(".", 1)
        expected = hmac.new(
            _cursor_secret(), encoded.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ConversationCursorError(
                "conversation_cursor_invalid", "分页 cursor 无效"
            )
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
    except ConversationCursorError:
        raise
    except (binascii.Error, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise ConversationCursorError(
            "conversation_cursor_invalid", "分页 cursor 无效"
        ) from exc

    expected_farm_id = farm_id if farm_id is not None else _DEFAULT_FARM_ID
    if (
        payload.get("v") != _CURSOR_VERSION
        or payload.get("conversation_id") != conversation_id
        or payload.get("user_id") != user_id
        or payload.get("farm_id") != expected_farm_id
        or payload.get("direction") != "older"
    ):
        raise ConversationCursorError(
            "conversation_cursor_scope_mismatch", "分页 cursor 不属于当前会话或用户"
        )
    try:
        cursor_revision = int(payload.get("snapshot_revision", -1))
    except (TypeError, ValueError) as exc:
        raise ConversationCursorError(
            "conversation_cursor_invalid", "分页 cursor 无效"
        ) from exc
    if cursor_revision != snapshot_revision:
        raise ConversationCursorError(
            "conversation_revision_changed", "会话内容已更新，请重新加载最新历史"
        )
    anchor = payload.get("anchor")
    if (
        not isinstance(anchor, dict)
        or not anchor.get("created_at")
        or not anchor.get("message_id")
    ):
        raise ConversationCursorError(
            "conversation_cursor_invalid", "分页 cursor 缺少锚点"
        )
    return anchor


def _collection_name() -> str:
    return settings.mongodb.collections.get(
        "conversation_messages", "conversationMessages"
    )


def _state_collection_name() -> str:
    """返回 Session state 集合名，优先使用新的 Context 配置。"""
    context = getattr(settings, "context", None)
    state_cfg = getattr(context, "conversation_state", None)
    configured = getattr(state_cfg, "collection", "conversationStates")
    return settings.mongodb.collections.get("conversation_states", configured)


def _observation_collection_name() -> str:
    return settings.mongodb.collections.get("memory_observations", "memoryObservations")


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


def get_state_collection() -> AsyncIOMotorCollection | None:
    """Get the MongoDB collection used for tenant-scoped conversation state.

    `None` is deliberately reserved for an unavailable persistence boundary;
    state read/write functions expose that condition as a structured result.
    """
    global _client, _state_collection
    if not settings.mongodb.enabled:
        return None
    if _state_collection is None:
        if not settings.mongodb.uri or not settings.mongodb.database:
            logger.warning(
                "mongodb enabled but uri/database missing; conversation state unavailable"
            )
            return None
        try:
            if _client is None:
                _client = AsyncIOMotorClient(
                    settings.mongodb.uri,
                    tls=settings.mongodb.tls,
                    connectTimeoutMS=settings.mongodb.connect_timeout_ms,
                    serverSelectionTimeoutMS=settings.mongodb.server_selection_timeout_ms,
                    maxPoolSize=settings.mongodb.max_pool_size,
                )
            _state_collection = _client[settings.mongodb.database][
                _state_collection_name()
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("conversation state Mongo client init failed: %s", exc)
            return None
    return _state_collection


def get_observation_collection() -> AsyncIOMotorCollection | None:
    """返回 MemoryObservation 事件集合；不等同于长期事实集合。"""
    global _client, _observation_collection
    if not settings.mongodb.enabled:
        return None
    if _observation_collection is None:
        if not settings.mongodb.uri or not settings.mongodb.database:
            logger.warning(
                "mongodb enabled but uri/database missing; memory observation unavailable"
            )
            return None
        try:
            if _client is None:
                _client = AsyncIOMotorClient(
                    settings.mongodb.uri,
                    tls=settings.mongodb.tls,
                    connectTimeoutMS=settings.mongodb.connect_timeout_ms,
                    serverSelectionTimeoutMS=settings.mongodb.server_selection_timeout_ms,
                    maxPoolSize=settings.mongodb.max_pool_size,
                )
            _observation_collection = _client[settings.mongodb.database][
                _observation_collection_name()
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory observation Mongo client init failed: %s", exc)
            return None
    return _observation_collection


async def status() -> dict[str, Any]:
    """返回 Mongo 持久化边界状态，区分 disabled、unavailable 和 ready。"""
    if not settings.mongodb.enabled:
        return {
            "enabled": False,
            "reachable": False,
            "source_status": "unavailable",
            "code": "mongo_not_configured",
        }
    collection = get_collection()
    if collection is None or _client is None:
        return {
            "enabled": True,
            "reachable": False,
            "source_status": "unavailable",
            "code": "mongo_config_missing",
        }
    try:
        await _client.admin.command("ping")
    except Exception as exc:  # noqa: BLE001
        logger.warning("mongodb health check failed: %s", exc)
        return {
            "enabled": True,
            "reachable": False,
            "source_status": "unavailable",
            "code": "mongo_unavailable",
        }
    return {"enabled": True, "reachable": True, "source_status": "mongo"}


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
        await coll.create_index(
            [(f"{MEMORY_LEARNING_EVENT}.status", 1), ("createdAt", 1)],
            name="idx_messages_memory_outbox_v3",
            partialFilterExpression={
                f"{MEMORY_LEARNING_EVENT}.status": {"$exists": True}
            },
        )
        await coll.create_index(
            [("farmId", 1), ("conversationId", 1), ("idempotencyKey", 1)],
            name="uniq_message_idempotency_key",
            unique=True,
            partialFilterExpression={"idempotencyKey": {"$exists": True}},
        )
        _indexes_initialized = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("conversation message index init failed (non-fatal): %s", exc)


async def ensure_observation_indexes() -> dict[str, Any]:
    """初始化 observation 事件的租户与幂等索引。"""
    global _observation_indexes_initialized
    if _observation_indexes_initialized:
        return {"ok": True, "status": "ready", "source_status": "mongo"}
    coll = get_observation_collection()
    if coll is None:
        return _unavailable_result("ensure_observation_indexes")
    try:
        await coll.create_index(
            [("userId", 1), ("farmId", 1), ("conversationId", 1), ("observationId", 1)],
            name="uniq_memory_observation_id",
            unique=True,
        )
        await coll.create_index(
            [("userId", 1), ("farmId", 1), ("conversationId", 1), ("createdAt", -1)],
            name="idx_memory_observation_created",
        )
        _observation_indexes_initialized = True
        return {"ok": True, "status": "ready", "source_status": "mongo"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("memory observation index init failed: %s", exc)
        return _unavailable_result("ensure_observation_indexes", exc)


async def ensure_state_indexes() -> dict[str, Any]:
    """初始化 Conversation state 索引，并明确返回持久化边界状态。"""
    global _state_indexes_initialized
    if _state_indexes_initialized:
        return {"ok": True, "status": "ready", "source_status": "mongo"}
    coll = get_state_collection()
    if coll is None:
        return _unavailable_result("ensure_state_indexes")
    try:
        await coll.create_index(
            [("userId", 1), ("farmId", 1), ("conversationId", 1)],
            name="uniq_conversation_state_tenant",
            unique=True,
        )
        await coll.create_index(
            [("userId", 1), ("farmId", 1), ("updatedAt", -1)],
            name="idx_conversation_state_updated",
        )
        _state_indexes_initialized = True
        return {"ok": True, "status": "ready", "source_status": "mongo"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("conversation state index init failed: %s", exc)
        return _unavailable_result("ensure_state_indexes", exc)


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
    idempotency_key: str | None = None,
    learning_event: dict[str, Any] | None = None,
) -> str | None:
    """幂等追加用户可见消息，返回 MongoDB _id；不可用时返回 None。"""
    coll = get_collection()
    if coll is None:
        return None
    await ensure_indexes()
    tenant_farm_id = farm_id if farm_id is not None else _DEFAULT_FARM_ID
    try:
        if idempotency_key:
            existing = await coll.find_one(
                {
                    "farmId": tenant_farm_id,
                    "conversationId": conversation_id,
                    "idempotencyKey": idempotency_key,
                },
                projection={"_id": 1},
            )
            if existing is not None:
                return str(existing.get("_id"))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        doc: dict[str, Any] = {
            "farmId": tenant_farm_id,
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
        normalized_kind = _normalize_message_kind(message_kind)
        if normalized_kind is not None:
            doc["messageKind"] = normalized_kind
        safe_meta = _sanitize_message_meta(meta)
        if safe_meta:
            doc["meta"] = safe_meta
        if idempotency_key:
            doc["idempotencyKey"] = idempotency_key
        if learning_event and role == "user" and normalized_kind == "prompt":
            # 与原文同一文档提交，进程在派发前退出也不会丢失学习事件。
            doc[MEMORY_LEARNING_EVENT] = learning_event
        result = await coll.insert_one(doc)
        return str(result.inserted_id)
    except Exception as exc:  # noqa: BLE001
        if idempotency_key:
            try:
                existing = await coll.find_one(
                    {
                        "farmId": tenant_farm_id,
                        "conversationId": conversation_id,
                        "idempotencyKey": idempotency_key,
                    },
                    projection={"_id": 1},
                )
            except Exception:  # noqa: BLE001
                existing = None
            if existing is not None:
                return str(existing.get("_id"))
        logger.warning("mongo insert failed (non-fatal): %s", exc)
        return None


async def append_observation(
    *,
    observation_id: str,
    user_id: str,
    farm_id: int,
    conversation_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """幂等追加 MemoryObservation 事件，不写入长期事实。"""
    coll = get_observation_collection()
    if coll is None:
        return _unavailable_result("append_observation")
    indexes = await ensure_observation_indexes()
    if indexes.get("status") == "unavailable":
        return indexes
    tenant_filter = {
        "userId": user_id,
        "farmId": farm_id,
        "conversationId": conversation_id,
        "observationId": observation_id,
    }
    try:
        existing = await coll.find_one(tenant_filter)
        if existing is not None:
            return {
                "ok": True,
                "status": "idempotent",
                "source_status": "mongo",
                "observation_id": observation_id,
            }
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        document = {
            **tenant_filter,
            "createdAt": now,
            **payload,
        }
        result = await coll.insert_one(document)
        return {
            "ok": True,
            "status": "ready",
            "source_status": "mongo",
            "observation_id": observation_id,
            "document_id": str(result.inserted_id),
        }
    except Exception as exc:  # noqa: BLE001
        try:
            existing = await coll.find_one(tenant_filter)
        except Exception:  # noqa: BLE001
            existing = None
        if existing is not None:
            return {
                "ok": True,
                "status": "idempotent",
                "source_status": "mongo",
                "observation_id": observation_id,
            }
        return _unavailable_result("append_observation", exc)


async def load_recent(
    conversation_id: str,
    limit: int = 20,
    *,
    user_id: str | None = None,
    farm_id: int | None = None,
    reset_at: str | None = None,
    strict: bool = False,
) -> list[dict[str, Any]]:
    """Return recent N messages for a conversation, oldest first."""
    coll = get_collection()
    if coll is None:
        if strict:
            raise RuntimeError("conversation_messages_unavailable")
        return []
    await ensure_indexes()
    try:
        filter_doc: dict[str, Any] = {"conversationId": conversation_id}
        if farm_id is not None:
            filter_doc["farmId"] = farm_id
        if user_id:
            filter_doc["userId"] = user_id
        if reset_at:
            filter_doc["createdAt"] = {"$gt": reset_at}
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
                "message_id": str(d.get("_id")) if d.get("_id") is not None else None,
                "createdAt": d.get("createdAt"),
                "turn_id": d.get("turnId"),
                "trace_id": d.get("traceId"),
                "message_kind": d.get("messageKind"),
            }
            for d in docs
        ]
    except Exception as exc:
        logger.warning("mongo load_recent failed (non-fatal): %s", exc)
        if strict:
            raise RuntimeError("conversation_messages_unavailable") from exc
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
    global _state_collection, _state_indexes_initialized
    if _client is not None:
        _client.close()
    _client = None
    _collection = None
    _indexes_initialized = False
    _state_collection = None
    _state_indexes_initialized = False


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
                "message_kind": _normalize_message_kind(d.get("messageKind")),
                "meta": _sanitize_message_meta(d.get("meta")),
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


async def get_conversation_messages(
    conversation_id: str,
    *,
    limit: int = 100,
    cursor: str | None = None,
    snapshot_revision: int = 0,
    user_id: str | None = None,
    farm_id: int | None = None,
) -> dict[str, Any]:
    """读取最新消息页或按签名 cursor 向更早历史分页。"""
    coll = get_collection()
    if coll is None:
        return {
            "conversation_id": conversation_id,
            "items": [],
            "message_count": 0,
            "page_count": 0,
            "has_more": False,
            "next_cursor": None,
            "source_status": "unavailable",
        }
    await ensure_indexes()

    tenant_farm_id = farm_id if farm_id is not None else _DEFAULT_FARM_ID
    filter_doc: dict[str, Any] = {
        "conversationId": conversation_id,
        "farmId": tenant_farm_id,
    }
    if user_id:
        filter_doc["userId"] = user_id

    if cursor:
        anchor = _decode_conversation_cursor(
            cursor,
            conversation_id=conversation_id,
            user_id=user_id,
            farm_id=farm_id,
            snapshot_revision=snapshot_revision,
        )
        anchor_id = str(anchor["message_id"])
        anchor_id_value: Any = (
            ObjectId(anchor_id) if ObjectId.is_valid(anchor_id) else anchor_id
        )
        filter_doc["$or"] = [
            {"createdAt": {"$lt": anchor["created_at"]}},
            {"createdAt": anchor["created_at"], "_id": {"$lt": anchor_id_value}},
        ]

    try:
        query = (
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
            .sort([("createdAt", -1), ("_id", -1)])
            .limit(limit + 1)
        )
        docs = await query.to_list(length=limit + 1)
        has_more = len(docs) > limit
        docs = docs[:limit]
        docs.reverse()
        items = [
            {
                "role": document["role"],
                "content": document["content"],
                "created_at": document.get("createdAt"),
                "message_id": (
                    str(document.get("_id"))
                    if document.get("_id") is not None
                    else None
                ),
                "turn_id": document.get("turnId"),
                "trace_id": document.get("traceId"),
                "message_kind": _normalize_message_kind(document.get("messageKind")),
                "meta": _sanitize_message_meta(document.get("meta")),
            }
            for document in docs
        ]
        if hasattr(coll, "count_documents"):
            message_count = await coll.count_documents(
                {
                    "conversationId": conversation_id,
                    "farmId": tenant_farm_id,
                    **({"userId": user_id} if user_id else {}),
                }
            )
        else:
            message_count = len(items)

        next_cursor = None
        if has_more and items:
            oldest = items[0]
            next_cursor = _encode_conversation_cursor(
                {
                    "v": _CURSOR_VERSION,
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "farm_id": tenant_farm_id,
                    "direction": "older",
                    "snapshot_revision": snapshot_revision,
                    "anchor": {
                        "created_at": oldest["created_at"],
                        "message_id": oldest["message_id"],
                    },
                }
            )
        return {
            "conversation_id": conversation_id,
            "items": items,
            "message_count": message_count,
            "page_count": len(items),
            "has_more": has_more,
            "next_cursor": next_cursor,
            "latest_message_id": items[-1]["message_id"] if items else None,
            "pagination": {
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_count": len(items),
                "limit": limit,
                "direction": "older",
                "snapshot_revision": snapshot_revision,
                "consistency": "snapshot",
            },
            "source_status": "mongo",
        }
    except ConversationCursorError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_conversation_messages failed: %s", exc)
        return {
            "conversation_id": conversation_id,
            "items": [],
            "message_count": 0,
            "page_count": 0,
            "has_more": False,
            "next_cursor": None,
            "source_status": "error",
            "code": "conversation_messages_unavailable",
        }
