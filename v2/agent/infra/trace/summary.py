"""Trace Summary — Build request-level summaries from trace nodes.

Adapted from archive/backend/app/infra/trace_summary.py,
v2 uses MongoDB document dicts instead of SQLAlchemy TraceRecord objects.

Core function: build_trace_request_summary(nodes) -> dict | None
"""
from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime
from typing import Any

TRACE_SUMMARY_SCHEMA_VERSION = 1

_FAILED_STATUSES = {"failed", "error", "timeout", "cancelled"}
_BLOCKED_STATUSES = {"blocked"}


def build_trace_request_summary(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Build a request-level summary from trace node docs.

    Args:
        nodes: List of MongoDB trace record dicts (from traceRecords collection).

    Returns:
        Summary dict or None if nodes is empty.
    """
    if not nodes:
        return None

    ordered = sorted(nodes, key=_node_sort_key)
    first = ordered[0]
    root_error = _root_error(ordered)
    metrics = _metrics(ordered)
    started_at = _first_time(ordered)
    ended_at = _last_time(ordered)
    status = _request_status(ordered, root_error)
    node_breakdown = _node_breakdown(ordered)

    return {
        "schema_version": TRACE_SUMMARY_SCHEMA_VERSION,
        "request_id": str(first.get("request_id", "")),
        "conversation_id": str(first.get("conversation_id", "")),
        "turn_id": str(first.get("turn_id", "")),
        "node_count": len(ordered),
        "total_duration_ms": metrics["total_duration_ms"],
        "created_at": _format_datetime(ended_at or started_at),
        "started_at": _format_datetime(started_at),
        "ended_at": _format_datetime(ended_at),
        "status": status,
        "status_reason": _status_reason(root_error, status),
        "error_count": _error_count(ordered),
        "root_error": root_error,
        "metrics": metrics,
        "node_breakdown": node_breakdown,
    }


def summary_to_mongo_doc(summary: dict[str, Any]) -> dict[str, Any]:
    """Convert API summary dict to MongoDB summary document."""
    return {
        "_id": summary["request_id"],
        "schema_version": summary["schema_version"],
        "request_id": summary["request_id"],
        "conversation_id": summary.get("conversation_id"),
        "turn_id": summary.get("turn_id"),
        "node_count": summary["node_count"],
        "total_duration_ms": summary["total_duration_ms"],
        "created_at": _parse_datetime(summary.get("created_at")),
        "started_at": _parse_datetime(summary.get("started_at")),
        "ended_at": _parse_datetime(summary.get("ended_at")),
        "status": summary["status"],
        "status_reason": summary.get("status_reason"),
        "error_count": summary["error_count"],
        "root_error": summary.get("root_error"),
        "metrics": summary.get("metrics") or {},
        "node_breakdown": summary.get("node_breakdown") or [],
        "updated_at": datetime.now(),
    }


def summary_from_mongo_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert MongoDB summary document to API response dict."""
    return {
        "schema_version": int(doc.get("schema_version") or TRACE_SUMMARY_SCHEMA_VERSION),
        "request_id": str(doc.get("request_id") or doc.get("_id") or ""),
        "conversation_id": doc.get("conversation_id"),
        "turn_id": doc.get("turn_id"),
        "node_count": int(doc.get("node_count") or 0),
        "total_duration_ms": int(doc.get("total_duration_ms") or 0),
        "created_at": _format_datetime(doc.get("created_at")),
        "started_at": _format_datetime(doc.get("started_at")),
        "ended_at": _format_datetime(doc.get("ended_at")),
        "status": str(doc.get("status") or "success"),
        "status_reason": doc.get("status_reason"),
        "error_count": int(doc.get("error_count") or 0),
        "root_error": doc.get("root_error"),
        "metrics": doc.get("metrics") or {},
        "node_breakdown": doc.get("node_breakdown") or [],
    }


def _metrics(nodes: list[dict[str, Any]]) -> dict[str, Any]:
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
        if node_type in {"llm", "llm_call"}:
            metrics["llm_calls"] += 1
            metrics["llm_duration_ms"] += duration
        elif node_type in {"tool", "skill_call"}:
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

        usage = _json_value(node.get("token_usage"))
        if isinstance(usage, dict):
            metrics["prompt_tokens"] += _int_value(
                usage.get("prompt_tokens", usage.get("input_tokens"))
            )
            metrics["completion_tokens"] += _int_value(
                usage.get("completion_tokens", usage.get("output_tokens"))
            )
            metrics["total_tokens"] += _int_value(usage.get("total_tokens"))
    return metrics


def _node_breakdown(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        if _node_has_error(node):
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


def _root_error(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    for node in nodes:
        if _node_has_error(node):
            return _root_error_from_node(node)
    return None


def _root_error_from_node(node: dict[str, Any]) -> dict[str, Any]:
    output = _json_value(node.get("output_data"))
    error_record: dict[str, Any] = {}
    if isinstance(output, dict):
        err = output.get("error")
        if isinstance(err, dict):
            error_record = err

    result: dict[str, Any] = {
        "node_type": _optional_str(node.get("node_type")),
        "node_name": _optional_str(node.get("node_name")),
        "code": _first_present(
            error_record.get("code"),
            output.get("code") if isinstance(output, dict) else None,
            error_record.get("type"),
            _fallback_error_code(node),
        ),
        "message": _first_present(
            node.get("error_message"),
            error_record.get("message"),
            output.get("message") if isinstance(output, dict) else None,
        ),
    }
    return {key: value for key, value in result.items() if value is not None}


def _node_has_error(node: dict[str, Any]) -> bool:
    if node.get("error_message"):
        return True
    status = str(node.get("status") or "").lower()
    if status and status != "success":
        return True
    output = _json_value(node.get("output_data"))
    return isinstance(output, dict) and bool(output.get("error") or output.get("code"))


def _request_status(
    nodes: list[dict[str, Any]], root_error: dict[str, Any] | None
) -> str:
    statuses = {str(node.get("status") or "").lower() for node in nodes}
    if statuses & _BLOCKED_STATUSES:
        return "blocked"
    if statuses & _FAILED_STATUSES:
        return "failed"
    return "failed" if root_error else "success"


def _status_reason(root_error: dict[str, Any] | None, status: str) -> str | None:
    if status == "success":
        return None
    if root_error:
        return str(root_error.get("code") or root_error.get("node_name") or status)
    return status


def _error_count(nodes: list[dict[str, Any]]) -> int:
    return sum(1 for node in nodes if _node_has_error(node))


def _first_time(nodes: list[dict[str, Any]]) -> datetime | None:
    times = [_node_time(node) for node in nodes]
    valid_times = [value for value in times if value is not None]
    return min(valid_times) if valid_times else None


def _last_time(nodes: list[dict[str, Any]]) -> datetime | None:
    times = [_node_end_time(node) for node in nodes]
    valid_times = [value for value in times if value is not None]
    return max(valid_times) if valid_times else None


def _node_sort_key(node: dict[str, Any]) -> tuple:
    return (
        _node_time(node) or datetime.min,
        int(node.get("step_index") or 0),
        str(node.get("node_name") or ""),
    )


def _node_time(node: dict[str, Any]) -> datetime | None:
    return _coerce_datetime(node.get("start_time")) or _coerce_datetime(
        node.get("created_at")
    )


def _node_end_time(node: dict[str, Any]) -> datetime | None:
    return (
        _coerce_datetime(node.get("end_time"))
        or _coerce_datetime(node.get("start_time"))
        or _coerce_datetime(node.get("created_at"))
    )


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    return None


def _parse_datetime(value: Any) -> datetime | None:
    return _coerce_datetime(value)


def _format_datetime(value: Any) -> str | None:
    resolved = _coerce_datetime(value)
    return resolved.isoformat() if resolved is not None else None


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _fallback_error_code(node: dict[str, Any]) -> str | None:
    status = str(node.get("status") or "").lower()
    if status and status != "success":
        node_type = str(node.get("node_type") or "node")
        return f"{node_type}_{status}"
    return None


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


__all__ = [
    "TRACE_SUMMARY_SCHEMA_VERSION",
    "build_trace_request_summary",
    "summary_to_mongo_doc",
    "summary_from_mongo_doc",
]
