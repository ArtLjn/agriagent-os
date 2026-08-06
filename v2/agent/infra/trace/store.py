"""Trace Store — MongoDB query functions for trace read operations.

Provides:
- list_traces: list request-level trace summaries (with conversation_id filter + pagination)
- get_trace_nodes: get all trace nodes for a request_id, ordered by step_index + created_at
- get_trace_summary: get pre-computed or build-on-demand request summary
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import datetime
from typing import Any

from agent.config import settings

logger = logging.getLogger(__name__)


def _trace_collection_name() -> str:
    return settings.mongodb.collections.get("trace_records", "traceRecords")


def _summary_collection_name() -> str:
    return settings.mongodb.collections.get(
        "trace_request_summaries", "traceRequestSummaries"
    )


def _get_trace_collection():
    """Lazy-init trace records collection."""
    if not settings.mongodb.enabled:
        return None
    from agent.infra.chat_store import get_collection as _get_chat_collection

    chat_coll = _get_chat_collection()
    if chat_coll is None:
        return None
    return chat_coll.database[_trace_collection_name()]


def _get_summary_collection():
    """Lazy-init trace request summaries collection."""
    if not settings.mongodb.enabled:
        return None
    from agent.infra.chat_store import get_collection as _get_chat_collection

    chat_coll = _get_chat_collection()
    if chat_coll is None:
        return None
    return chat_coll.database[_summary_collection_name()]


async def list_traces(
    conversation_id: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
) -> dict[str, Any]:
    """List request-level trace summaries.

    Prefers pre-computed ``traceRequestSummaries`` collection.
    Falls back to on-demand aggregation from ``traceRecords`` if summaries
    collection is empty or disabled.

    Returns:
        {
            "items": [ {request_id, conversation_id, turn_id, node_count,
                        total_duration_ms, status, error_count, root_error,
                        started_at, ended_at, metrics}, ... ],
            "next_cursor": str | null,
            "has_more": bool
        }
    """
    coll = _get_trace_collection()
    if coll is None:
        return {"items": [], "next_cursor": None, "has_more": False}

    summary_coll = _get_summary_collection()

    # ── Try pre-computed summaries first ──────────────────────────────
    if summary_coll is not None:
        try:
            result = await _list_from_summary_collection(
                summary_coll, conversation_id, limit, cursor
            )
            if result["items"]:
                return result
        except Exception as exc:
            logger.warning("trace summary collection read failed, fallback to aggregation: %s", exc)

    # ── Fallback: on-demand aggregation from raw records ───────────────
    return await _list_from_raw_records(coll, conversation_id, limit, cursor)


async def _list_from_summary_collection(
    summary_coll,
    conversation_id: str | None,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    """Read from pre-computed summaries collection."""
    filter_doc: dict[str, Any] = {}
    if conversation_id:
        filter_doc["conversation_id"] = conversation_id
    if cursor:
        filter_doc["_id"] = {"$lt": cursor}

    cursor_obj = (
        summary_coll.find(filter_doc)
        .sort("_id", -1)
        .limit(limit + 1)
    )
    docs = await cursor_obj.to_list(length=limit + 1)

    has_more = len(docs) > limit
    items = [_summary_doc_to_api(doc) for doc in docs[:limit]]
    next_cursor = docs[limit]["_id"] if has_more and len(docs) > limit else None

    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def _list_from_raw_records(
    coll,
    conversation_id: str | None,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    """On-demand aggregation from raw traceRecords."""
    filter_doc: dict[str, Any] = {}
    if conversation_id:
        filter_doc["conversation_id"] = conversation_id

    # Get distinct request_ids with their latest timestamp
    pipeline: list[dict[str, Any]] = [
        {"$match": filter_doc},
        {
            "$group": {
                "_id": "$request_id",
                "conversation_id": {"$first": "$conversation_id"},
                "turn_id": {"$first": "$turn_id"},
                "latest_time": {"$max": "$created_at"},
                "node_count": {"$sum": 1},
                "total_duration_ms": {"$sum": "$duration_ms"},
            }
        },
        {"$sort": {"latest_time": -1}},
    ]

    if cursor:
        # Get the cutoff time for cursor-based pagination
        try:
            cursor_doc = await coll.find_one({"_id": cursor})
            if cursor_doc:
                pipeline.insert(
                    1,
                    {
                        "$match": {
                            **filter_doc,
                            "created_at": {"$lt": cursor_doc["created_at"]},
                        }
                    },
                )
        except Exception:
            pass

    pipeline.append({"$limit": limit + 1})

    try:
        results = await coll.aggregate(pipeline).to_list(length=limit + 1)
    except Exception as exc:
        logger.warning("trace aggregation failed: %s", exc)
        return {"items": [], "next_cursor": None, "has_more": False}

    has_more = len(results) > limit
    results = results[:limit]

    items = []
    for r in results:
        request_id = r["_id"]
        nodes = await coll.find({"request_id": request_id}).to_list(length=500)
        summary = _build_summary_from_nodes(nodes, request_id)
        if summary:
            items.append(summary)

    next_cursor = items[-1]["request_id"] if has_more and items else None
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}


async def get_trace_nodes(
    request_id: str,
    limit: int = 200,
) -> dict[str, Any]:
    """Get all trace nodes for a request_id, ordered by step_index + created_at.

    Returns:
        {
            "request_id": str,
            "conversation_id": str,
            "turn_id": str,
            "nodes": [...],
            "count": int,
            "has_more": bool
        }
    """
    coll = _get_trace_collection()
    if coll is None:
        return {"request_id": request_id, "nodes": [], "count": 0, "has_more": False}

    cursor = (
        coll.find({"request_id": request_id})
        .sort([("step_index", 1), ("created_at", 1)])
        .limit(limit + 1)
    )
    docs = await cursor.to_list(length=limit + 1)
    has_more = len(docs) > limit
    docs = docs[:limit]

    if not docs:
        return {"request_id": request_id, "nodes": [], "count": 0, "has_more": False}

    nodes = [_node_doc_to_api(doc) for doc in docs]
    return {
        "request_id": request_id,
        "conversation_id": docs[0].get("conversation_id", ""),
        "turn_id": docs[0].get("turn_id", ""),
        "nodes": nodes,
        "count": len(nodes),
        "has_more": has_more,
    }


async def get_trace_summary(
    request_id: str,
) -> dict[str, Any] | None:
    """Get request-level summary (pre-computed or on-demand).

    Returns full summary with metrics + node_breakdown, or None if no data.
    """
    # Try pre-computed summary first
    summary_coll = _get_summary_collection()
    if summary_coll is not None:
        try:
            doc = await summary_coll.find_one({"_id": request_id})
            if doc:
                return _summary_doc_to_full_api(doc)
        except Exception:
            pass

    # Fallback: build from raw nodes
    coll = _get_trace_collection()
    if coll is None:
        return None

    nodes = await coll.find({"request_id": request_id}).to_list(length=500)
    if not nodes:
        return None

    summary = _build_summary_from_nodes(nodes, request_id)
    if summary is None:
        return None

    # Add node_breakdown
    summary["node_breakdown"] = _build_node_breakdown(nodes)
    return summary


# ── Summary builders ───────────────────────────────────────────────


def _build_summary_from_nodes(
    nodes: list[dict[str, Any]], request_id: str
) -> dict[str, Any] | None:
    """Build a request-level summary from raw trace node docs."""
    if not nodes:
        return None

    ordered = sorted(nodes, key=_node_sort_key)
    first = ordered[0]
    last = ordered[-1]

    started_at = _coerce_datetime(first.get("start_time") or first.get("created_at"))
    ended_at = _coerce_datetime(last.get("end_time") or last.get("created_at"))
    if ended_at is None:
        ended_at = started_at

    status = _compute_status(ordered)
    root_error = _find_root_error(ordered)
    metrics = _compute_metrics(ordered)
    error_count = sum(1 for n in ordered if _node_has_error(n))

    return {
        "request_id": request_id,
        "conversation_id": first.get("conversation_id", ""),
        "turn_id": first.get("turn_id", ""),
        "node_count": len(ordered),
        "total_duration_ms": metrics["total_duration_ms"],
        "status": status,
        "error_count": error_count,
        "root_error": root_error,
        "started_at": _format_datetime(started_at),
        "ended_at": _format_datetime(ended_at),
        "status_reason": _status_reason(root_error, status),
        "metrics": metrics,
    }


def _compute_metrics(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "total_duration_ms": 0,
        "llm_duration_ms": 0,
        "tool_duration_ms": 0,
        "rag_duration_ms": 0,
        "memory_duration_ms": 0,
        "planner_duration_ms": 0,
        "reflection_duration_ms": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "llm_calls": 0,
        "tool_calls": 0,
        "skill_calls": 0,
    }
    for node in nodes:
        duration = int(node.get("duration_ms") or 0)
        metrics["total_duration_ms"] += duration
        node_type = str(node.get("node_type") or "")
        if node_type in {"llm_call", "llm"}:
            metrics["llm_calls"] += 1
            metrics["llm_duration_ms"] += duration
        elif node_type in {"tool_call", "skill_call", "tool"}:
            metrics["tool_calls"] += 1
            metrics["skill_calls"] += 1
            metrics["tool_duration_ms"] += duration
        elif node_type in {"rag", "context_build"}:
            metrics["rag_duration_ms"] += duration
        elif node_type == "memory":
            metrics["memory_duration_ms"] += duration
        elif node_type in {"planner", "routing", "prompt_render"}:
            metrics["planner_duration_ms"] += duration
        elif node_type in {"reflection", "reflection_check"}:
            metrics["reflection_duration_ms"] += duration

        usage = node.get("token_usage")
        if isinstance(usage, dict):
            metrics["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            metrics["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            metrics["total_tokens"] += int(usage.get("total_tokens") or 0)

    return metrics


def _build_node_breakdown(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group nodes by node_type and compute per-type stats."""
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for node in nodes:
        node_type = str(node.get("node_type") or "unknown")
        item = grouped.setdefault(
            node_type,
            {
                "node_type": node_type,
                "count": 0,
                "duration_ms_total": 0,
                "error_count": 0,
            },
        )
        item["count"] += 1
        item["duration_ms_total"] += int(node.get("duration_ms") or 0)
        if str(node.get("status") or "") != "success":
            item["error_count"] += 1

    result = []
    for item in grouped.values():
        item["avg_duration_ms"] = (
            round(item["duration_ms_total"] / item["count"], 1)
            if item["count"]
            else 0
        )
        result.append(item)
    return result


