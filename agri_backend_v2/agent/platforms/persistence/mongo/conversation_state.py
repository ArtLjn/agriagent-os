"""会话状态的租户隔离、版本写入、重置和摘要租约；连接由 chat_store 管理。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)
_UNSET = object()
# 必须大于摘要模型调用的超时；Worker 崩溃后其他进程可接管，旧持有者不能提交。
SUMMARY_LEASE_SECONDS = 60


def _state_filter(
    conversation_id: str,
    *,
    user_id: str,
    farm_id: int | None,
) -> dict[str, Any]:
    """构造不可绕过租户边界的 state 查询条件。"""
    from agent.platforms.persistence.mongo.chat_store import _DEFAULT_FARM_ID

    return {
        "userId": user_id,
        "farmId": farm_id if farm_id is not None else _DEFAULT_FARM_ID,
        "conversationId": conversation_id,
    }


def _unavailable_result(operation: str, exc: Exception | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "status": "unavailable",
        "source_status": "unavailable",
        "code": "conversation_state_unavailable",
        "operation": operation,
    }
    if exc is not None:
        result["message"] = str(exc)
    return result


def _state_result(document: dict[str, Any], *, status: str = "ready") -> dict[str, Any]:
    """将 Mongo camelCase 文档转换为 Memory Service 使用的稳定 snake_case 契约。"""
    return {
        "ok": True,
        "status": status,
        "source_status": "mongo",
        "conversation_id": document.get("conversationId"),
        "user_id": document.get("userId", ""),
        "farm_uid": document.get("farmUid", ""),
        "farm_id": document.get("farmId"),
        "conversation_revision": int(document.get("conversationRevision", 0) or 0),
        "summary_revision": int(document.get("summaryRevision", 0) or 0),
        "reset_generation": int(document.get("resetGeneration", 0) or 0),
        "reset_at": document.get("resetAt"),
        "summary_lease": document.get("summaryLease"),
        "summary_commit_key": document.get("summaryCommitKey"),
        "summary_commit_token": document.get("summaryCommitToken"),
        "summary": document.get("summary"),
        "summary_status": document.get("summaryStatus", "ready"),
        "summary_source_from_message_id": document.get("summarySourceFromMessageId"),
        "summary_source_to_message_id": document.get("summarySourceToMessageId"),
        "summary_source_conversation_revision": document.get(
            "summarySourceConversationRevision"
        ),
        "summary_content_hash": document.get("summaryContentHash"),
        "summary_generated_by": document.get("summaryGeneratedBy"),
        "summary_created_at": document.get("summaryCreatedAt"),
        "summary_expires_at": document.get("summaryExpiresAt"),
        "pending_action": document.get("pendingAction"),
        "task_state": document.get("taskState"),
        "updated_at": document.get("updatedAt"),
        "last_write_key": document.get("lastWriteKey"),
    }


def _result_attr(result: Any, name: str, default: Any = None) -> Any:
    """兼容 Motor 返回对象和测试 fake 返回字典。"""
    if isinstance(result, dict):
        return result.get(name, default)
    return getattr(result, name, default)


def _is_expired(value: Any, *, now: datetime | None = None) -> bool:
    """只把可解析且已到期的生命周期字段视为过期。"""
    if not value:
        return False
    if isinstance(value, datetime):
        expires_at = value
    elif isinstance(value, str):
        try:
            expires_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
    else:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return expires_at <= current


def _expired_state_fields(
    document: dict[str, Any], *, now: datetime | None = None
) -> tuple[bool, bool]:
    """返回 pending action 与临时任务各自是否需要清理。"""
    pending = document.get("pendingAction") or {}
    task = document.get("taskState") or {}
    return (
        pending.get("status") in {"expired", "approved", "rejected", "cancelled"}
        or _is_expired(pending.get("expires_at"), now=now),
        task.get("status") in {"expired", "completed", "failed", "cancelled"}
        or _is_expired(task.get("expires_at"), now=now),
    )


async def get_conversation_state(
    conversation_id: str,
    *,
    user_id: str,
    farm_id: int | None = None,
    cleanup_expired: bool = True,
) -> dict[str, Any] | None:
    """读取租户范围内的 Conversation state。

    返回 `None` 表示该租户下尚未创建 state；返回结构化 `unavailable` 表示
    Mongo 边界不可用。两者不能混淆，调用方不得把 unavailable 当成空状态。
    """
    from agent.platforms.persistence.mongo import chat_store as store

    coll = store.get_state_collection()
    if coll is None:
        return _unavailable_result("get_conversation_state")
    indexes = await store.ensure_state_indexes()
    if indexes.get("status") == "unavailable":
        return indexes
    try:
        document = await coll.find_one(
            _state_filter(conversation_id, user_id=user_id, farm_id=farm_id)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("conversation state read failed: %s", exc)
        return _unavailable_result("get_conversation_state", exc)
    if document is None:
        return None
    state = _state_result(document)
    if not cleanup_expired:
        return state
    pending_expired, task_expired = _expired_state_fields(document)
    if not pending_expired and not task_expired:
        return state
    cleaned = await clear_expired_session_state(
        conversation_id,
        user_id=user_id,
        farm_id=farm_id,
        expected_revision=state["conversation_revision"],
        clear_pending_action=pending_expired,
        clear_task_state=task_expired,
    )
    if cleaned.get("status") in {"ready", "idempotent"}:
        return cleaned
    # 清理与其他写入竞争时，不把已过期数据重新暴露给 Context。
    return {
        **state,
        "status": "stale",
        "pending_action": None if pending_expired else state.get("pending_action"),
        "task_state": None if task_expired else state.get("task_state"),
    }


async def save_conversation_state(
    conversation_id: str,
    *,
    user_id: str,
    farm_id: int | None = None,
    farm_uid: str | None = None,
    expected_revision: int = 0,
    summary: str | None | object = _UNSET,
    summary_status: str | object = _UNSET,
    summary_revision: int | object = _UNSET,
    summary_source_from_message_id: str | None | object = _UNSET,
    summary_source_to_message_id: str | None | object = _UNSET,
    summary_source_conversation_revision: int | None | object = _UNSET,
    summary_content_hash: str | None | object = _UNSET,
    summary_generated_by: str | None | object = _UNSET,
    summary_created_at: str | None | object = _UNSET,
    summary_expires_at: str | None | object = _UNSET,
    pending_action: dict[str, Any] | None | object = _UNSET,
    task_state: dict[str, Any] | None | object = _UNSET,
    reset_generation: int | object = _UNSET,
    reset_at: str | None | object = _UNSET,
    summary_lease: dict | None | object = _UNSET,
    idempotency_key: str | None = None,
    advance_conversation_revision: bool = True,
) -> dict[str, Any]:
    """以 revision CAS 保存 Conversation state。

    新 state 使用 `expected_revision=0` 创建；已有 state 必须传入读取时的
    `conversation_revision`。相同 `idempotency_key` 的重试返回当前版本，
    不会再次递增 revision。摘要 claim/commit 可关闭 conversation revision
    推进，只推进独立的 summary revision，避免后台压缩阻塞当前 Turn 收尾。
    """
    from agent.platforms.persistence.mongo import chat_store as store

    coll = store.get_state_collection()
    if coll is None:
        return _unavailable_result("save_conversation_state")
    indexes = await store.ensure_state_indexes()
    if indexes.get("status") == "unavailable":
        return indexes

    tenant_filter = _state_filter(conversation_id, user_id=user_id, farm_id=farm_id)
    try:
        current = await coll.find_one(tenant_filter)
        if current is not None and idempotency_key:
            if current.get("lastWriteKey") == idempotency_key:
                return _state_result(current, status="idempotent")
            current_revision = int(current.get("conversationRevision", 0) or 0)
            if current_revision != expected_revision:
                return {
                    "ok": False,
                    "status": "conflict",
                    "source_status": "mongo",
                    "code": "conversation_state_revision_conflict",
                    "expected_revision": expected_revision,
                    "actual_revision": current_revision,
                    "state": _state_result(current),
                }
        elif current is not None:
            current_revision = int(current.get("conversationRevision", 0) or 0)
            if current_revision != expected_revision:
                return {
                    "ok": False,
                    "status": "conflict",
                    "source_status": "mongo",
                    "code": "conversation_state_revision_conflict",
                    "expected_revision": expected_revision,
                    "actual_revision": current_revision,
                    "state": _state_result(current),
                }
        elif expected_revision != 0:
            return {
                "ok": False,
                "status": "conflict",
                "source_status": "mongo",
                "code": "conversation_state_revision_conflict",
                "expected_revision": expected_revision,
                "actual_revision": None,
            }

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        set_doc: dict[str, Any] = {"updatedAt": now}
        if farm_uid is not None:
            set_doc["farmUid"] = farm_uid
        if idempotency_key is not None:
            set_doc["lastWriteKey"] = idempotency_key
        field_values = {
            "summary": summary,
            "summaryStatus": summary_status,
            "summaryRevision": summary_revision,
            "summarySourceFromMessageId": summary_source_from_message_id,
            "summarySourceToMessageId": summary_source_to_message_id,
            "summarySourceConversationRevision": summary_source_conversation_revision,
            "summaryContentHash": summary_content_hash,
            "summaryGeneratedBy": summary_generated_by,
            "summaryCreatedAt": summary_created_at,
            "summaryExpiresAt": summary_expires_at,
            "pendingAction": pending_action,
            "taskState": task_state,
            "resetGeneration": reset_generation,
            "resetAt": reset_at,
            "summaryLease": summary_lease,
        }
        for field_name, value in field_values.items():
            if value is not _UNSET:
                set_doc[field_name] = value
        if reset_at is not _UNSET:
            set_doc.update(summaryCommitKey=None, summaryCommitToken=None)

        base_doc = {
            **tenant_filter,
            "sessionId": conversation_id,
            "conversationRevision": 0,
            "summaryRevision": 0,
            "resetGeneration": 0,
            "summaryStatus": "ready",
            "createdAt": now,
        }
        # Mongo 不允许同一个 upsert 路径同时出现在 `$set` 和
        # `$setOnInsert`。`farmUid` 等可选状态字段必须只由一个 modifier
        # 负责，否则首次 Turn 的消息虽已落库，Conversation state 会因
        # Mongo code 40 失败，最终被错误展示为 finalization incomplete。
        for field_name in set_doc:
            base_doc.pop(field_name, None)
        if advance_conversation_revision:
            base_doc.pop("conversationRevision", None)
        update_doc: dict[str, Any] = {
            "$set": set_doc,
            "$setOnInsert": base_doc,
        }
        if advance_conversation_revision:
            update_doc["$inc"] = {"conversationRevision": 1}
        result = await coll.update_one(
            {**tenant_filter, "conversationRevision": expected_revision},
            update_doc,
            upsert=True,
        )
        matched = int(_result_attr(result, "matched_count", 0) or 0)
        upserted = _result_attr(result, "upserted_id")
        if matched == 0 and upserted is None:
            latest = await coll.find_one(tenant_filter)
            actual = int(latest.get("conversationRevision", 0) or 0) if latest else None
            return {
                "ok": False,
                "status": "conflict",
                "source_status": "mongo",
                "code": "conversation_state_revision_conflict",
                "expected_revision": expected_revision,
                "actual_revision": actual,
            }
        saved = await coll.find_one(tenant_filter)
        if saved is None:
            return _unavailable_result(
                "save_conversation_state",
                RuntimeError("state write acknowledged but document could not be read"),
            )
        return _state_result(saved)
    except Exception as exc:  # noqa: BLE001
        # 并发首次 upsert 可能因唯一索引先抛 DuplicateKeyError；重新读取后
        # 将它归类为 CAS 冲突，而不是把已存在的新版本误报为存储不可用。
        try:
            latest = await coll.find_one(tenant_filter)
        except Exception:  # noqa: BLE001
            latest = None
        if latest is not None:
            actual = int(latest.get("conversationRevision", 0) or 0)
            if actual != expected_revision:
                return {
                    "ok": False,
                    "status": "conflict",
                    "source_status": "mongo",
                    "code": "conversation_state_revision_conflict",
                    "expected_revision": expected_revision,
                    "actual_revision": actual,
                }
        logger.warning("conversation state write failed: %s", exc)
        return _unavailable_result("save_conversation_state", exc)


async def clear_expired_session_state(
    conversation_id: str,
    *,
    user_id: str,
    farm_id: int | None,
    expected_revision: int,
    clear_pending_action: bool,
    clear_task_state: bool,
) -> dict[str, Any]:
    """以 CAS 清理已过期的 Session 短时状态。"""
    if not clear_pending_action and not clear_task_state:
        return await get_conversation_state(
            conversation_id,
            user_id=user_id,
            farm_id=farm_id,
            cleanup_expired=False,
        ) or _unavailable_result("clear_expired_session_state")
    return await save_conversation_state(
        conversation_id,
        user_id=user_id,
        farm_id=farm_id,
        expected_revision=expected_revision,
        pending_action=None if clear_pending_action else _UNSET,
        task_state=None if clear_task_state else _UNSET,
        idempotency_key=f"expiry:{conversation_id}:{expected_revision}",
    )


async def reset_conversation_state(
    conversation_id: str,
    *,
    user_id: str,
    farm_id: int | None = None,
    expected_revision: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """清理 active state 并递增 reset generation，保留 conversationMessages。"""
    current = await get_conversation_state(
        conversation_id, user_id=user_id, farm_id=farm_id
    )
    if current and current.get("status") == "unavailable":
        return current
    revision = int(current.get("conversation_revision", 0) or 0) if current else 0
    if expected_revision is not None and expected_revision != revision:
        return {
            "ok": False,
            "status": "conflict",
            "source_status": "mongo",
            "code": "conversation_state_revision_conflict",
            "expected_revision": expected_revision,
            "actual_revision": revision,
        }
    return await save_conversation_state(
        conversation_id,
        user_id=user_id,
        farm_id=farm_id,
        farm_uid=(current or {}).get("farm_uid"),
        expected_revision=revision,
        summary=None,
        summary_status="stale",
        summary_revision=int((current or {}).get("summary_revision", 0) or 0) + 1,
        summary_source_from_message_id=None,
        summary_source_to_message_id=None,
        summary_source_conversation_revision=None,
        summary_content_hash=None,
        summary_generated_by=None,
        summary_created_at=None,
        summary_expires_at=None,
        pending_action=None,
        task_state=None,
        reset_generation=int((current or {}).get("reset_generation", 0) or 0) + 1,
        reset_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        summary_lease=None,
        idempotency_key=idempotency_key,
    )


async def claim_summary_generation(
    conversation_id: str,
    *,
    user_id: str,
    farm_id: int | None,
    source_conversation_revision: int,
    summary_key: str,
    source_summary_revision: int | None = None,
) -> dict[str, Any]:
    """使用独立租约抢占摘要，保留上一份有效摘要及会话写入幂等键。"""
    from agent.platforms.persistence.mongo import chat_store as store

    current = await get_conversation_state(
        conversation_id, user_id=user_id, farm_id=farm_id
    )
    if current and current.get("status") == "unavailable":
        return current
    if current is None:
        current = await save_conversation_state(
            conversation_id,
            user_id=user_id,
            farm_id=farm_id,
            advance_conversation_revision=False,
        )
        if not current.get("ok"):
            return current
    if current.get("conversation_revision") != source_conversation_revision:
        return {
            "ok": False,
            "status": "conflict",
            "source_status": "mongo",
            "code": "summary_source_revision_conflict",
            "actual_revision": current.get("conversation_revision"),
        }
    if (
        source_summary_revision is not None
        and current.get("summary_revision", 0) != source_summary_revision
    ):
        return {
            "ok": False,
            "status": "conflict",
            "source_status": "mongo",
            "code": "summary_base_revision_conflict",
        }
    previous_lease = current.get("summary_lease")
    if previous_lease and not _is_expired(previous_lease.get("expires_at")):
        return {
            "ok": False,
            "status": "conflict",
            "source_status": "mongo",
            "code": "summary_generation_in_progress",
            "actual_revision": current.get("conversation_revision"),
        }
    now = datetime.now(timezone.utc)
    lease = {
        "token": uuid4().hex,
        "key": summary_key,
        "source_revision": source_conversation_revision,
        "reset_generation": current.get("reset_generation", 0),
        "expires_at": (now + timedelta(seconds=SUMMARY_LEASE_SECONDS)).isoformat(),
    }
    coll = store.get_state_collection()
    if coll is None:
        return _unavailable_result("claim_summary_generation")
    try:
        # 相同 revision 的两个 Worker 也必须争抢同一个旧租约值，只有一个能成功。
        result = await coll.update_one(
            {
                **_state_filter(conversation_id, user_id=user_id, farm_id=farm_id),
                "conversationRevision": source_conversation_revision,
                "summaryRevision": current.get("summary_revision", 0),
                "summaryLease": previous_lease,
            },
            {"$set": {"summaryLease": lease, "summaryStatus": "generating"}},
            upsert=False,
        )
        if not _result_attr(result, "matched_count", 0):
            return {
                "ok": False,
                "status": "conflict",
                "source_status": "mongo",
                "code": "summary_claim_conflict",
            }
        return {
            **current,
            "status": "ready",
            "summary_status": "generating",
            "summary_lease": lease,
        }
    except Exception as exc:  # noqa: BLE001
        return _unavailable_result("claim_summary_generation", exc)


async def save_summary_result(
    conversation_id: str,
    *,
    user_id: str,
    farm_id: int | None,
    expected_revision: int,
    source_conversation_revision: int,
    summary_key: str,
    lease_token: str,
    summary: str | object = _UNSET,
    status: str,
    source_from_message_id: str | None = None,
    source_to_message_id: str | None = None,
    content_hash: str | None = None,
    generated_by: str | None = None,
    created_at: str | None = None,
    expires_at: str | None = None,
) -> dict[str, Any]:
    """仅租约持有者可提交；正常会话推进不冲突，reset 或超时接管会拦截旧结果。"""
    from agent.platforms.persistence.mongo import chat_store as store

    current = await get_conversation_state(
        conversation_id, user_id=user_id, farm_id=farm_id
    )
    if current and current.get("status") == "unavailable":
        return current
    current = current or {}
    if (
        current.get("summary_commit_key") == summary_key
        and current.get("summary_commit_token") == lease_token
    ):
        return {**current, "status": "idempotent"}
    lease = current.get("summary_lease") or {}
    if (
        not lease_token
        or lease.get("token") != lease_token
        or lease.get("key") != summary_key
        or lease.get("source_revision") != source_conversation_revision
        or expected_revision != source_conversation_revision
        or lease.get("reset_generation") != current.get("reset_generation", 0)
        or _is_expired(lease.get("expires_at"))
    ):
        return {
            "ok": False,
            "status": "conflict",
            "source_status": "mongo",
            "code": "summary_lease_lost",
            "actual_revision": current.get("conversation_revision"),
        }
    fields: dict[str, Any] = {
        "summaryLease": None,
        "summaryStatus": status,
        "summaryCommitKey": summary_key,
        "summaryCommitToken": lease_token,
    }
    if status == "ready":
        fields.update(
            {
                "summary": summary,
                "summarySourceFromMessageId": source_from_message_id,
                "summarySourceToMessageId": source_to_message_id,
                "summarySourceConversationRevision": source_conversation_revision,
                "summaryContentHash": content_hash,
                "summaryGeneratedBy": generated_by,
                "summaryCreatedAt": created_at,
                "summaryExpiresAt": expires_at,
            }
        )
    update: dict[str, Any] = {"$set": fields}
    if status == "ready":
        update["$inc"] = {"summaryRevision": 1}
    coll = store.get_state_collection()
    if coll is None:
        return _unavailable_result("save_summary_result")
    try:
        result = await coll.update_one(
            {
                **_state_filter(conversation_id, user_id=user_id, farm_id=farm_id),
                "summaryLease": lease,
            },
            update,
            upsert=False,
        )
        if not _result_attr(result, "matched_count", 0):
            return {
                "ok": False,
                "status": "conflict",
                "source_status": "mongo",
                "code": "summary_lease_lost",
            }
        return await get_conversation_state(
            conversation_id, user_id=user_id, farm_id=farm_id
        ) or _unavailable_result("save_summary_result")
    except Exception as exc:  # noqa: BLE001
        return _unavailable_result("save_summary_result", exc)
