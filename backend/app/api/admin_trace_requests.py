"""Admin Trace request 级摘要分页。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.infra.mongo import get_mongo_database
from app.models.trace import TraceRecord


class TraceRequestSummary(BaseModel):
    request_id: str
    session_id: str | None = None
    farm_id: int
    node_count: int
    total_duration_ms: int
    created_at: str | None = None


class TraceRequestPageResponse(BaseModel):
    items: list[TraceRequestSummary]
    total: int


async def list_trace_requests_from_mongo(
    *,
    request_id: str | None,
    session_id: str | None,
    farm_id: int | None,
    limit: int,
    offset: int,
) -> TraceRequestPageResponse:
    database = get_mongo_database()
    if database is None:
        return TraceRequestPageResponse(items=[], total=0)
    docs = await database["traceRecords"].aggregate(
        _mongo_request_summary_pipeline(
            _mongo_trace_filter(
                request_id=request_id,
                session_id=session_id,
                farm_id=farm_id,
            ),
            limit=limit,
            offset=offset,
        )
    ).to_list(1)
    result = docs[0] if docs else {"items": [], "total": []}
    return TraceRequestPageResponse(
        items=[_summary_from_mongo_doc(doc) for doc in result.get("items", [])],
        total=_mongo_total(result),
    )


def trace_request_page_from_records(
    records: list[TraceRecord], *, limit: int, offset: int
) -> TraceRequestPageResponse:
    grouped: dict[str, TraceRequestSummary] = {}
    sort_times: dict[str, datetime] = {}
    for record in records:
        _merge_trace_record(grouped, sort_times, record)
    ordered = sorted(
        grouped.values(),
        key=lambda item: (sort_times.get(item.request_id, datetime.min), item.request_id),
        reverse=True,
    )
    start = max(offset, 0)
    return TraceRequestPageResponse(
        items=ordered[start : start + max(limit, 0)],
        total=len(ordered),
    )


def _merge_trace_record(
    grouped: dict[str, TraceRequestSummary],
    sort_times: dict[str, datetime],
    record: TraceRecord,
) -> None:
    request_id = str(record.request_id)
    item = grouped.setdefault(
        request_id,
        TraceRequestSummary(
            request_id=request_id,
            session_id=record.session_id,
            farm_id=record.farm_id,
            node_count=0,
            total_duration_ms=0,
            created_at=None,
        ),
    )
    sort_times.setdefault(request_id, datetime.min)
    item.node_count += 1
    item.total_duration_ms += record.duration_ms or 0
    occurred_at = trace_record_display_time(record)
    if occurred_at is not None and occurred_at >= sort_times[request_id]:
        sort_times[request_id] = occurred_at
        item.created_at = occurred_at.isoformat()


def trace_record_display_time(record: TraceRecord) -> datetime | None:
    for value in (
        getattr(record, "start_time", None),
        getattr(record, "created_at", None),
        getattr(record, "end_time", None),
    ):
        occurred_at = coerce_sort_datetime(value)
        if occurred_at is not None:
            return occurred_at
    return None


def coerce_sort_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return strip_tzinfo(value)
    if isinstance(value, str):
        try:
            return strip_tzinfo(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def strip_tzinfo(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)


def _mongo_trace_filter(
    *,
    request_id: str | None,
    session_id: str | None,
    farm_id: int | None,
) -> dict[str, Any]:
    filter_doc: dict[str, Any] = {}
    if request_id:
        filter_doc["requestId"] = request_id
    if session_id:
        filter_doc["sessionId"] = session_id
    if farm_id is not None:
        filter_doc["farmId"] = farm_id
    return filter_doc


def _mongo_request_summary_pipeline(
    filter_doc: dict[str, Any], *, limit: int, offset: int
) -> list[dict[str, Any]]:
    return [
        {"$match": filter_doc},
        {"$group": _mongo_request_group_stage()},
        {"$sort": {"createdAt": -1, "_id": -1}},
        {
            "$facet": {
                "items": [{"$skip": max(offset, 0)}, {"$limit": max(limit, 0)}],
                "total": [{"$count": "count"}],
            }
        },
    ]


def _mongo_request_group_stage() -> dict[str, Any]:
    return {
        "_id": "$requestId",
        "sessionId": {"$first": "$sessionId"},
        "farmId": {"$first": "$farmId"},
        "nodeCount": {"$sum": 1},
        "totalDurationMs": {"$sum": {"$ifNull": ["$durationMs", 0]}},
        "createdAt": {
            "$max": {
                "$ifNull": [
                    "$startTime",
                    {"$ifNull": ["$createdAt", "$endTime"]},
                ]
            }
        },
    }


def _summary_from_mongo_doc(doc: dict[str, Any]) -> TraceRequestSummary:
    return TraceRequestSummary(
        request_id=str(doc.get("_id") or ""),
        session_id=doc.get("sessionId"),
        farm_id=int(doc.get("farmId") or 0),
        node_count=int(doc.get("nodeCount") or 0),
        total_duration_ms=int(doc.get("totalDurationMs") or 0),
        created_at=_format_datetime(doc.get("createdAt")),
    )


def _mongo_total(result: dict[str, Any]) -> int:
    total_docs = result.get("total") or []
    return int(total_docs[0].get("count", 0)) if total_docs else 0


def _format_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
