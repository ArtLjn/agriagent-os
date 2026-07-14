"""Admin Trace 查询 API — 链路查询、Gantt 时间线、清理。"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.config import settings
from app.modules.auth.dependencies import require_admin
from app.evaluation.diagnostics import SkillDiagnosticService
from app.infra.mongo import get_mongo_database
from app.infra.mongo_mappers import trace_record_from_mongo_doc
from app.infra.repository_runtime import (
    get_trace_repository,
    resolve_maybe_awaitable,
)
from app.infra.trace_repository import TracePage
from app.models.trace import TraceRecord
from app.api.admin_trace_requests import (
    TraceRequestPageResponse,
    list_trace_requests_from_mongo,
    trace_request_page_from_records,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["admin-trace"],
    dependencies=[Depends(require_admin)],
)


class TimelineNode(BaseModel):
    node_type: str
    node_name: str
    duration_ms: int | None
    status: str
    token_usage: dict | None = None
    start_time: str | None = None
    error_message: str | None = None
    input_data: Any = None
    output_data: Any = None


class TimelineRound(BaseModel):
    round_index: int
    nodes: list[TimelineNode]


class TimelineResponse(BaseModel):
    request_id: str
    rounds: list[TimelineRound]


@router.get("/traces")
async def list_traces(
    request_id: str | None = Query(None),
    session_id: str | None = Query(None),
    farm_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """查询 trace 记录列表。"""
    if _trace_storage_is_mongo() or not _trace_table_exists(db):
        page = await _list_traces_from_mongo(
            request_id=request_id,
            session_id=session_id,
            farm_id=farm_id,
            limit=limit,
            offset=offset,
        )
        return _trace_page_response(page)

    if farm_id is not None:
        page = await _list_traces_from_repository(
            db,
            farm_id=farm_id,
            request_id=request_id,
            session_id=session_id,
            limit=limit,
            offset=offset,
        )
        return _trace_page_response(page)

    query = db.query(TraceRecord)
    if request_id:
        query = query.filter(TraceRecord.request_id == request_id)
    if session_id:
        query = query.filter(TraceRecord.session_id == session_id)
    if farm_id:
        query = query.filter(TraceRecord.farm_id == farm_id)

    total = query.count()
    items = (
        query.order_by(TraceRecord.created_at.desc()).offset(offset).limit(limit).all()
    )

    return _trace_page_response(TracePage(items=items, total=total))


@router.get("/traces/requests", response_model=TraceRequestPageResponse)
async def list_trace_requests(
    request_id: str | None = Query(None),
    session_id: str | None = Query(None),
    farm_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> TraceRequestPageResponse:
    """按 request 聚合 trace 列表，分页单位是一次请求而不是单个节点。"""
    if _trace_storage_is_mongo() or not _trace_table_exists(db):
        return await list_trace_requests_from_mongo(
            request_id=request_id,
            session_id=session_id,
            farm_id=farm_id,
            limit=limit,
            offset=offset,
        )

    query = db.query(TraceRecord)
    if request_id:
        query = query.filter(TraceRecord.request_id == request_id)
    if session_id:
        query = query.filter(TraceRecord.session_id == session_id)
    if farm_id is not None:
        query = query.filter(TraceRecord.farm_id == farm_id)
    records = (
        query.order_by(
            TraceRecord.start_time.desc(),
            TraceRecord.created_at.desc(),
            TraceRecord.id.desc(),
        ).all()
    )
    return trace_request_page_from_records(records, limit=limit, offset=offset)


@router.get("/traces/{request_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    request_id: str, db: Session = Depends(get_db)
) -> TimelineResponse:
    """获取某次请求的 Gantt 时间线数据。"""
    records = await _records_by_request_id(request_id, db)
    if not records:
        return TimelineResponse(request_id=request_id, rounds=[])

    rounds_map: dict[int, list[TimelineNode]] = defaultdict(list)
    for r in sorted(records, key=_trace_record_sort_key):
        rounds_map[r.round_index].append(
            TimelineNode(
                node_type=r.node_type,
                node_name=r.node_name,
                duration_ms=r.duration_ms,
                status=r.status,
                token_usage=_coerce_token_usage(r.token_usage),
                start_time=_format_datetime(r.start_time),
                error_message=r.error_message,
                input_data=r.input_data,
                output_data=r.output_data,
            )
        )

    rounds = [
        TimelineRound(round_index=idx, nodes=nodes)
        for idx, nodes in sorted(
            rounds_map.items(), key=lambda item: _round_first_node_sort_key(item[1])
        )
    ]
    return TimelineResponse(request_id=request_id, rounds=rounds)


@router.get("/traces/{request_id}/diagnostics")
async def get_trace_diagnostics(request_id: str, db: Session = Depends(get_db)) -> dict:
    """获取 Skill 诊断汇总。"""
    records = await _records_by_request_id(request_id, db)
    report = SkillDiagnosticService().build_report(request_id, records)
    return {
        "request_id": report.request_id,
        "tool_selection": report.tool_selection,
        "context_injection": report.context_injection,
        "tool_calls": report.tool_calls,
        "pending_actions": report.pending_actions,
        "pending_lifecycle": report.pending_lifecycle,
        "context_dependencies": report.context_dependencies,
        "context_dependency_diagnostic": report.context_dependency_diagnostic,
        "tool_not_called_reason": report.tool_not_called_reason,
        "pending_action_diagnostic": report.pending_action_diagnostic,
        "reflection_checks": report.reflection_checks,
        "reflection_diagnostic": report.reflection_diagnostic,
        "errors": report.errors,
        "final_response": report.final_response,
        "drilldown_links": report.drilldown_links,
    }


def _format_datetime(value: Any) -> str | None:
    """将数据库时间值统一转为 API 响应字符串。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _coerce_token_usage(value: Any) -> dict | None:
    """兼容旧数据或测试中保存为 JSON 字符串的 token_usage。"""
    if value is None or isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _trace_record_sort_key(record: TraceRecord) -> tuple[datetime, int, str]:
    """按真实发生时间排序 trace 节点，避免历史 round_index 脏数据误导 UI。"""
    occurred_at = _coerce_sort_datetime(
        getattr(record, "start_time", None)
    ) or _coerce_sort_datetime(getattr(record, "created_at", None))
    return (
        occurred_at or datetime.min,
        _coerce_sort_int(getattr(record, "id", None)),
        str(getattr(record, "node_name", "")),
    )


