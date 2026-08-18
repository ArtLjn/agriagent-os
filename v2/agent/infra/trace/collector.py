"""Trace 收集器 — MongoDB 批量写入。

参考 archive/backend/app/infra/trace_collector.py + trace_dao.py，
适配 v2 的 MongoDB 架构（用 motor 异步写入，不再用 SQLAlchemy）。

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
from datetime import datetime
from typing import Any

from agent.config import settings
from agent.infra.trace.context import get_trace, get_step_index

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
    from agent.infra.chat_store import get_collection as _get_chat_collection

    # 复用 chat_store 的 MongoDB 连接（同一个 client + database）。
    chat_coll = _get_chat_collection()
    if chat_coll is None:
        return None
    return chat_coll.database[_collection_name()]


def _get_summary_collection():
    """Lazy-init MongoDB collection for trace request summaries."""
    if not settings.mongodb.enabled:
        return None
    from agent.infra.chat_store import get_collection as _get_chat_collection

    chat_coll = _get_chat_collection()
    if chat_coll is None:
        return None
    return chat_coll.database[_summary_collection_name()]


def _get_event_collection():
    """延迟初始化持久化 SSE 事件集合。"""
    if not settings.mongodb.enabled:
        return None
    from agent.infra.chat_store import get_collection as _get_chat_collection

    chat_coll = _get_chat_collection()
    if chat_coll is None:
        return None
    return chat_coll.database[_event_collection_name()]


def _truncate(value: Any) -> Any:
    """限制 trace 数据体积。"""
    import json

    serialized = json.dumps(value, ensure_ascii=False, default=str)
    if len(serialized) <= _MAX_TRACE_JSON_LEN:
        return value
    return {
        "__truncated": True,
        "__original_len": len(serialized),
        "preview": serialized[:_MAX_TRACE_JSON_LEN],
    }


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

    trace_data = {
        "trace_id": trace.trace_id,
        "request_id": trace.request_id,
        "conversation_id": trace.conversation_id,
        "turn_id": trace.turn_id,
        "user_id": trace.user_id,
        "farm_uid": trace.farm_uid,
        "step_index": get_step_index(),
        "node_type": node_type,
        "node_name": node_name,
        "input_data": _truncate(input_data) if input_data is not None else None,
        "output_data": _truncate(output_data) if output_data is not None else None,
        "start_time": datetime.fromtimestamp(start_time),
        "end_time": datetime.fromtimestamp(end_time),
        "duration_ms": duration_ms,
        "token_usage": token_usage,
        "status": status or ("error" if error_message else "success"),
        "error_message": error_message,
        "created_at": datetime.now(),
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
        "event_id": event_id,
        "event_type": str(event.get("type") or ""),
        "seq": int(event.get("seq") or 0),
        "phase": str(event.get("phase") or ""),
        "step_index": int(event.get("step_index") or event.get("step") or 0),
        "terminal": bool(event.get("terminal")),
        "status_before": str(event.get("status_before") or ""),
        "status_after": str(event.get("status_after") or ""),
        "occurred_at": event.get("occurred_at"),
        "data": _truncate(event.get("data") or {}),
        "created_at": datetime.now(),
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
            logger.error(
                "trace event projection skipped: missing identity trace_id=%s event_id=%s",
                trace_id,
                event_id,
            )
            continue
        try:
            result = await coll.update_one(
                {"trace_id": trace_id, "event_id": event_id},
                {"$set": item},
                upsert=True,
            )
            if getattr(result, "acknowledged", True) is False:
                raise RuntimeError("mongo_write_not_acknowledged")
            count += 1
        except Exception:
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
        from agent.infra.trace.summary import (
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
            from agent.infra.trace.store import _build_node_breakdown

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
    )


def trace_tool_call(
    tool_name: str,
    arguments: dict,
    result: Any = None,
    duration_ms: int | None = None,
    error: str | None = None,
) -> None:
    """便捷方法：记录工具调用。"""
    record(
        node_type="tool_call",
        node_name=tool_name,
        input_data=arguments,
        output_data=result,
        duration_ms=duration_ms,
        error_message=error,
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
    )


def trace_turn_outcome(status: str, error: str | None = None) -> None:
    """记录 turn 最终状态，避免异常路径在请求摘要中伪装成 success。"""
    failed = bool(error) or status == "failed"
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
    )
