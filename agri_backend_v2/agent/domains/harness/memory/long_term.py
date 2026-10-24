"""长期记忆检索、个性化投影与 observation 端口。"""

from __future__ import annotations

from typing import Any

from agent.domains.harness.memory.models import MemorySearchResult


async def search(
    *,
    user_id: str,
    farm_id: int,
    query: str = "",
    scope: str = "farm",
    dependencies: list[str] | None = None,
) -> MemorySearchResult:
    """兼容旧调用方的全局个人记忆检索端口。"""
    from agent.domains.harness.memory.personalization import visible_memories
    from agent.platforms.persistence.mongo import personalization_store

    # 旧入口没有可信 farm_uid，只允许全局个人记录，不能把旧数字 ID 视作授权。
    document = await personalization_store.load(user_id)
    if not document["settings"]["use_saved_memories"]:
        return []
    return [
        record
        for record in visible_memories(document, "")
        if record["scope"] == "user" and record["status"] == "active"
    ]


async def observe(
    *,
    user_id: str,
    farm_id: int,
    conversation_id: str,
    turn_id: str,
    user_input: str,
    assistant_answer: str,
    metadata: dict[str, Any] | None = None,
    conversation_revision: int = 0,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """幂等保存受控 observation 事件，但不把它升级为长期事实。"""
    from agent.config import settings

    if not settings.mongodb.enabled:
        return {
            "accepted": False,
            "persisted": False,
            "status": "unavailable",
            "source_status": "unavailable",
            "code": "memory_observation_unavailable",
        }

    from agent.platforms.persistence.mongo import chat_store

    observation_id = idempotency_key or f"turn:{turn_id}:memory-observation"
    result = await chat_store.append_observation(
        observation_id=observation_id,
        user_id=user_id,
        farm_id=farm_id,
        conversation_id=conversation_id,
        payload={
            "turnId": turn_id,
            "conversationRevision": conversation_revision,
            "scope": "conversation",
            "status": "pending",
            "sourceStatus": "mongo",
            "userInputSummary": user_input[:500],
            "assistantResponseSummary": assistant_answer[:500],
            "metadata": metadata or {},
        },
    )
    return {
        "accepted": False,
        "persisted": result.get("status") in {"ready", "idempotent"},
        "status": result.get("status", "unavailable"),
        "source_status": result.get("source_status", "unavailable"),
        "observation_id": observation_id,
        "code": result.get("code"),
    }


__all__ = ["observe", "search"]


async def get_personalization_context(
    *, user_id: str, farm_uid: str, query: str = "", temporary: bool = False
) -> dict:
    """隔离持久化边界，存储故障返回空投影供主对话继续执行。"""
    import asyncio
    import logging

    from agent.config import memory_runtime
    from agent.domains.harness.memory.personalization import MemoryError, context_text
    from agent.platforms.persistence.mongo import personalization_store

    if temporary:
        return {}
    try:
        async with asyncio.timeout(memory_runtime.context_timeout):
            doc = await personalization_store.load(
                user_id, query=query, farm_uid=farm_uid
            )
            from agent.platforms.persistence.memory_index import retrieve

            ids = (
                await retrieve(doc, farm_uid, query)
                if doc["settings"]["use_saved_memories"]
                else []
            )
            # 远程检索期间可能发生删除；以返回后重新读取的版本为准。
            control = await personalization_store.load(user_id, memory_ids=[])
            if control["revision"] != doc["revision"]:
                doc = await personalization_store.load(
                    user_id, query=query, farm_uid=farm_uid
                )
                ids = []
            if ids:
                extra = await personalization_store.load(user_id, memory_ids=ids)
                if extra["revision"] != doc["revision"]:
                    doc = await personalization_store.load(
                        user_id, query=query, farm_uid=farm_uid
                    )
                else:
                    known = {m["memory_id"] for m in doc["memories"]}
                    doc["memories"].extend(
                        m for m in extra["memories"] if m["memory_id"] not in known
                    )
            return {
                "personalization": context_text(doc, farm_uid, query, ids),
                "personalization_revision": doc["revision"],
            }
    except (MemoryError, RuntimeError, TimeoutError) as exc:
        logging.getLogger(__name__).warning(
            "personalization unavailable code=%s",
            getattr(exc, "code", "memory_runtime_unavailable"),
        )
        return {}
