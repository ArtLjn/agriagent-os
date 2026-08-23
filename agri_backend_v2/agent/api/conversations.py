"""会话端点：GET /api/v2/conversations + GET /api/v2/conversations/{id}。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Header, HTTPException, Query

from agent.api import api_router
from agent.auth import parse_identity
from agent.platforms.persistence.mongo.chat_store import (
    ConversationCursorError,
    get_conversation,
    get_conversation_messages,
    get_conversation_state,
    list_conversations,
)
from agent.platforms.persistence.redis.turn_store import get_turn, legacy_status_fields
from agent.domains.harness.observability.trace.store import (
    get_trace_summary,
    get_trace_timeline,
    list_traces,
)
from agent.domains.harness.observability.trace.safety import sanitize_payload
from shared.roles import is_admin_role

logger = logging.getLogger(__name__)


def _message_ids_by_turn(items: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """按 turn 汇总消息回链，供 Turn 摘要复用而不复制消息正文。"""
    grouped: dict[str, dict[str, str]] = {}
    for item in items:
        turn_id = str(item.get("turn_id") or "")
        message_id = item.get("message_id")
        if not turn_id or not message_id:
            continue
        bucket = grouped.setdefault(turn_id, {})
        kind = str(item.get("message_kind") or "")
        if kind == "prompt" or (item.get("role") == "user" and "prompt" not in bucket):
            bucket["prompt"] = str(message_id)
        elif kind in {"final_answer", "error_answer"} or "answer" not in bucket:
            bucket["answer"] = str(message_id)
    return grouped


def _events_status(evidence_status: Any, *, has_trace: bool) -> str:
    """把 Trace 存储状态收敛为 Turn API 的证据状态枚举。"""
    if not has_trace:
        return "not_available"
    normalized = str(evidence_status or "empty")
    if normalized in {"ok", "available"}:
        return "available"
    if normalized in {"unavailable", "error"}:
        return "error"
    if normalized in {"not_available", "not_configured"}:
        return "not_available"
    return "missing"


def _normalize_turn_snapshot(turn: dict[str, Any] | None) -> dict[str, Any] | None:
    """将 Redis Turn 状态转换为历史详情可直接消费的字段。"""
    if turn is None:
        return None
    result = dict(turn)
    legacy_status_fields(result)
    for name in (
        "step_count",
        "conversation_revision",
        "summary_revision",
        "reset_generation",
    ):
        try:
            result[name] = int(result.get(name, 0) or 0)
        except (TypeError, ValueError):
            result[name] = 0
    return result


def _check_turn_scope(turn: dict[str, Any], identity: dict[str, Any]) -> None:
    """复用 Turn 的用户/农场边界，防止通过会话详情越权读取运行态。"""
    if str(turn.get("user_id", "")) != str(identity["user_id"]):
        raise HTTPException(
            403, {"code": "turn_forbidden", "message": "无权访问该 turn"}
        )
    turn_farm = turn.get("farm_uid") or turn.get("farm_id")
    identity_farm = identity.get("farm_uid") or identity.get("farm_id")
    if str(turn_farm) != str(identity_farm):
        raise HTTPException(
            403, {"code": "turn_forbidden", "message": "无权访问该 turn"}
        )


@api_router.get("/conversations")
async def conversations_list(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """List conversations with pagination."""
    try:
        identity = parse_identity(authorization)
        return await list_conversations(
            limit=limit,
            cursor=cursor,
            user_id=identity["user_id"],
            farm_id=identity["farm_id"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("conversations list failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@api_router.get("/conversations/{conversation_id}")
async def conversation_detail(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    before: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """Get conversation messages."""
    try:
        identity = parse_identity(authorization)
        result = await get_conversation(
            conversation_id,
            limit=limit,
            before=before,
            user_id=identity["user_id"],
            farm_id=identity["farm_id"],
        )
        state = await get_conversation_state(
            conversation_id,
            user_id=identity["user_id"],
            farm_id=identity["farm_id"],
        )
        if not result.get("items") and state is None:
            raise HTTPException(
                404, {"detail": "conversation not found", "code": "not_found"}
            )
        state = state or {}
        source_status = str(
            state.get("source_status") or state.get("context_source_status") or "empty"
        )
        return {
            **result,
            "conversation_revision": int(state.get("conversation_revision", 0) or 0),
            "summary_revision": int(state.get("summary_revision", 0) or 0),
            "reset_generation": int(state.get("reset_generation", 0) or 0),
            "source_status": source_status,
            "context_source_status": source_status,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("conversation detail failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@api_router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """读取最新消息页或使用 cursor 加载更早历史。"""
    try:
        identity = parse_identity(authorization)
        state = await get_conversation_state(
            conversation_id,
            user_id=identity["user_id"],
            farm_id=identity["farm_id"],
        )
        if state and state.get("status") == "unavailable":
            if cursor:
                raise HTTPException(
                    503,
                    {
                        "code": "conversation_state_unavailable",
                        "message": "会话版本暂不可用，无法安全继续分页",
                    },
                )
            snapshot_revision = 0
        else:
            snapshot_revision = int((state or {}).get("conversation_revision", 0) or 0)

        result = await get_conversation_messages(
            conversation_id,
            limit=limit,
            cursor=cursor,
            snapshot_revision=snapshot_revision,
            user_id=identity["user_id"],
            farm_id=identity["farm_id"],
        )
        if not result.get("items") and state is None:
            raise HTTPException(
                404, {"detail": "conversation not found", "code": "not_found"}
            )
        source_status = str(
            (state or {}).get("source_status")
            or (state or {}).get("context_source_status")
            or result.get("source_status")
            or "empty"
        )
        return {
            **result,
            "conversation_revision": snapshot_revision,
            "summary_revision": int((state or {}).get("summary_revision", 0) or 0),
            "reset_generation": int((state or {}).get("reset_generation", 0) or 0),
            "source_status": source_status,
            "context_source_status": source_status,
        }
    except ConversationCursorError as exc:
        raise HTTPException(409, {"code": exc.code, "message": str(exc)}) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("conversation messages failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@api_router.get("/conversations/{conversation_id}/turns")
async def conversation_turns(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """按会话返回 Turn 摘要，并保留消息到 Turn 的稳定回链。"""
    try:
        identity = parse_identity(authorization)
        messages = await get_conversation(
            conversation_id,
            limit=500,
            user_id=identity["user_id"],
            farm_id=identity["farm_id"],
        )
        message_ids = _message_ids_by_turn(messages.get("items", []))
        trace_page = await list_traces(
            conversation_id=conversation_id,
            limit=limit,
            cursor=cursor,
            user_id=identity["user_id"],
            farm_uid=identity["farm_uid"],
        )
        items: list[dict[str, Any]] = []
        seen_turns: set[str] = set()
        for trace in trace_page.get("items", []):
            turn_id = str(trace.get("turn_id") or "")
            if not turn_id:
                continue
            seen_turns.add(turn_id)
            metrics = trace.get("metrics") or {}
            items.append(
                {
                    "turn_id": turn_id,
                    "trace_id": trace.get("trace_id") or trace.get("request_id"),
                    "status": trace.get("status", "unknown"),
                    "stop_reason": trace.get("status_reason"),
                    "step_count": int(metrics.get("step_count", 0) or 0),
                    "message_ids": message_ids.get(turn_id, {}),
                    "business_result": _safe_business_result(
                        trace.get("business_result")
                    ),
                    "approval": None,
                    "error": trace.get("root_error"),
                    "events_status": _events_status(
                        trace_page.get("evidence_status"), has_trace=True
                    ),
                    "started_at": trace.get("started_at"),
                    "finished_at": trace.get("ended_at"),
                }
            )

        # Trace 过期或未持久化时，仍返回消息侧已知的 Turn，不伪造执行成功。
        if not trace_page.get("items"):
            for turn_id, ids in message_ids.items():
                if turn_id in seen_turns:
                    continue
                items.append(
                    {
                        "turn_id": turn_id,
                        "trace_id": None,
                        "status": "unknown",
                        "stop_reason": None,
                        "step_count": 0,
                        "message_ids": ids,
                        "business_result": None,
                        "approval": None,
                        "error": None,
                        "events_status": "not_available",
                        "started_at": None,
                        "finished_at": None,
                    }
                )
        evidence_status = str(trace_page.get("evidence_status") or "empty")
        source_status = "unavailable" if evidence_status == "unavailable" else "mongo"
        return {
            "conversation_id": conversation_id,
            "items": items,
            "pagination": {
                "next_cursor": trace_page.get("next_cursor"),
                "has_more": bool(trace_page.get("has_more")),
                "limit": limit,
                "direction": "older",
            },
            "next_cursor": trace_page.get("next_cursor"),
            "has_more": bool(trace_page.get("has_more")),
            "source_status": source_status,
            "evidence_status": evidence_status,
            "evidence": trace_page.get("evidence"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("conversation turns failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@api_router.get("/conversations/{conversation_id}/turns/{turn_id}")
async def conversation_turn_detail(
    conversation_id: str,
    turn_id: str,
    include_payload: bool = Query(default=False),
    authorization: str | None = Header(default=None),
) -> dict:
    """聚合运行态 Turn、Trace summary 和受控执行时间线。"""
    try:
        identity = parse_identity(authorization)
        runtime_turn = await get_turn(turn_id)
        if runtime_turn is not None:
            _check_turn_scope(runtime_turn, identity)
            if str(runtime_turn.get("conversation_id", "")) != conversation_id:
                raise HTTPException(
                    404, {"code": "turn_not_found", "message": "会话中不存在该 turn"}
                )
        normalized_turn = _normalize_turn_snapshot(runtime_turn)
        messages = await get_conversation(
            conversation_id,
            limit=500,
            user_id=identity["user_id"],
            farm_id=identity["farm_id"],
        )
        turn_messages = [
            item for item in messages.get("items", []) if item.get("turn_id") == turn_id
        ]
        trace_id = (normalized_turn or {}).get("trace_id")
        if not trace_id:
            trace_id = next(
                (
                    item.get("trace_id")
                    for item in turn_messages
                    if item.get("trace_id")
                ),
                None,
            )
        if not trace_id:
            trace_page = await list_traces(
                conversation_id=conversation_id,
                turn_id=turn_id,
                limit=1,
                user_id=identity["user_id"],
                farm_uid=identity["farm_uid"],
            )
            trace_item = next(iter(trace_page.get("items", [])), None)
            trace_id = (trace_item or {}).get("trace_id") or (trace_item or {}).get(
                "request_id"
            )

        payload_requested = include_payload is True
        if payload_requested and not is_admin_role(identity.get("role")):
            raise HTTPException(
                403,
                {
                    "code": "trace_payload_forbidden",
                    "message": "无权查看 Trace payload",
                },
            )
        summary = (
            await get_trace_summary(
                trace_id,
                user_id=identity["user_id"],
                farm_uid=identity["farm_uid"],
            )
            if trace_id
            else None
        )
        timeline = (
            await get_trace_timeline(
                trace_id,
                include_payload=payload_requested,
                user_id=identity["user_id"],
                farm_uid=identity["farm_uid"],
            )
            if trace_id
            else None
        )
        if normalized_turn is None and not turn_messages and summary is None:
            raise HTTPException(
                404, {"code": "turn_not_found", "message": "会话中不存在该 turn"}
            )
        trace_evidence = (timeline or {}).get("evidence", {})
        events_status = _events_status(
            (timeline or {}).get("evidence_status"), has_trace=bool(trace_id)
        )
        evidence = {
            "runtime_turn": "available" if normalized_turn else "not_available",
            "trace_summary": "available" if summary else "missing",
            "trace_nodes": _evidence_component_status(trace_evidence.get("nodes")),
            "trace_events": _evidence_component_status(trace_evidence.get("events")),
            "conversation_messages": "available" if turn_messages else "missing",
        }
        trace_source_status = "unavailable" if events_status == "error" else "mongo"
        return {
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "trace_id": trace_id,
            "status": (normalized_turn or {}).get("status")
            or (summary or {}).get("status")
            or "unknown",
            "stop_reason": (normalized_turn or {}).get("stop_reason")
            or (summary or {}).get("status_reason"),
            "step_count": (normalized_turn or {}).get("step_count", 0),
            "message_ids": _message_ids_by_turn(turn_messages).get(turn_id, {}),
            "business_result": _safe_business_result(
                (normalized_turn or {}).get("committed_result")
                or (summary or {}).get("business_result")
            ),
            "approval": _approval_snapshot(normalized_turn),
            "error": (summary or {}).get("root_error")
            or (normalized_turn or {}).get("error_message"),
            "events_status": events_status,
            "steps": (timeline or {}).get("items", []),
            "summary": summary,
            "evidence": evidence,
            "source_status": trace_source_status,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("conversation turn detail failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


def _evidence_component_status(component: Any) -> str:
    """归一化 Trace timeline 的节点/事件证据状态。"""
    if not isinstance(component, dict):
        return "missing"
    return _events_status(component.get("status"), has_trace=True)


def _safe_business_result(value: Any) -> dict[str, Any] | None:
    """只返回已提交业务结果的脱敏摘要，不把内部响应原文带入历史详情。"""
    if value is None:
        return None
    sanitized = sanitize_payload(value, max_chars=8_000)
    return sanitized if isinstance(sanitized, dict) else {"value": sanitized}


def _approval_snapshot(turn: dict[str, Any] | None) -> dict[str, Any] | None:
    """把 Redis 审批态投影成不含原始参数的公开摘要。"""
    if not turn:
        return None
    pending = turn.get("pending_approval")
    if isinstance(pending, dict):
        result: dict[str, Any] = {"status": "awaiting_approval"}
        if pending.get("tool_name"):
            result["tool_name"] = str(pending["tool_name"])
        if pending.get("risk_level"):
            result["risk_level"] = str(pending["risk_level"])
        return result
    if turn.get("rejected_reason"):
        return {
            "status": "rejected",
            "reason": str(turn["rejected_reason"])[:500],
        }
    if turn.get("approved") is True:
        return {"status": "approved"}
    return None
