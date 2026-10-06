"""Session View 和 Short Memory 的 Mongo 投影实现。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from agent.domains.harness.memory.models import SessionView


logger = logging.getLogger(__name__)


def source_divergence(
    session_view: dict[str, Any],
    *,
    redis_conversation_revision: int = 0,
    redis_summary_revision: int = 0,
) -> dict[str, Any] | None:
    """比较已加载 Session View 与 Redis Turn 快照，返回可解释差异。"""
    if session_view.get("source_status") == "divergent":
        return session_view.get("source_divergence") or {
            "code": "context_source_divergence",
            "sources": {"mongo": "divergent"},
        }
    if session_view.get("source_status") == "unavailable":
        return {
            "code": "context_source_unavailable",
            "sources": {"mongo": "unavailable", "redis": "available"},
        }
    mongo_revision = int(session_view.get("conversation_revision", 0) or 0)
    mongo_summary_revision = int(session_view.get("summary_revision", 0) or 0)
    if (
        redis_conversation_revision > 0
        and mongo_revision > 0
        and redis_conversation_revision != mongo_revision
    ):
        return {
            "code": "conversation_revision_divergence",
            "sources": {
                "mongo": {"conversation_revision": mongo_revision},
                "redis": {"conversation_revision": redis_conversation_revision},
            },
        }
    if (
        redis_summary_revision > 0
        and mongo_summary_revision > 0
        and redis_summary_revision != mongo_summary_revision
    ):
        return {
            "code": "summary_revision_divergence",
            "sources": {
                "mongo": {"summary_revision": mongo_summary_revision},
                "redis": {"summary_revision": redis_summary_revision},
            },
        }
    source_revision = session_view.get("summary_source_conversation_revision")
    if source_revision is not None and int(source_revision or 0) > mongo_revision:
        return {
            "code": "summary_source_revision_ahead",
            "sources": {
                "mongo": {
                    "conversation_revision": mongo_revision,
                    "summary_source_conversation_revision": int(source_revision),
                }
            },
        }
    return None


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
) -> SessionView:
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
) -> SessionView:
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
        view: SessionView = {
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
            "summary_source_to_message_id": state.get("summary_source_to_message_id"),
            "summary_source_conversation_revision": state.get(
                "summary_source_conversation_revision"
            ),
            "summary_content_hash": state.get("summary_content_hash"),
            "conversation_revision": int(state.get("conversation_revision", 0) or 0),
            "reset_generation": int(state.get("reset_generation", 0) or 0),
            "pending_action": state.get("pending_action"),
            "task_state": state.get("task_state"),
        }
        divergence = source_divergence(view)
        if divergence:
            view["source_status"] = "divergent"
            view["source_divergence"] = divergence
        return view
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
    # None 具有“清除旧恢复门”的明确语义；否则不同动作恢复后 Mongo 会保留
    # 上一轮的 blocked_action，导致后续 Turn 继续被错误拦截。
    fields["task_state"] = (
        prepare_task_state(task_state, turn_id=turn_id)
        if task_state is not None
        else None
    )
    return await chat_store.save_conversation_state(**fields)


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


__all__ = [
    "complete_turns",
    "empty_session_view",
    "get_session_view",
    "persist_session_turn",
    "prepare_pending_action",
    "prepare_task_state",
    "project_recent_turns",
    "reset_session",
    "source_divergence",
]
