"""Trace request 级摘要构造。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.platforms.evaluation.trace_models import TraceRecord

TRACE_SUMMARY_SCHEMA_VERSION = 1

_FAILED_STATUSES = {"failed", "error", "timeout", "cancelled"}
_BLOCKED_STATUSES = {"blocked"}


def build_trace_request_summary(records: list[TraceRecord]) -> dict[str, Any] | None:
    """从同一 request 的 trace nodes 构造默认展示摘要。"""
    if not records:
        return None
    ordered = sorted(records, key=_record_sort_key)
    first = ordered[0]
    root_error = _root_error(ordered)
    metrics = _metrics(ordered)
    started_at = _first_time(ordered)
    ended_at = _last_time(ordered)
    status = _request_status(ordered, root_error)
    return {
        "schema_version": TRACE_SUMMARY_SCHEMA_VERSION,
        "request_id": str(first.request_id),
        "session_id": _optional_str(getattr(first, "session_id", None)),
        "farm_id": _int_value(getattr(first, "farm_id", 0)),
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
    }


def trace_request_summary_to_mongo_doc(summary: dict[str, Any]) -> dict[str, Any]:
    """把 API 摘要字段映射为 Mongo request summary 文档。"""
    farm_id = int(summary["farm_id"])
    request_id = str(summary["request_id"])
    return {
        "_id": f"{farm_id}:{request_id}",
        "schemaVersion": summary["schema_version"],
        "requestId": request_id,
        "sessionId": summary.get("session_id"),
        "farmId": farm_id,
        "nodeCount": summary["node_count"],
        "totalDurationMs": summary["total_duration_ms"],
        "createdAt": _parse_datetime(summary.get("created_at")),
        "startedAt": _parse_datetime(summary.get("started_at")),
        "endedAt": _parse_datetime(summary.get("ended_at")),
        "status": summary["status"],
        "statusReason": summary.get("status_reason"),
        "errorCount": summary["error_count"],
        "rootError": summary.get("root_error"),
        "metrics": summary.get("metrics") or {},
        "updatedAt": datetime.now(),
    }


def trace_request_summary_from_mongo_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """把 Mongo request summary 文档映射为 API 摘要字段。"""
    return {
        "schema_version": int(doc.get("schemaVersion") or TRACE_SUMMARY_SCHEMA_VERSION),
        "request_id": str(doc.get("requestId") or doc.get("_id") or ""),
        "session_id": doc.get("sessionId"),
        "farm_id": int(doc.get("farmId") or 0),
        "node_count": int(doc.get("nodeCount") or 0),
        "total_duration_ms": int(doc.get("totalDurationMs") or 0),
        "created_at": _format_datetime(doc.get("createdAt")),
        "started_at": _format_datetime(doc.get("startedAt")),
        "ended_at": _format_datetime(doc.get("endedAt")),
        "status": str(doc.get("status") or "success"),
        "status_reason": doc.get("statusReason"),
        "error_count": int(doc.get("errorCount") or 0),
        "root_error": doc.get("rootError"),
        "metrics": doc.get("metrics") or {},
    }


def _metrics(records: list[TraceRecord]) -> dict[str, Any]:
    metrics = {
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
    for record in records:
        duration = int(record.duration_ms or 0)
        metrics["total_duration_ms"] += duration
        node_type = str(record.node_type or "")
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
        usage = _json_value(record.token_usage)
        if isinstance(usage, dict):
            metrics["prompt_tokens"] += _int_value(
                usage.get("prompt_tokens", usage.get("input_tokens"))
            )
            metrics["completion_tokens"] += _int_value(
                usage.get("completion_tokens", usage.get("output_tokens"))
            )
            metrics["total_tokens"] += _int_value(usage.get("total_tokens"))
    return metrics


def _root_error(records: list[TraceRecord]) -> dict[str, Any] | None:
    for record in records:
        if _record_has_error(record):
            return _root_error_from_record(record)
    return None


def _root_error_from_record(record: TraceRecord) -> dict[str, Any]:
    output = _json_value(record.output_data)
    output_record = output if isinstance(output, dict) else {}
    error = output_record.get("error")
    error_record = error if isinstance(error, dict) else {}
    result = {
        "node_id": _optional_int(getattr(record, "id", None)),
        "node_type": _optional_str(getattr(record, "node_type", None)),
        "node_name": _optional_str(getattr(record, "node_name", None)),
        "code": _first_present(
            error_record.get("code"),
            output_record.get("code"),
            error_record.get("type"),
            _fallback_error_code(record),
        ),
        "message": _first_present(
            record.error_message,
            error_record.get("message"),
            output_record.get("message"),
            output_record.get("content"),
        ),
        "recover": _first_present(
            error_record.get("recover"), output_record.get("recover")
        ),
    }
    return {key: value for key, value in result.items() if value is not None}


def _record_has_error(record: TraceRecord) -> bool:
    if record.error_message:
        return True
    status = str(record.status or "").lower()
    if status and status != "success":
        return True
    output = _json_value(record.output_data)
    return isinstance(output, dict) and bool(output.get("error") or output.get("code"))


def _request_status(
    records: list[TraceRecord], root_error: dict[str, Any] | None
) -> str:
    statuses = {str(record.status or "").lower() for record in records}
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


def _error_count(records: list[TraceRecord]) -> int:
    return sum(1 for record in records if _record_has_error(record))


def _first_time(records: list[TraceRecord]) -> datetime | None:
    times = [_record_time(record) for record in records]
    valid_times = [value for value in times if value is not None]
    return min(valid_times) if valid_times else None


def _last_time(records: list[TraceRecord]) -> datetime | None:
    times = [_record_end_time(record) for record in records]
    valid_times = [value for value in times if value is not None]
    return max(valid_times) if valid_times else None


def _record_sort_key(record: TraceRecord) -> tuple[datetime, int, str]:
    return (
        _record_time(record) or datetime.min,
        int(record.id or 0),
        str(record.node_name or ""),
    )


def _record_time(record: TraceRecord) -> datetime | None:
    return _coerce_datetime(record.start_time) or _coerce_datetime(record.created_at)


def _record_end_time(record: TraceRecord) -> datetime | None:
    return (
        _coerce_datetime(record.end_time)
        or _coerce_datetime(record.start_time)
        or _coerce_datetime(record.created_at)
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


def _fallback_error_code(record: TraceRecord) -> str | None:
    status = str(record.status or "").lower()
    if status and status != "success":
        return f"{record.node_type}_{status}"
    return None


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


__all__ = [
    "TRACE_SUMMARY_SCHEMA_VERSION",
    "build_trace_request_summary",
    "trace_request_summary_from_mongo_doc",
    "trace_request_summary_to_mongo_doc",
]
