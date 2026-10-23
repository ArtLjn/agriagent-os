"""从已持久化的 LLM Trace 聚合实际用量，不把父节点摘要重复计费。"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from agent.config import settings
from agent.platforms.persistence.mongo.chat_store import get_collection
from shared.time import BEIJING_TZ

MAX_RANGE_DAYS = 93
QUERY_TIMEOUT_MS = 15000
TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


class TokenStatsUnavailable(Exception):
    """Trace 存储不可用，调用方不能将其解释为零用量。"""


def build_pipeline(
    start: date, end: date, user_id: str | None, model: str | None
) -> list[dict]:
    """按北京时间自然日过滤 UTC 时间，只统计提供 usage 的 LLM 调用。"""
    match: dict[str, Any] = {
        "node_type": "llm_call",
        "token_usage": {"$type": "object"},
        "created_at": {
            "$gte": datetime.combine(start, time.min, BEIJING_TZ).astimezone(
                UTC
            ),
            "$lt": datetime.combine(
                end + timedelta(days=1), time.min, BEIJING_TZ
            ).astimezone(UTC),
        },
    }
    if user_id:
        match["user_id"] = user_id
    if model:
        match["node_name"] = model
    group: dict[str, Any] = {
        "_id": {
            "date": {
                "$dateToString": {
                    "format": "%Y-%m-%d",
                    "date": "$created_at",
                    "timezone": str(BEIJING_TZ),
                }
            },
            "hour": {
                "$dateToString": {
                    "format": "%H",
                    "date": "$created_at",
                    "timezone": str(BEIJING_TZ),
                }
            },
            "user_id": "$user_id",
            "model": "$node_name",
        },
        "request_count": {"$sum": 1},
    }
    for field in TOKEN_FIELDS:
        group[field] = {"$sum": {"$ifNull": [f"$token_usage.{field}", 0]}}
    return [
        {"$match": match},
        {"$group": group},
        {"$sort": {"_id.date": 1, "_id.hour": 1}},
    ]


async def hourly_usage(
    start: date, end: date, user_id: str | None, model: str | None
) -> list[dict]:
    """在数据库端聚合，避免把完整 Trace 内容加载进管理端。"""
    try:
        collection = get_collection() if settings.mongodb.enabled else None
        if collection is None:
            raise TokenStatsUnavailable()
        traces = collection.database[
            settings.mongodb.collections.get("trace_records", "traceRecords")
        ]
        cursor = traces.aggregate(
            build_pipeline(start, end, user_id, model), maxTimeMS=QUERY_TIMEOUT_MS
        )
        return [{**row.pop("_id"), **row} async for row in cursor]
    except Exception as exc:
        raise TokenStatsUnavailable() from exc


def summarize(items: list[dict]) -> dict:
    """同一模型跨用户和小时合并；请求数表示有 usage 的模型调用次数。"""
    models: dict[str, dict] = {}
    for item in items:
        model = item.get("model") or "unknown"
        row = models.setdefault(
            model,
            {
                "model": model,
                "call_type": "llm_call",
                **dict.fromkeys((*TOKEN_FIELDS, "request_count"), 0),
            },
        )
        for field in (*TOKEN_FIELDS, "request_count"):
            row[field] += item[field]
    return {
        "by_model": models,
        "total_tokens": sum(row["total_tokens"] for row in models.values()),
        "total_requests": sum(row["request_count"] for row in models.values()),
    }
