"""Memory Service：Mongo-backed Session View 与长期记忆端口。

Conversation 的唯一事实源是 Mongo ``conversationMessages`` 和
``conversationStates``。本模块不提供本地文件 fallback；持久化不可用时必须
返回 ``unavailable``，由 application 层决定当前 Turn 是否继续。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def prepare_pending_action(
    pending_action: dict[str, Any] | None,
    *,
    turn_id: str,
) -> dict[str, Any] | None:
    """为待审批动作补齐 Session 生命周期字段。"""
    if pending_action is None:
        return None
    from agent.config import settings

    now = _utc_now()
    normalized = dict(pending_action)
    normalized.setdefault("status", "pending")
    normalized.setdefault("source_turn_id", turn_id)
    normalized.setdefault("created_at", _isoformat(now))
    normalized.setdefault(
        "expires_at",
        _isoformat(
            now
            + timedelta(
                seconds=settings.context.conversation_state.pending_action_ttl_seconds
            )
        ),
    )
    return normalized


def prepare_task_state(
    task_state: dict[str, Any] | None,
    *,
    turn_id: str,
) -> dict[str, Any] | None:
    """为临时任务补齐状态、来源和过期时间。"""
    if task_state is None:
        return None
    from agent.config import settings

    now = _utc_now()
    normalized = dict(task_state)
    normalized.setdefault("status", "active")
    normalized.setdefault("source_turn_id", turn_id)
    normalized.setdefault("updated_at", _isoformat(now))
    normalized.setdefault(
        "expires_at",
        _isoformat(
            now
            + timedelta(
                seconds=settings.context.conversation_state.task_state_ttl_seconds
            )
        ),
    )
    return normalized


def empty_session_view(
    conversation_id: str,
    *,
    user_id: str = "",
    farm_id: int = 1,
    source_status: str = "empty",
) -> dict[str, Any]:
    """构造不包含历史事实的 Session View。"""
    return {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "farm_id": farm_id,
        "messages": [],
        "summary": None,
        "summary_revision": 0,
        "summary_status": "empty",
        "summary_source_from_message_id": None,
        "summary_source_to_message_id": None,
        "summary_source_conversation_revision": None,
        "summary_content_hash": None,
        "conversation_revision": 0,
        "reset_generation": 0,
        "pending_action": None,
        "task_state": None,
        "source_status": source_status,
        "long_term": {},
    }


async def get_session_view(
    conversation_id: str,
    *,
    user_id: str = "",
    farm_id: int = 1,
) -> dict[str, Any]:
    """读取 Mongo-backed Short Memory projection。"""
    from agent.config import settings

    if not settings.mongodb.enabled:
        return empty_session_view(
            conversation_id,
            user_id=user_id,
            farm_id=farm_id,
            source_status="unavailable",
        )

    from agent.platforms.persistence.mongo import chat_store

    try:
        state = await chat_store.get_conversation_state(
            conversation_id,
            user_id=user_id,
            farm_id=farm_id,
        )
        if state and state.get("status") == "unavailable":
            return empty_session_view(
                conversation_id,
                user_id=user_id,
                farm_id=farm_id,
                source_status="unavailable",
            )

        recent = await chat_store.load_recent(
            conversation_id,
            limit=max(settings.context.recent_turn_limit * 2, 2),
            user_id=user_id,
            farm_id=farm_id,
        )
        state = state or {}
        summary_status = state.get("summary_status", "empty")
        return {
            **empty_session_view(
                conversation_id,
                user_id=user_id,
                farm_id=farm_id,
                source_status="mongo",
            ),
            "messages": project_recent_turns(
                recent, settings.context.recent_turn_limit
            ),
            "summary": state.get("summary") if summary_status == "ready" else None,
            "summary_revision": int(state.get("summary_revision", 0) or 0),
            "summary_status": summary_status,
            "summary_source_from_message_id": state.get(
                "summary_source_from_message_id"
            ),
            "summary_source_to_message_id": state.get(
                "summary_source_to_message_id"
            ),
            "summary_source_conversation_revision": state.get(
                "summary_source_conversation_revision"
            ),
            "summary_content_hash": state.get("summary_content_hash"),
            "conversation_revision": int(
                state.get("conversation_revision", 0) or 0
            ),
            "reset_generation": int(state.get("reset_generation", 0) or 0),
            "pending_action": state.get("pending_action"),
            "task_state": state.get("task_state"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "session view read failed conversation=%s error=%s",
            conversation_id,
            exc,
        )
        return empty_session_view(
            conversation_id,
            user_id=user_id,
            farm_id=farm_id,
            source_status="unavailable",
        )


async def search(
    *,
    user_id: str,
    farm_id: int,
    query: str = "",
    scope: str = "farm",
    dependencies: list[str] | None = None,
) -> list[dict[str, Any]]:
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


async def persist_session_turn(
    *,
    conversation_id: str,
    user_id: str,
    farm_id: int,
    farm_uid: str,
    expected_revision: int,
    turn_id: str,
    pending_action: dict[str, Any] | None = None,
    task_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """在可见消息终态后以 CAS 推进 Conversation state revision。"""
    from agent.platforms.persistence.mongo import chat_store

    fields: dict[str, Any] = {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "farm_id": farm_id,
        "farm_uid": farm_uid,
        "expected_revision": expected_revision,
        "pending_action": prepare_pending_action(pending_action, turn_id=turn_id),
        "idempotency_key": f"turn:{turn_id}:session-state",
    }
    if task_state is not None:
        fields["task_state"] = prepare_task_state(task_state, turn_id=turn_id)
    return await chat_store.save_conversation_state(
        **fields,
    )


async def reset_session(
    conversation_id: str,
    *,
    user_id: str = "",
    farm_id: int = 1,
) -> dict[str, Any]:
    """清除 active Session View；用户可见 Mongo 消息不删除。"""
    from agent.config import settings

    if not settings.mongodb.enabled:
        return {
            "ok": False,
            "status": "unavailable",
            "source_status": "unavailable",
            "code": "conversation_state_unavailable",
            "message": "Mongo conversation state 未启用，无法执行 reset",
        }

    from agent.platforms.persistence.mongo import chat_store

    return await chat_store.reset_conversation_state(
        conversation_id,
        user_id=user_id,
        farm_id=farm_id,
    )


def complete_turns(messages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """将消息投影成已完成的 user/assistant Turn。"""
    turns: list[list[dict[str, Any]]] = []
    pending: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") == "user":
            pending = [message]
        elif message.get("role") == "assistant" and pending:
            pending.append(message)
            turns.append(pending)
            pending = []
    return turns


def project_recent_turns(
    messages: list[dict[str, Any]], recent_turn_limit: int
) -> list[dict[str, Any]]:
    """按完整 Turn 投影最近窗口，而非按单条消息截断。"""
    selected = complete_turns(messages)[-max(1, recent_turn_limit) :]
    return [message for turn in selected for message in turn]
