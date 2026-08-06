"""Admin Token 统计查询 API。"""

import logging
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, inspect as sa_inspect
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.infra.mongo import get_mongo_database
from app.infra.repository_runtime import run_maybe_awaitable
from app.domains.users.dependencies import require_admin
from app.domains.farm.models import Farm
from app.platforms.evaluation.token_stats_models import TokenDailyStats
from app.platforms.evaluation.trace_models import TraceRecord
from app.domains.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/stats", tags=["admin-stats"])


def _int_from_usage(usage: dict | None, key: str) -> int:
    if not usage:
        return 0
    value = usage.get(key, 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _date_value(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


@router.get("/tokens")
def token_summary(
    user_id: str | None = Query(None),
    farm_id: int | None = Query(None),
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    """近 N 天 Token 用量汇总（按 model + call_type 分组）。"""
    start_date = (date.today() - timedelta(days=days)).isoformat()

    query = db.query(
        TokenDailyStats.model,
        TokenDailyStats.call_type,
        func.sum(TokenDailyStats.prompt_tokens),
        func.sum(TokenDailyStats.completion_tokens),
        func.sum(TokenDailyStats.total_tokens),
        func.sum(TokenDailyStats.request_count),
    )
    filters = [TokenDailyStats.date >= start_date]
    if user_id is not None:
        filters.append(TokenDailyStats.user_id == user_id)
    if farm_id is not None:
        filters.append(TokenDailyStats.farm_id == farm_id)

    rows = (
        query.filter(*filters)
        .group_by(TokenDailyStats.model, TokenDailyStats.call_type)
        .all()
    )

    by_model: dict[str, dict] = {}
    total_tokens = 0
    total_requests = 0
    for model, call_type, prompt, completion, total, count in rows:
        total_tokens += total or 0
        total_requests += count or 0
        key = f"{model}:{call_type}"
        by_model[key] = {
            "model": model,
            "call_type": call_type,
            "prompt_tokens": prompt or 0,
            "completion_tokens": completion or 0,
            "total_tokens": total or 0,
            "request_count": count or 0,
        }

    return {
        "days": days,
        "total_tokens": total_tokens,
        "total_requests": total_requests,
        "by_model": by_model,
    }


@router.get("/tokens/daily")
def token_daily(
    user_id: str | None = Query(None),
    farm_id: int | None = Query(None),
    date_str: str | None = Query(None, alias="date"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    """指定日期的 Token 用量明细。"""
    target = date_str or date.today().isoformat()

    query = db.query(TokenDailyStats)
    filters = [TokenDailyStats.date == target]
    if user_id is not None:
        filters.append(TokenDailyStats.user_id == user_id)
    if farm_id is not None:
        filters.append(TokenDailyStats.farm_id == farm_id)

    rows = query.filter(*filters).all()

    return {
        "date": target,
        "items": [
            {
                "model": r.model,
                "call_type": r.call_type,
                "user_id": r.user_id,
                "farm_id": r.farm_id,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "request_count": r.request_count,
                "estimated_cost_cny": float(r.estimated_cost_cny),
            }
            for r in rows
        ],
    }


@router.get("/tokens/hourly")
def token_hourly(
    user_id: str | None = Query(None),
    farm_id: int | None = Query(None),
    model: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict:
    """按小时聚合真实 LLM Token 用量，用于监控热力图。"""
    end = date.fromisoformat(end_date) if end_date else date.today()
    start = date.fromisoformat(start_date) if start_date else end
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end + timedelta(days=1), time.min)
    if not _trace_table_exists(db):
        mongo_response = _token_hourly_from_mongo(
            db=db,
            user_id=user_id,
            farm_id=farm_id,
            model=model,
            start=start,
            end=end,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        if mongo_response["items"]:
            return mongo_response
        return _token_hourly_from_daily_stats(
            db, user_id=user_id, farm_id=farm_id, model=model, start=start, end=end
        )

    query = (
        db.query(TraceRecord, Farm.user_id.label("user_id"))
        .join(Farm, Farm.id == TraceRecord.farm_id)
        .filter(
            TraceRecord.node_type == "llm_call",
            TraceRecord.start_time >= start_dt,
            TraceRecord.start_time < end_dt,
        )
    )
    if user_id is not None:
        query = query.filter(Farm.user_id == user_id)
    if farm_id is not None:
        query = query.filter(TraceRecord.farm_id == farm_id)
    if model is not None:
        query = query.filter(TraceRecord.node_name == model)

    buckets: dict[tuple[str, str | None, int, str, str], dict] = {}
    for trace, farm_user_id in query.all():
        usage = trace.token_usage or {}
        usage_source = usage.get("usage_source")
        if usage_source not in {"provider", "usage_metadata"}:
            continue
        prompt_tokens = _int_from_usage(usage, "prompt_tokens")
        completion_tokens = _int_from_usage(usage, "completion_tokens")
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens <= 0:
            continue

        hour = trace.start_time.strftime("%H") if trace.start_time else "00"
        day = (
            trace.start_time.date().isoformat()
            if trace.start_time
            else start.isoformat()
        )
        item_key = (
            day,
            farm_user_id,
            trace.farm_id,
            trace.node_name,
            hour,
        )
        item = buckets.setdefault(
            item_key,
            {
                "date": day,
                "hour": hour,
                "user_id": farm_user_id,
                "farm_id": trace.farm_id,
                "model": trace.node_name,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "request_count": 0,
            },
        )
        item["prompt_tokens"] += prompt_tokens
        item["completion_tokens"] += completion_tokens
        item["total_tokens"] += total_tokens
        item["request_count"] += 1

    items = sorted(
        buckets.values(),
        key=lambda item: (
            item["date"],
            item["hour"],
            item["user_id"] or "",
            item["model"],
        ),
    )
    hours = sorted({item["hour"] for item in items})

    if not items:
        return _token_hourly_from_daily_stats(
            db, user_id=user_id, farm_id=farm_id, model=model, start=start, end=end
        )

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "items": items,
        "hours": hours,
        "total_tokens": sum(item["total_tokens"] for item in items),
        "total_requests": sum(item["request_count"] for item in items),
    }


def _token_hourly_from_daily_stats(
    db: Session,
    *,
    user_id: str | None,
    farm_id: int | None,
    model: str | None,
    start: date,
    end: date,
) -> dict:
    query = db.query(
        TokenDailyStats.date,
        TokenDailyStats.user_id,
        TokenDailyStats.farm_id,
        TokenDailyStats.model,
        func.sum(TokenDailyStats.prompt_tokens),
        func.sum(TokenDailyStats.completion_tokens),
        func.sum(TokenDailyStats.total_tokens),
        func.sum(TokenDailyStats.request_count),
    ).filter(TokenDailyStats.date >= start, TokenDailyStats.date <= end)
    if user_id is not None:
        query = query.filter(TokenDailyStats.user_id == user_id)
    if farm_id is not None:
        query = query.filter(TokenDailyStats.farm_id == farm_id)
    if model is not None:
        query = query.filter(TokenDailyStats.model == model)
    rows = (
        query.group_by(
            TokenDailyStats.date,
            TokenDailyStats.user_id,
            TokenDailyStats.farm_id,
            TokenDailyStats.model,
        )
        .all()
    )
    items = [_daily_stats_hourly_item(row) for row in rows]
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "items": items,
        "hours": ["00"] if items else [],
        "total_tokens": sum(item["total_tokens"] for item in items),
        "total_requests": sum(item["request_count"] for item in items),
    }


def _daily_stats_hourly_item(row) -> dict:
    row_date, row_user_id, row_farm_id, row_model, prompt, completion, total, count = row
    return {
        "date": _date_value(row_date).isoformat(),
        "hour": "00",
        "user_id": row_user_id,
        "farm_id": row_farm_id,
        "model": row_model,
        "prompt_tokens": prompt or 0,
        "completion_tokens": completion or 0,
        "total_tokens": total or 0,
        "request_count": count or 0,
    }


def _token_hourly_from_mongo(
    *,
    db: Session,
    user_id: str | None,
    farm_id: int | None,
    model: str | None,
    start: date,
    end: date,
    start_dt: datetime,
    end_dt: datetime,
) -> dict:
    database = get_mongo_database()
    if database is None:
        return _empty_hourly_response(start, end)
    farm_user_ids = _farm_user_id_map(db, user_id=user_id)
    filter_doc: dict = {
        "nodeType": "llm_call",
        "startTime": {"$gte": start_dt, "$lt": end_dt},
    }
    if farm_id is not None:
        filter_doc["farmId"] = farm_id
    if model is not None:
        filter_doc["nodeName"] = model
    cursor = database["traceRecords"].find(filter_doc).sort([("startTime", 1)])
    docs = run_maybe_awaitable(cursor.to_list(None))
    rows = []
    for doc in docs:
        doc_farm_id = doc.get("farmId")
        farm_user_id = farm_user_ids.get(doc_farm_id)
        if user_id is not None and farm_user_id != user_id:
            continue
        rows.append(
            {
                "farm_id": doc_farm_id,
                "user_id": farm_user_id,
                "model": doc.get("nodeName"),
                "start_time": doc.get("startTime"),
                "token_usage": doc.get("tokenUsage") or {},
            }
        )
    return _hourly_response_from_rows(start, end, rows)


def _hourly_response_from_rows(start: date, end: date, rows: list[dict]) -> dict:
    buckets: dict[tuple[str, str | None, int, str, str], dict] = {}
    for row in rows:
        usage = row["token_usage"] or {}
        usage_source = usage.get("usage_source")
        if usage_source not in {"provider", "usage_metadata"}:
            continue
        prompt_tokens = _int_from_usage(usage, "prompt_tokens")
        completion_tokens = _int_from_usage(usage, "completion_tokens")
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens <= 0:
            continue

        start_time = row.get("start_time")
        hour = start_time.strftime("%H") if start_time else "00"
        day = _date_value(start_time).isoformat() if start_time else start.isoformat()
        item_key = (
            day,
            row.get("user_id"),
            row.get("farm_id"),
            row.get("model"),
            hour,
        )
        item = buckets.setdefault(
            item_key,
            {
                "date": day,
                "hour": hour,
                "user_id": row.get("user_id"),
                "farm_id": row.get("farm_id"),
                "model": row.get("model"),
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "request_count": 0,
            },
        )
        item["prompt_tokens"] += prompt_tokens
        item["completion_tokens"] += completion_tokens
        item["total_tokens"] += total_tokens
        item["request_count"] += 1
    items = sorted(
        buckets.values(),
        key=lambda item: (
            item["date"],
            item["hour"],
            item["user_id"] or "",
            item["model"] or "",
        ),
    )
    hours = sorted({item["hour"] for item in items})
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "items": items,
        "hours": hours,
        "total_tokens": sum(item["total_tokens"] for item in items),
        "total_requests": sum(item["request_count"] for item in items),
    }


def _empty_hourly_response(start: date, end: date) -> dict:
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "items": [],
        "hours": [],
        "total_tokens": 0,
        "total_requests": 0,
    }


def _farm_user_id_map(db: Session, *, user_id: str | None = None) -> dict[int, str]:
    query = db.query(Farm.id, Farm.user_id)
    if user_id is not None:
        query = query.filter(Farm.user_id == user_id)
    return {farm_id: farm_user_id for farm_id, farm_user_id in query.all()}


def _trace_table_exists(db: Session) -> bool:
    try:
        return bool(sa_inspect(db.get_bind()).has_table("trace_records"))
    except Exception as exc:
        logger.debug(
            "Trace 表存在性检查跳过 | code=trace_table_check_skipped error=%s",
            exc,
        )
        return True


__all__ = ["router"]