def _round_first_node_sort_key(nodes: list[TimelineNode]) -> tuple[datetime, str]:
    if not nodes:
        return (datetime.min, "")
    first = nodes[0]
    return (
        _coerce_sort_datetime(first.start_time) or datetime.min,
        first.node_name,
    )


def _coerce_sort_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _strip_tzinfo(value)
    if isinstance(value, str):
        try:
            return _strip_tzinfo(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def _strip_tzinfo(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)


def _coerce_sort_int(value: Any) -> int:
    return value if isinstance(value, int) else 0


async def _list_traces_from_repository(
    db: Session,
    *,
    farm_id: int,
    request_id: str | None,
    session_id: str | None,
    limit: int,
    offset: int,
) -> TracePage:
    repo = get_trace_repository(db)
    if request_id:
        rows = await resolve_maybe_awaitable(
            repo.get_by_request_id(farm_id=farm_id, request_id=request_id)
        )
        return TracePage(items=rows[offset : offset + limit], total=len(rows))
    if session_id:
        return await resolve_maybe_awaitable(
            repo.list_by_session(
                farm_id=farm_id,
                session_id=session_id,
                limit=limit,
                offset=offset,
            )
        )
    query = db.query(TraceRecord).filter(TraceRecord.farm_id == farm_id)
    total = query.count()
    items = (
        query.order_by(TraceRecord.created_at.desc()).offset(offset).limit(limit).all()
    )
    return TracePage(items=items, total=total)


async def _list_traces_from_mongo(
    *,
    request_id: str | None,
    session_id: str | None,
    farm_id: int | None,
    limit: int,
    offset: int,
) -> TracePage:
    database = get_mongo_database()
    if database is None:
        return TracePage(items=[], total=0)
    filter_doc: dict[str, Any] = {}
    if request_id:
        filter_doc["requestId"] = request_id
    if session_id:
        filter_doc["sessionId"] = session_id
    if farm_id is not None:
        filter_doc["farmId"] = farm_id
    collection = database["traceRecords"]
    total = await collection.count_documents(filter_doc)
    cursor = (
        collection.find(filter_doc)
        .sort([("createdAt", -1), ("mysqlId", -1)])
        .skip(max(offset, 0))
        .limit(max(limit, 0))
    )
    docs = await cursor.to_list(None)
    return TracePage(
        items=[trace_record_from_mongo_doc(doc) for doc in docs],
        total=total,
    )


async def _records_by_request_id(request_id: str, db: Session) -> list[TraceRecord]:
    if _trace_storage_is_mongo() or not _trace_table_exists(db):
        database = get_mongo_database()
        if database is None:
            return []
        cursor = (
            database["traceRecords"]
            .find({"requestId": request_id})
            .sort([("startTime", 1), ("createdAt", 1), ("mysqlId", 1)])
        )
        docs = await cursor.to_list(None)
        return [trace_record_from_mongo_doc(doc) for doc in docs]
    return (
        db.query(TraceRecord)
        .filter(TraceRecord.request_id == request_id)
        .order_by(TraceRecord.start_time, TraceRecord.created_at, TraceRecord.id)
        .all()
    )


def _trace_page_response(page: TracePage) -> dict[str, Any]:
    return {
        "items": [
            {
                "id": r.id,
                "request_id": r.request_id,
                "session_id": r.session_id,
                "farm_id": r.farm_id,
                "round_index": r.round_index,
                "node_type": r.node_type,
                "node_name": r.node_name,
                "duration_ms": r.duration_ms,
                "status": r.status,
                "token_usage": r.token_usage,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in page.items
        ],
        "total": page.total,
    }


@router.get("/traces/{request_id}/nodes/{node_id}")
async def get_node_detail(
    request_id: str, node_id: int, db: Session = Depends(get_db)
) -> dict:
    """获取节点详情（完整 input/output）。"""
    record = await _node_by_request_and_id(request_id, node_id, db)
    if not record:
        return {"error": "节点不存在"}
    return {
        "id": record.id,
        "request_id": record.request_id,
        "round_index": record.round_index,
        "node_type": record.node_type,
        "node_name": record.node_name,
        "input_data": record.input_data,
        "output_data": record.output_data,
        "duration_ms": record.duration_ms,
        "token_usage": record.token_usage,
        "status": record.status,
        "error_message": record.error_message,
        "start_time": record.start_time,
        "end_time": record.end_time,
    }


@router.delete("/traces")
async def delete_traces(
    before: str = Query(..., description="删除此日期之前的 trace (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> dict:
    """按日期清理历史 trace。"""
    cutoff = datetime.fromisoformat(before)
    if _trace_storage_is_mongo() or not _trace_table_exists(db):
        deleted = await _delete_mongo_traces_before(cutoff)
        logger.info("Admin 删除 Mongo trace | before=%s deleted=%d", before, deleted)
        return {"deleted": deleted}
    deleted = (
        db.query(TraceRecord)
        .filter(TraceRecord.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info("Admin 删除 trace | before=%s deleted=%d", before, deleted)
    return {"deleted": deleted}


async def _node_by_request_and_id(
    request_id: str, node_id: int, db: Session
) -> TraceRecord | None:
    if _trace_storage_is_mongo() or not _trace_table_exists(db):
        database = get_mongo_database()
        if database is None:
            return None
        doc = await database["traceRecords"].find_one(
            {"requestId": request_id, "mysqlId": node_id}
        )
        return trace_record_from_mongo_doc(doc) if doc is not None else None
    return (
        db.query(TraceRecord)
        .filter(TraceRecord.request_id == request_id, TraceRecord.id == node_id)
        .first()
    )


async def _delete_mongo_traces_before(cutoff: datetime) -> int:
    database = get_mongo_database()
    if database is None:
        return 0
    result = await database["traceRecords"].delete_many({"createdAt": {"$lt": cutoff}})
    return int(getattr(result, "deleted_count", 0) or 0)


def _trace_table_exists(db: Session) -> bool:
    try:
        bind = db.get_bind()
    except Exception:
        bind = getattr(db, "bind", None)
    if bind is None:
        return True
    try:
        return bool(sa_inspect(bind).has_table("trace_records"))
    except Exception as exc:
        logger.debug(
            "Trace 表存在性检查跳过 | code=trace_table_check_skipped error=%s",
            exc,
        )
        return True


def _trace_storage_is_mongo() -> bool:
    return settings.storage.trace == "mongo"


__all__ = ["router"]
