"""Session View 和 Short Memory 的 Mongo 投影实现。"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from agent.domains.harness.memory.models import SessionView

logger = logging.getLogger(__name__)
# 防止排队消息挤占完整轮次，同时为失败摘要保留有界的原文回退。
SESSION_HISTORY_MESSAGE_LIMIT = 2000
# 原话工作集独立于完整对话窗口与摘要；保留最近十二轮中的用户陈述供预算边界选取。
SESSION_USER_EVIDENCE_TURN_LIMIT = 12


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
        "recent_user_statements": [],
        "summary": None,
        "summary_revision": 0,
        "summary_status": "empty",
        "summary_source_from_message_id": None,
        "summary_source_to_message_id": None,
        "summary_source_conversation_revision": None,
        "summary_content_hash": None,
        "conversation_revision": 0,
        "reset_generation": 0,
        "reset_at": None,
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

        state = state or {}
        keep = settings.context.recent_turn_limit
        limit = max(keep + 1, SESSION_USER_EVIDENCE_TURN_LIMIT) * 2 + 1
        while True:
            recent = await chat_store.load_recent(
                conversation_id,
                limit=limit,
                user_id=user_id,
                farm_id=farm_id,
                reset_at=state.get("reset_at"),
                strict=True,
            )
            turns = complete_turns(recent)
            watermark = state.get("summary_source_to_message_id")
            covered = (
                watermark
                and recent
                and recent[0].get("message_id")
                and recent[0]["message_id"] <= watermark
            )
            if (
                (len(turns) >= keep and covered)
                or len(recent) < limit
                or limit >= SESSION_HISTORY_MESSAGE_LIMIT
            ):
                break
            limit = min(limit * 2, SESSION_HISTORY_MESSAGE_LIMIT)
        # 历史退出窗口前先更新摘要；短消息不会触发 token 水位，因此不能只依赖压缩。
        if len(turns) > keep:
            from agent.domains.harness.context import summarizer

            result = await summarizer.maybe_summarize_async(
                conversation_id,
                user_id=user_id,
                farm_id=farm_id,
                source_conversation_revision=int(state.get("conversation_revision", 0)),
            )
            refreshed = await chat_store.get_conversation_state(
                conversation_id, user_id=user_id, farm_id=farm_id
            )
            if refreshed and refreshed.get("status") == "unavailable":
                raise RuntimeError("conversation_state_unavailable")
            # reset 与摘要竞争时，不能把旧代次读到的消息交给新请求。
            if (refreshed or {}).get("reset_generation", 0) != state.get(
                "reset_generation", 0
            ):
                raise RuntimeError("conversation_reset_during_memory_read")
            state = refreshed or state
            if result.status not in {"ready", "idempotent"}:
                logger.warning(
                    "session summary refresh incomplete code=%s conversation=%s",
                    result.error_code or result.status,
                    conversation_id,
                )
        summary_status = state.get("summary_status", "empty")
        watermark = state.get("summary_source_to_message_id")
        # 摘要失败时保留本次读取中未被摘要覆盖的原文，避免静默丢失刚滑出的轮次。
        old_turns = turns[:-keep]
        uncovered = [
            item
            for item in old_turns
            if not watermark
            or not item[-1].get("message_id")
            or item[-1]["message_id"] > watermark
        ]
        view: SessionView = {
            **empty_session_view(
                conversation_id,
                user_id=user_id,
                farm_id=farm_id,
                source_status="mongo",
            ),
            "messages": [
                message for item in uncovered + turns[-keep:] for message in item
            ],
            # 最新一问一答由 latest_exchange 保留；这里只读更早原话，不引用助手推测。
            "recent_user_statements": [
                message["content"]
                for item in turns[-SESSION_USER_EVIDENCE_TURN_LIMIT:-1]
                for message in item
                if message.get("role") == "user"
            ],
            "summary": state.get("summary"),
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
            "reset_at": state.get("reset_at"),
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
        # 同一轮可能多次审批；相同原始载荷重试幂等，状态转换必须另行写入。
        "idempotency_key": "turn:{}:session-state:{}".format(
            turn_id,
            hashlib.sha256(
                json.dumps(
                    [pending_action, task_state],
                    sort_keys=True,
                    ensure_ascii=False,
                    default=str,
                ).encode()
            ).hexdigest(),
        ),
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
    pending: dict[str, dict[str, Any]] = {}
    for message in messages:
        # 无 turn_id 的历史数据只在无 ID 消息间配对，不能污染有 ID 的新请求。
        turn_id = str(message.get("turn_id") or "")
        if message.get("role") == "user":
            pending[turn_id] = message
        elif message.get("role") == "assistant" and turn_id in pending:
            turns.append([pending.pop(turn_id), message])
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
