"""Trace 收集器 — MongoDB 批量写入。

参考 archive/backend/app/infra/trace_collector.py + trace_dao.py，
适配 agri_backend_v2 的 MongoDB 架构（用 motor 异步写入，不再用 SQLAlchemy）。

trace 文档结构：
  {
    request_id: str,
    conversation_id: str,
    turn_id: str,
    step_index: int,
    node_type: str,         # "llm_call" | "tool_call" | "observation" | ...
    node_name: str,          # model name 或 tool name
    input_data: Any,
    output_data: Any,
    start_time: datetime,
    end_time: datetime,
    duration_ms: int,
    token_usage: dict | None,
    status: str,             # "success" | "error"
    error_message: str | None,
    created_at: datetime,
  }
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from agent.config import settings
from agent.domains.harness.observability.trace.context import (
    current_parent_span_id,
    get_trace,
    get_step_index,
    new_span_id,
)
from agent.domains.harness.observability.trace.safety import (
    safe_token_usage,
    sanitize_payload,
)

logger = logging.getLogger(__name__)

_MAX_TRACE_JSON_LEN = 32_000
_BATCH_SIZE = 20
_FLUSH_INTERVAL = 5.0  # seconds

_queue: deque[dict[str, Any]] = deque(maxlen=2000)
# SSE 事件投影独立于 traceRecords；Mongo 不可用或投影重试时仍保持有界。
_event_queue: deque[dict[str, Any]] = deque(maxlen=5000)
_flush_task: asyncio.Task | None = None
_running = False


def _collection_name() -> str:
    return settings.mongodb.collections.get("trace_records", "traceRecords")


def _summary_collection_name() -> str:
    return settings.mongodb.collections.get(
        "trace_request_summaries", "traceRequestSummaries"
    )


def _event_collection_name() -> str:
    return settings.mongodb.collections.get("trace_events", "traceEvents")


def _get_collection():
    """Lazy-init MongoDB collection for trace records."""
    if not settings.mongodb.enabled:
        return None
    from agent.platforms.persistence.mongo.chat_store import get_collection as _get_chat_collection

    # 复用 chat_store 的 MongoDB 连接（同一个 client + database）。
    chat_coll = _get_chat_collection()
    if chat_coll is None:
        return None
    return chat_coll.database[_collection_name()]


def _get_summary_collection():
    """Lazy-init MongoDB collection for trace request summaries."""
    if not settings.mongodb.enabled:
        return None
    from agent.platforms.persistence.mongo.chat_store import get_collection as _get_chat_collection

    chat_coll = _get_chat_collection()
    if chat_coll is None:
        return None
    return chat_coll.database[_summary_collection_name()]


def _get_event_collection():
    """延迟初始化持久化 SSE 事件集合。"""
    if not settings.mongodb.enabled:
        return None
    from agent.platforms.persistence.mongo.chat_store import get_collection as _get_chat_collection

    chat_coll = _get_chat_collection()
    if chat_coll is None:
        return None
    return chat_coll.database[_event_collection_name()]


def _truncate(value: Any) -> Any:
    """限制 trace 数据体积。"""
    trace_cfg = getattr(settings, "trace", None)
    limit = int(getattr(trace_cfg, "max_payload_chars", _MAX_TRACE_JSON_LEN))
    return sanitize_payload(value, max_chars=limit)


def record(
    node_type: str,
    node_name: str,
    input_data: Any = None,
    output_data: Any = None,
    start_time: float | None = None,
    end_time: float | None = None,
    duration_ms: int | None = None,
    token_usage: dict | None = None,
    error_message: str | None = None,
    status: str | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    span_kind: str = "internal",
    layer: str = "agent",
    phase: str | None = None,
    attempt: int = 1,
    attributes: dict[str, Any] | None = None,
    resource: dict[str, Any] | None = None,
    step_index: int | None = None,
) -> None:
    """记录一条 trace。无上下文时静默跳过。"""
    trace = get_trace()
    if trace is None:
        return

    now = time.time()
    if start_time is None:
        start_time = now
    if end_time is None:
        end_time = now
    if duration_ms is None:
        duration_ms = int((end_time - start_time) * 1000)

    root_span_id = getattr(trace, "root_span_id", None) or "root"
    resolved_span_id = span_id or new_span_id()
    resolved_parent_span_id = parent_span_id
    if resolved_parent_span_id is None and resolved_span_id != root_span_id:
        resolved_parent_span_id = current_parent_span_id()

    trace_data = {
        "schema_version": 2,
        "trace_id": trace.trace_id,
        "request_id": trace.request_id,
        "conversation_id": trace.conversation_id,
        "turn_id": trace.turn_id,
        "user_id": trace.user_id,
        "farm_uid": trace.farm_uid,
        "span_id": resolved_span_id,
        "parent_span_id": resolved_parent_span_id,
        "span_kind": span_kind,
        "layer": layer,
        "step_index": get_step_index() if step_index is None else step_index,
        "phase": phase,
        "attempt": max(1, attempt),
        "node_type": node_type,
        "node_name": node_name,
        "input_data": _truncate(input_data) if input_data is not None else None,
        "output_data": _truncate(output_data) if output_data is not None else None,
        # Trace 节点和 SSE 事件必须共享 UTC 时间基准，否则合并时间线会把
        # 本地无时区时间与 UTC 时间按字面值比较，导致真实执行顺序错乱。
        "start_time": datetime.fromtimestamp(start_time, tz=timezone.utc),
        "end_time": datetime.fromtimestamp(end_time, tz=timezone.utc),
        "duration_ms": duration_ms,
        "token_usage": safe_token_usage(token_usage),
        "status": status or ("error" if error_message else "success"),
        "error_message": error_message,
        "attributes": _truncate(attributes or {}),
        "resource": _truncate(resource or {}),
        "sampling": {
            "level": int(getattr(trace, "sampling_level", 1)),
            "redacted": True,
        },
        "created_at": datetime.now(timezone.utc),
    }
    _queue.append(trace_data)


def record_event(event: dict[str, Any]) -> dict[str, Any]:
    """接收 SSE Trace 事件，不阻断事件发布且不伪造已落库状态。

    当前只把标准化事件放入有限内存缓冲；函数返回时尚未执行 Mongo 写入，
    所以返回值明确标记 ``persisted=False``。调用方不得据此宣称事件已持久化。
    """
    trace = get_trace()
    trace_id = str(event.get("trace_id") or (trace.trace_id if trace else ""))
    event_id = str(event.get("event_id") or "")
    if not trace_id or not event_id:
        missing = "trace_id" if not trace_id else "event_id"
        return {
            "accepted": False,
            "persisted": False,
            "status": f"missing_{missing}",
        }

    record_data = {
        "schema_version": 2,
        "record_kind": "sse_event",
        "trace_id": trace_id,
        "request_id": str(
            event.get("request_id") or (trace.request_id if trace else trace_id)
        ),
        "user_id": str(event.get("user_id") or (trace.user_id if trace else "")),
        "farm_uid": str(event.get("farm_uid") or (trace.farm_uid if trace else "")),
        "conversation_id": str(
            event.get("conversation_id") or (trace.conversation_id if trace else "")
        ),
        "turn_id": str(event.get("turn_id") or (trace.turn_id if trace else "")),
        "span_id": event.get("span_id"),
        "parent_span_id": event.get("parent_span_id"),
        "event_id": event_id,
        "event_name": str(event.get("event_name") or event.get("type") or ""),
        "event_type": str(event.get("type") or ""),
        "seq": int(event.get("seq") or 0),
        "phase": str(event.get("phase") or ""),
        "step_index": int(event.get("step_index") or event.get("step") or 0),
        "terminal": bool(event.get("terminal")),
        "status_before": str(event.get("status_before") or ""),
        "status_after": str(event.get("status_after") or ""),
        "occurred_at": event.get("occurred_at"),
        "data": _truncate(event.get("data") or {}),
        "projection_status": "queued",
        "created_at": datetime.now(timezone.utc),
    }
    queue_was_full = (
        _event_queue.maxlen is not None and len(_event_queue) >= _event_queue.maxlen
    )
    _event_queue.append(record_data)
    if queue_was_full:
        logger.warning(
            "trace event queue full; oldest event evicted: trace_id=%s event_id=%s",
            trace_id,
            event_id,
        )
        return {
            "accepted": True,
            "persisted": False,
            "status": "queued_with_eviction",
            "storage": "traceEvents",
            "dropped": True,
        }
    return {
        "accepted": True,
        "persisted": False,
        "status": "not_yet_persisted",
        "storage": "traceEvents",
    }


async def flush_now() -> int:
    """立即刷新 trace 节点和 SSE 事件，不阻断主链路。"""
    count = 0
    if _queue:
        coll = _get_collection()
        if coll is None:
            _queue.clear()
        else:
            items = list(_queue)
            _queue.clear()
            try:
                result = await coll.insert_many(items, ordered=False)
                count += len(result.inserted_ids)
                logger.debug(
                    "trace records flushed: count=%d", len(result.inserted_ids)
                )
                await _refresh_summaries(items)
            except Exception:
                logger.exception("trace records flush failed (non-fatal)")

    count += await _flush_events()
    return count


async def _flush_events() -> int:
    """幂等投影 SSE 事件；失败事件留在有界队列中等待下一次 flush。"""
    if not _event_queue:
        return 0
    try:
        coll = _get_event_collection()
    except Exception:
        logger.exception("trace event collection unavailable (non-fatal)")
        return 0
    if coll is None:
        return 0

    items = list(_event_queue)
    _event_queue.clear()
    failed: list[dict[str, Any]] = []
    count = 0
    for item in items:
        trace_id = str(item.get("trace_id") or "")
        event_id = str(item.get("event_id") or "")
        if not trace_id or not event_id:
            failed.append(item)
            item["projection_status"] = "dropped"
            logger.error(
                "trace event projection skipped: missing identity trace_id=%s event_id=%s",
                trace_id,
                event_id,
            )
            continue
        try:
            persisted_item = {**item, "projection_status": "persisted"}
            result = await coll.update_one(
                {"trace_id": trace_id, "event_id": event_id},
                {"$set": persisted_item},
                upsert=True,
            )
            if getattr(result, "acknowledged", True) is False:
                raise RuntimeError("mongo_write_not_acknowledged")
            count += 1
        except Exception:
            item["projection_status"] = "retrying"
            failed.append(item)
            logger.exception(
                "trace event projection failed (non-fatal): trace_id=%s event_id=%s seq=%s",
                trace_id,
                event_id,
                item.get("seq"),
            )

    # Mongo 等待期间新入队的事件要保留在失败事件之后。
    pending = failed + list(_event_queue)
    _event_queue.clear()
    _event_queue.extend(pending)
    if count:
        logger.debug("trace events flushed: count=%d", count)
    return count


async def _refresh_summaries(new_items: list[dict[str, Any]]) -> None:
    """刷新受影响 request_id 的预计算摘要。"""
    try:
        from agent.domains.harness.observability.trace.summary import (
            build_trace_request_summary,
            summary_to_mongo_doc,
        )

        summary_coll = _get_summary_collection()
        if summary_coll is None:
            return

        rec_coll = _get_collection()
        if rec_coll is None:
            return

        # Collect unique request_ids
        request_ids = {
            item["request_id"] for item in new_items if item.get("request_id")
        }
        for request_id in request_ids:
            nodes = await rec_coll.find({"request_id": request_id}).to_list(length=500)
            summary = build_trace_request_summary(nodes)
            if summary is None:
                continue
            # Add node_breakdown
            from agent.domains.harness.observability.trace.store import _build_node_breakdown

            summary["node_breakdown"] = _build_node_breakdown(nodes)
            doc = summary_to_mongo_doc(summary)
            await summary_coll.replace_one(
                {"_id": request_id},
                doc,
                upsert=True,
            )
    except Exception as exc:
        logger.warning("trace summary refresh failed (non-fatal): %s", exc)


async def _flush_loop() -> None:
    """定时 flush。"""
    while _running:
        try:
            await asyncio.sleep(_FLUSH_INTERVAL)
            if _queue or _event_queue:
                await flush_now()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("trace flush loop error")
            await asyncio.sleep(1)


async def start_trace_system() -> None:
    """启动 trace 后台 flush worker。"""
    global _flush_task, _running
    index_specs = [
        (
            _get_collection(),
            _collection_name(),
            [("request_id", 1), ("step_index", 1)],
            {},
        ),
        (
            _get_collection(),
            _collection_name(),
            [("trace_id", 1), ("step_index", 1)],
            {},
        ),
        (
            _get_summary_collection(),
            _summary_collection_name(),
            [("conversation_id", 1), ("created_at", -1)],
            {},
        ),
        (
            _get_summary_collection(),
            _summary_collection_name(),
            [("turn_id", 1)],
            {},
        ),
        (
            _get_event_collection(),
            _event_collection_name(),
            [("trace_id", 1), ("event_id", 1)],
            {"unique": True},
        ),
        (
            _get_event_collection(),
            _event_collection_name(),
            [("trace_id", 1), ("seq", 1)],
            {"unique": True},
        ),
        (
            _get_event_collection(),
            _event_collection_name(),
            [("turn_id", 1), ("occurred_at", 1)],
            {},
        ),
    ]
    seen: set[tuple[str, tuple[tuple[str, int], ...]]] = set()
    for coll, collection_name, keys, options in index_specs:
        if coll is None:
            continue
        identity = (collection_name, tuple(keys))
        if identity in seen:
            continue
        seen.add(identity)
        try:
            await coll.create_index(keys, background=True, **options)
        except Exception:
            logger.exception(
                "trace index initialization failed: collection=%s keys=%s options=%s",
                collection_name,
                keys,
                options,
            )
    _running = True
    _flush_task = asyncio.create_task(_flush_loop())
    logger.info(
        "trace system started (batch=%d, interval=%.0fs)", _BATCH_SIZE, _FLUSH_INTERVAL
    )


async def stop_trace_system() -> None:
    """停止 trace 系统，flush 剩余数据。"""
    global _running, _flush_task
    _running = False
    if _flush_task:
        _flush_task.cancel()
        try:
            await _flush_task
        except asyncio.CancelledError:
            pass
    if _queue or _event_queue:
        await flush_now()
    logger.info(
        "trace system stopped, flush attempted: trace_records_pending=%d "
        "trace_events_pending=%d",
        len(_queue),
        len(_event_queue),
    )


def trace_llm_call(
    model: str,
    messages: list[dict],
    response: dict | None = None,
    duration_ms: int | None = None,
    token_usage: dict | None = None,
    error: str | None = None,
    attempt: int = 1,
) -> None:
    """记录完整的模型输入和输出，供 Trace Drawer 复盘单次模型调用。"""
    record(
        node_type="llm_call",
        node_name=model,
        input_data={"message_count": len(messages), "messages": messages},
        output_data=response,
        duration_ms=duration_ms,
        token_usage=token_usage,
        error_message=error,
        phase="reasoning",
        attempt=attempt,
        attributes={
            "provider": "configured_llm",
            "model": model,
            "message_count": len(messages),
            "tool_calls_count": len((response or {}).get("tool_calls") or []),
        },
    )


def trace_tool_call(
    tool_name: str,
    arguments: dict,
    result: Any = None,
    duration_ms: int | None = None,
    error: str | None = None,
    attempt: int = 1,
    *,
    agent_tool_name: str = "",
    business_tool_name: str = "",
    operation: str = "",
    capability_group: str = "",
    data_scope: str = "",
    freshness_requirement: str = "",
    tool_call_id: str = "",
    progress: str = "",
    progress_reason: str = "",
    observation_fingerprint: str = "",
    semantic_progress: str = "",
    semantic_progress_reason: str = "",
    parallel_batch_id: str = "",
    status: str = "",
    step_index: int | None = None,
) -> None:
    """记录 Agent 工具到 Business MCP 的真实映射和观察进度。"""
    resolved_agent_name = agent_tool_name or tool_name
    attributes = {
        "tool_name": resolved_agent_name,
        "agent_tool_name": resolved_agent_name,
        "business_tool_name": business_tool_name,
        "operation": operation,
        "capability_group": capability_group,
        "data_scope": data_scope,
        "freshness_requirement": freshness_requirement,
        "tool_call_id": tool_call_id,
        "progress": progress,
        "progress_reason": progress_reason,
        "observation_fingerprint": observation_fingerprint,
        "semantic_progress": semantic_progress,
        "semantic_progress_reason": semantic_progress_reason,
        "parallel_batch_id": parallel_batch_id,
    }
    attributes = {
        key: value for key, value in attributes.items() if value not in ("", None)
    }
    record(
        node_type="tool_call",
        node_name=resolved_agent_name,
        input_data=arguments,
        output_data=result,
        duration_ms=duration_ms,
        error_message=error,
        phase="tool_executing",
        attempt=attempt,
        attributes=attributes,
        step_index=step_index,
        status=status or None,
    )


def trace_skill_router(
    *,
    registry_count: int,
    exposed_tool_count: int,
    selected_tools: list[str] | None = None,
    candidate_tools: list[str] | None = None,
    selected_skills: list[str] | None = None,
    candidate_skills: list[str] | None = None,
    router_status: str | None = None,
    router_error: str | None = None,
    metadata_version: str = "",
    selected_tool_calls: list[dict[str, Any]] | None = None,
    selection_status: str = "selected",
    decision_source: str = "llm_tool_call",
    duration_ms: int | None = None,
    router_mode: str = "llm_tool_binding",
    step_index: int | None = None,
) -> None:
    """记录 LLM 返回后的真实 Skill 选择结果。"""
    resolved_selected_tools = list(dict.fromkeys(selected_tools or []))
    resolved_selected_skills = list(dict.fromkeys(selected_skills or []))
    resolved_candidate_skills = list(dict.fromkeys(candidate_skills or []))
    record(
        node_type="skill_router",
        node_name="skill_router.r1",
        input_data={
            "registry_skill_count": registry_count,
            "exposed_tool_count": exposed_tool_count,
            "candidate_tools": candidate_tools or [],
            "candidate_skills": resolved_candidate_skills,
            "metadata_version": metadata_version,
            "router_mode": router_mode,
        },
        output_data={
            "schema_version": 2,
            "selection_status": selection_status,
            "selected_tools": resolved_selected_tools,
            "selected_skills": resolved_selected_skills,
            "selected_tool_calls": selected_tool_calls or [],
            "decision_source": decision_source,
            "candidate_count": exposed_tool_count,
            "router_status": router_status or selection_status,
            "router_error": router_error,
        },
        duration_ms=duration_ms,
        phase="reasoning",
        step_index=step_index,
        attributes={
            "registry_skill_count": registry_count,
            "exposed_tool_count": exposed_tool_count,
            "selected_tool_count": len(resolved_selected_tools),
            "selected_skill_count": len(resolved_selected_skills),
            "candidate_skill_count": len(resolved_candidate_skills),
            "selection_status": selection_status,
            "decision_source": decision_source,
            "router_mode": router_mode,
        },
    )


def trace_catalog_recall(
    *,
    registry_count: int,
    exposed_tool_count: int,
    candidate_tools: list[str],
    duration_ms: int | None = None,
    router_mode: str = "llm_tool_binding",
    step_budget: dict[str, Any] | None = None,
) -> None:
    """记录 LLM 决策前的 Skill 候选目录快照。"""
    record(
        node_type="catalog_recall",
        node_name="skill_catalog.load",
        input_data={
            "registry_skill_count": registry_count,
            "exposed_tool_count": exposed_tool_count,
            "router_mode": router_mode,
        },
        output_data={
            "candidate_tools": candidate_tools,
            "candidate_count": len(candidate_tools),
            "selection_status": "pending",
            "decision_source": "skill_registry",
            "step_budget": step_budget or {},
        },
        duration_ms=duration_ms,
        phase="setup",
        attributes={
            "registry_skill_count": registry_count,
            "exposed_tool_count": exposed_tool_count,
            "candidate_count": len(candidate_tools),
            "router_mode": router_mode,
            "step_budget_source": (step_budget or {}).get("source", ""),
            "step_budget_limit": (step_budget or {}).get("resolved_steps"),
        },
    )


def trace_context_build(
    *,
    message_count: int,
    history_count: int,
    memory_block_count: int,
    duration_ms: int | None = None,
    compressed: bool = False,
    blocks: list[dict[str, Any]] | None = None,
    budget: dict[str, Any] | None = None,
    conversation_revision: int = 0,
    summary_revision: int = 0,
    source_status: str = "",
    tool_schema_mode: str = "all",
    selected_skills: list[str] | None = None,
    context_dependencies: list[str] | None = None,
    memory_revision: int = 0,
    estimation_mode: str = "approximate",
) -> None:
    """记录模型实际上下文装配的摘要，不重复保存对话全文。"""
    record(
        node_type="context_build",
        node_name="context.build_initial_messages",
        input_data={
            "history_count": history_count,
            "memory_block_count": memory_block_count,
        },
        output_data={
            "message_count": message_count,
            "compressed": compressed,
            "blocks": blocks or [],
            "budget": budget or {},
            "selected_skills": selected_skills or [],
            "context_dependencies": context_dependencies or [],
            "memory_revision": memory_revision,
            "estimation_mode": estimation_mode,
        },
        duration_ms=duration_ms,
        phase="setup",
        attributes={
            "history_count": history_count,
            "memory_block_count": memory_block_count,
            "message_count": message_count,
            "compressed": compressed,
            "conversation_revision": conversation_revision,
            "summary_revision": summary_revision,
            "memory_revision": memory_revision,
            "source_status": source_status,
            "tool_schema_mode": tool_schema_mode,
            "estimation_mode": estimation_mode,
            "selected_skill_count": len(selected_skills or []),
        },
    )


def trace_summary_compaction(
    *,
    source_conversation_revision: int,
    summary_revision: int,
    status: str,
    reason: str,
    duration_ms: int = 0,
    error_code: str | None = None,
) -> None:
    """记录摘要 claim/commit/失败，不记录摘要全文。"""
    record(
        node_type="summary_compaction",
        node_name="memory.summary_compaction",
        output_data={
            "source_conversation_revision": source_conversation_revision,
            "summary_revision": summary_revision,
            "status": status,
            "reason": reason,
            "error_code": error_code,
        },
        duration_ms=duration_ms,
        status="error" if error_code else "success",
        error_message=error_code,
        phase="memory",
    )


def trace_memory_read(
    *, source_status: str, memory_revision: int = 0, hit_count: int = 0
) -> None:
    """记录 Short/Long Memory 读取状态和命中数量。"""
    record(
        node_type="memory_read",
        node_name="memory.get_session_view",
        output_data={
            "source_status": source_status,
            "memory_revision": memory_revision,
            "hit_count": hit_count,
        },
        phase="memory",
        status="error" if source_status in {"unavailable", "divergent"} else "success",
        error_message=(
            f"memory_source_{source_status}"
            if source_status in {"unavailable", "divergent"}
            else None
        ),
    )


def trace_memory_observe(*, status: str, source_status: str, idempotent: bool) -> None:
    """记录 observation 是否落库，区别 accepted、unavailable 和幂等命中。"""
    record(
        node_type="memory_observe",
        node_name="memory.observe",
        output_data={
            "status": status,
            "source_status": source_status,
            "idempotent": idempotent,
        },
        phase="finalizing",
        status="error" if source_status == "unavailable" else "success",
        error_message="memory_observation_unavailable"
        if source_status == "unavailable"
        else None,
    )


def trace_context_source_divergence(
    *, sources: dict[str, Any], code: str = "context_source_divergence"
) -> None:
    """记录事实源版本/状态不一致，禁止把它解释成业务不存在。"""
    record(
        node_type="context_source_divergence",
        node_name="context.source_consistency",
        output_data={"code": code, "sources": sources},
        phase="setup",
        status="error",
        error_message=code,
    )


def trace_context_budget_error(*, budget: dict[str, Any], code: str) -> None:
    """记录 required block 或输出预留导致的预算错误。"""
    record(
        node_type="context_budget_error",
        node_name="context.budget",
        output_data={"code": code, "budget": budget},
        phase="setup",
        status="error",
        error_message=code,
    )


def trace_persistence_state(
    *, message_status: str, session_status: str, observation_status: str
) -> None:
    """记录终态消息、Session 和 observation 的收尾状态。"""
    incomplete = any(
        value not in {"ready", "idempotent", "skipped"}
        for value in (message_status, session_status, observation_status)
    )
    record(
        node_type="persistence_state",
        node_name="turn.finalization",
        output_data={
            "message_status": message_status,
            "session_status": session_status,
            "observation_status": observation_status,
        },
        phase="finalizing",
        status="fallback" if incomplete else "success",
        error_message="turn_finalization_incomplete" if incomplete else None,
    )


def trace_approval(
    *,
    tool_name: str,
    risk_level: str,
    decision: str,
    duration_ms: int,
    reason: str = "",
) -> None:
    """记录 HITL 等待和决议，不把审批正文重复写入 Trace。"""
    record(
        node_type="approval",
        node_name=tool_name,
        input_data={"tool_name": tool_name, "risk_level": risk_level},
        output_data={"decision": decision, "reason": reason},
        duration_ms=duration_ms,
        phase="awaiting_approval",
        status="error" if decision in {"rejected", "expired", "cancelled"} else "success",
        error_message=reason if decision in {"rejected", "expired", "cancelled"} else None,
        attributes={
            "tool_name": tool_name,
            "risk_level": risk_level,
            "decision": decision,
        },
    )


def trace_queue_wait(duration_ms: int) -> None:
    """记录 Worker 从入队到执行的等待时间。"""
    record(
        node_type="queue_wait",
        node_name="redis.dispatch",
        duration_ms=duration_ms,
        phase="setup",
        attributes={"queue_wait_ms": duration_ms},
        resource={"system": "redis", "operation": "xreadgroup"},
    )


def trace_commit_state(result: dict[str, Any], *, reply_generated: bool) -> None:
    """记录业务已提交与模型收尾状态，避免把答复失败误判为写入失败。"""
    record(
        node_type="commit_state",
        node_name="write_finalization",
        output_data={
            "business_committed": True,
            "reply_generated": reply_generated,
            "result": result,
        },
        phase="finalizing",
        attributes={
            "business_committed": True,
            "reply_generated": reply_generated,
        },
    )


def trace_turn_outcome(status: str, error: str | None = None) -> None:
    """记录 turn 最终状态，避免异常路径在请求摘要中伪装成 success。"""
    failed = bool(error) or status == "failed"
    trace = get_trace()
    if trace is not None:
        record(
            node_type="trace_root",
            node_name="turn",
            start_time=trace.created_at,
            end_time=time.time(),
            duration_ms=int((time.time() - trace.created_at) * 1000),
            span_id=getattr(trace, "root_span_id", None) or "root",
            parent_span_id=None,
            span_kind="root",
            layer="agent",
            phase="terminal",
            step_index=0,
            attributes={"turn_id": trace.turn_id},
        )
    record(
        node_type="turn",
        node_name="outcome",
        input_data={"status": status},
        output_data={
            "status": status,
            "error": {"code": error or status} if failed else None,
        },
        error_message=error,
        status="error" if failed else "success",
        parent_span_id=(getattr(trace, "root_span_id", None) or "root")
        if trace
        else None,
        phase="terminal",
        attributes={"stop_status": status},
    )