def _compute_status(nodes: list[dict[str, Any]]) -> str:
    """Compute overall request status from node statuses."""
    failed_statuses = {"failed", "error", "timeout", "cancelled"}
    blocked_statuses = {"blocked"}
    statuses = {str(n.get("status") or "").lower() for n in nodes}
    if statuses & blocked_statuses:
        return "blocked"
    if statuses & failed_statuses:
        return "failed"
    # Check root error
    for n in nodes:
        if _node_has_error(n):
            return "failed"
    return "success"


def _find_root_error(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find the root error from trace nodes."""
    for node in nodes:
        if not _node_has_error(node):
            continue
        output = node.get("output_data")
        if isinstance(output, str):
            import json

            try:
                output = json.loads(output)
            except (json.JSONDecodeError, ValueError):
                output = None

        error_data: dict[str, Any] = {}
        if isinstance(output, dict):
            err = output.get("error")
            if isinstance(err, dict):
                error_data = err

        result: dict[str, Any] = {}
        code = (
            error_data.get("code")
            or (output.get("code") if isinstance(output, dict) else None)
            or f"{node.get('node_type')}_error"
        )
        message = (
            node.get("error_message")
            or error_data.get("message")
            or (output.get("message") if isinstance(output, dict) else None)
        )
        if code:
            result["code"] = str(code)
        if message:
            result["message"] = str(message)
        if node.get("node_type"):
            result["node_type"] = str(node["node_type"])
        if node.get("node_name"):
            result["node_name"] = str(node["node_name"])

        return result or None
    return None


def _node_has_error(node: dict[str, Any]) -> bool:
    if node.get("error_message"):
        return True
    status = str(node.get("status") or "").lower()
    if status and status != "success":
        return True
    return False


def _status_reason(root_error: dict[str, Any] | None, status: str) -> str | None:
    if status == "success":
        return None
    if root_error:
        return str(root_error.get("code") or root_error.get("node_name") or status)
    return status


# ── Doc conversion helpers ──────────────────────────────────────────


def _node_doc_to_api(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a MongoDB trace record doc to API response format."""
    return {
        "step_index": int(doc.get("step_index") or 0),
        "node_type": doc.get("node_type", ""),
        "node_name": doc.get("node_name", ""),
        "input_data": doc.get("input_data"),
        "output_data": doc.get("output_data"),
        "start_time": _format_datetime(doc.get("start_time")),
        "end_time": _format_datetime(doc.get("end_time")),
        "duration_ms": int(doc.get("duration_ms") or 0),
        "token_usage": doc.get("token_usage"),
        "status": doc.get("status", "success"),
        "error_message": doc.get("error_message"),
    }


def _summary_doc_to_api(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a summary doc to list-item API format."""
    return {
        "request_id": doc.get("request_id", doc.get("_id", "")),
        "conversation_id": doc.get("conversation_id", ""),
        "turn_id": doc.get("turn_id", ""),
        "node_count": int(doc.get("node_count") or 0),
        "total_duration_ms": int(doc.get("total_duration_ms") or 0),
        "status": doc.get("status", "success"),
        "error_count": int(doc.get("error_count") or 0),
        "root_error": doc.get("root_error"),
        "started_at": _format_datetime(doc.get("started_at")),
        "ended_at": _format_datetime(doc.get("ended_at")),
        "metrics": doc.get("metrics") or {},
    }


def _summary_doc_to_full_api(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a summary doc to full API format (with node_breakdown)."""
    result = _summary_doc_to_api(doc)
    result["node_breakdown"] = doc.get("node_breakdown") or []
    result["status_reason"] = doc.get("status_reason")
    return result


# ── Datetime helpers ────────────────────────────────────────────────


def _node_sort_key(node: dict[str, Any]) -> tuple:
    return (
        int(node.get("step_index") or 0),
        _coerce_datetime(node.get("created_at")) or datetime.min,
        str(node.get("node_name") or ""),
    )


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except ValueError:
            return None
    return None


def _format_datetime(value: Any) -> str | None:
    resolved = _coerce_datetime(value)
    return resolved.isoformat() if resolved is not None else None


__all__ = [
    "list_traces",
    "get_trace_nodes",
    "get_trace_summary",
]
