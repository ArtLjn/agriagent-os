"""Long-term Memory 的检索与 observation 端口。

当前阶段只持久化受控 observation，不自动抽取或写入长期事实；事实写入和
检索实现将在后续 Memory data governance 阶段接入。
"""

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
    """长期记忆检索端口；当前阶段明确返回空结果。"""
    del user_id, farm_id, query, scope, dependencies
    return []


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
