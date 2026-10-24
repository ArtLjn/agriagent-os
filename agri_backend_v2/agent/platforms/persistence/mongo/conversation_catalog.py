"""会话目录与生命周期：按租户归档、恢复、删除，独立于消息和摘要版本。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pymongo.errors import DuplicateKeyError

from agent.platforms.persistence.mongo.conversation_state import _state_filter

DELETED = "deleted"


class ConversationLifecycleError(RuntimeError):
    """目录操作的可公开错误，不向客户端泄露存储细节。"""

    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


async def require_access(
    conversation_id: str, *, user_id: str, farm_id: int, writable: bool = False
) -> None:
    """删除的会话不能通过旧链接读取或继续写入，归档会话须先恢复再聊天。"""
    from agent.platforms.persistence.mongo import chat_store

    collection = chat_store.get_state_collection()
    if collection is None:
        raise ConversationLifecycleError(
            "conversation_storage_unavailable", "会话存储暂不可用", 503
        )
    try:
        state = await collection.find_one(
            _state_filter(conversation_id, user_id=user_id, farm_id=farm_id)
        )
    except Exception as exc:
        raise ConversationLifecycleError(
            "conversation_storage_unavailable", "会话状态暂不可用", 503
        ) from exc
    if state and state.get("lifecycle") == DELETED:
        raise ConversationLifecycleError(
            "conversation_not_found", "会话不存在或已删除", 404
        )
    if writable and state and state.get("archived"):
        raise ConversationLifecycleError(
            "conversation_archived", "请先从草稿箱恢复会话", 409
        )


async def change_lifecycle(
    conversation_id: str,
    *,
    user_id: str,
    farm_id: int,
    archived: bool | None = None,
    delete: bool = False,
) -> dict:
    """仅在当前租户内变更目录；删除留存不可恢复标记，避免迟到写入使会话复活。"""
    from agent.platforms.persistence.mongo import chat_store

    messages = chat_store.get_collection()
    states = chat_store.get_state_collection()
    if messages is None or states is None:
        raise ConversationLifecycleError(
            "conversation_storage_unavailable", "会话存储暂不可用", 503
        )
    scope = _state_filter(conversation_id, user_id=user_id, farm_id=farm_id)
    try:
        indexes = await chat_store.ensure_state_indexes()
        if not indexes.get("ok"):
            raise ConversationLifecycleError(
                "conversation_storage_unavailable", "会话状态暂不可用", 503
            )
        state = await states.find_one(scope)
        if state and state.get("lifecycle") == DELETED:
            if delete:
                return {"conversation_id": conversation_id, "deleted": True}
            raise ConversationLifecycleError(
                "conversation_not_found", "会话不存在或已删除", 404
            )
        if not await messages.find_one(scope, {"_id": 1}):
            raise ConversationLifecycleError(
                "conversation_not_found", "会话不存在或已删除", 404
            )
        if delete and not (state or {}).get("archived"):
            raise ConversationLifecycleError(
                "conversation_not_archived", "请先归档会话再删除", 409
            )
        # 先初始化独立目录字段；保留运行态已有 revision，不能覆盖摘要或消息版本。
        if state is None:
            try:
                await states.update_one(scope, {"$setOnInsert": scope}, upsert=True)
            except DuplicateKeyError:
                pass
        condition = {**scope, "lifecycle": {"$ne": DELETED}}
        if delete:
            condition["archived"] = True
        now = datetime.now(UTC).isoformat()
        update = (
            {"lifecycle": DELETED, "deletedAt": now}
            if delete
            else {"archived": archived, "archivedAt": now if archived else None}
        )
        result = await states.update_one(condition, {"$set": update})
        if result.matched_count != 1:
            raise ConversationLifecycleError(
                "conversation_state_changed", "会话状态已变化，请刷新后重试", 409
            )
        return {
            "conversation_id": conversation_id,
            **({"deleted": True} if delete else {"archived": archived}),
        }
    except ConversationLifecycleError:
        raise
    except Exception as exc:
        raise ConversationLifecycleError(
            "conversation_storage_unavailable", "会话操作失败，请稍后重试", 503
        ) from exc


async def list_conversations(
    limit: int = 20,
    cursor: str | None = None,
    *,
    user_id: str | None = None,
    farm_id: int | None = None,
    archived: bool = False,
) -> dict[str, Any]:
    """按当前用户和农场聚合目录，先过滤归档/删除状态再应用分页边界。"""
    from agent.platforms.persistence.mongo import chat_store

    coll = chat_store.get_collection()
    if coll is None:
        raise ConversationLifecycleError(
            "conversation_storage_unavailable", "会话存储暂不可用", 503
        )

    # 目录沿用消息时间排序，归档不修改历史消息时间。
    match: dict[str, Any] = {
        "farmId": farm_id if farm_id is not None else chat_store._DEFAULT_FARM_ID
    }
    if user_id:
        match["userId"] = user_id
    pipeline: list[dict[str, Any]] = [
        {"$match": match},
        {"$sort": {"createdAt": 1, "_id": 1}},
        {
            "$group": {
                "_id": "$conversationId",
                "last_msg": {"$last": "$content"},
                "last_role": {"$last": "$role"},
                "last_at": {"$last": "$createdAt"},
                "message_count": {"$sum": 1},
            }
        },
        {
            "$lookup": {
                "from": chat_store._state_collection_name(),
                "let": {"conversation": "$_id"},
                "pipeline": [
                    {
                        "$match": {
                            **match,
                            "$expr": {"$eq": ["$conversationId", "$$conversation"]},
                        }
                    }
                ],
                "as": "catalog",
            }
        },
        {
            "$match": {
                "catalog.lifecycle": {"$ne": DELETED},
                "catalog.archived": True if archived else {"$ne": True},
            }
        },
        {"$sort": {"last_at": -1, "_id": -1}},
    ]

    try:
        if cursor:
            # 游标代表排序边界，单纯排除该 ID 会把之前的会话反复返回。
            anchor = await coll.find_one(
                {**match, "conversationId": cursor},
                sort=[("createdAt", -1), ("_id", -1)],
            )
            if anchor is None:
                return {"items": [], "next_cursor": None, "has_more": False}
            pipeline.append(
                {
                    "$match": {
                        "$or": [
                            {"last_at": {"$lt": anchor["createdAt"]}},
                            {"last_at": anchor["createdAt"], "_id": {"$lt": cursor}},
                        ]
                    }
                }
            )
        pipeline.append({"$limit": limit + 1})
        results = await coll.aggregate(pipeline).to_list(length=limit + 1)
    except Exception as exc:
        raise ConversationLifecycleError(
            "conversation_storage_unavailable", "加载会话失败，请稍后重试", 503
        ) from exc

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
                "archived": archived,
            }
        )

    next_cursor = items[-1]["conversation_id"] if has_more and items else None
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}
