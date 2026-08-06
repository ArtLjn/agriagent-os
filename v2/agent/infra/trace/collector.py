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
_flush_task: asyncio.Task | None = None
_running = False


def _collection_name() -> str:
    return settings.mongodb.collections.get("trace_records", "traceRecords")


def _summary_collection_name() -> str:
    return settings.mongodb.collections.get(
        "trace_request_summaries", "traceRequestSummaries"
    )


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
        "request_id": trace.request_id,
        "conversation_id": trace.conversation_id,
        "turn_id": trace.turn_id,
        "step_index": get_step_index(),
        "node_type": node_type,
        "node_name": node_name,
        "input_data": _truncate(input_data) if input_data else None,
        "output_data": _truncate(output_data) if output_data else None,
        "start_time": datetime.fromtimestamp(start_time),
        "end_time": datetime.fromtimestamp(end_time),
        "duration_ms": duration_ms,
        "token_usage": token_usage,
        "status": status or ("error" if error_message else "success"),
        "error_message": error_message,
        "created_at": datetime.now(),
    }
    _queue.append(trace_data)


async def flush_now() -> int:
    """立即将队列中的 trace 写入 MongoDB，并刷新预计算摘要。"""
    if not _queue:
        return 0
    coll = _get_collection()
    if coll is None:
        _queue.clear()
        return 0

    items = list(_queue)
    _queue.clear()
    try:
        result = await coll.insert_many(items, ordered=False)
        count = len(result.inserted_ids)
        logger.debug("trace flushed: %d records", count)

        # Refresh pre-computed summaries for affected request_ids
        await _refresh_summaries(items)
        return count
    except Exception as exc:
        logger.warning("trace flush failed (non-fatal): %s", exc)
        return 0


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
        request_ids = {item["request_id"] for item in new_items if item.get("request_id")}
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
            if _queue:
                await flush_now()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("trace flush loop error")
            await asyncio.sleep(1)


async def start_trace_system() -> None:
    """启动 trace 后台 flush worker。"""
    global _flush_task, _running
    coll = _get_collection()
    if coll is not None:
        try:
            await coll.database[_collection_name()].create_index(
                [("request_id", 1), ("step_index", 1)], background=True
            )
        except Exception:
            pass
    _running = True
    _flush_task = asyncio.create_task(_flush_loop())
    logger.info("trace system started (batch=%d, interval=%.0fs)", _BATCH_SIZE, _FLUSH_INTERVAL)


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
    if _queue:
        await flush_now()
    logger.info("trace system stopped, remaining data flushed")


def trace_llm_call(
    model: str,
    messages: list[dict],
    response: dict | None = None,
    duration_ms: int | None = None,
    token_usage: dict | None = None,
    error: str | None = None,
) -> None:
    """便捷方法：记录 LLM 调用。"""
    record(
        node_type="llm_call",
        node_name=model,
        input_data={"message_count": len(messages)},
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
