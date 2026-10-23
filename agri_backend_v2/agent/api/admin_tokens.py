"""管理员 Token 统计：北京时间、真实 Trace usage、最多查询一个季度。"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query

from agent.api import api_router
from agent.auth import parse_identity, require_identity_permission
from agent.platforms.persistence.mongo import token_stats
from shared.roles import Permission
from shared.time import beijing_today


def admin_identity(authorization: str | None = Header(default=None)):
    """跨用户统计必须经过管理员权限检查。"""
    return require_identity_permission(
        parse_identity(authorization), Permission.ADMIN_DEBUG
    )


async def query_usage(start: date, end: date, user_id: str | None, model: str | None):
    """限制查询范围，并将存储错误转换为不泄露连接信息的响应。"""
    if end < start or (end - start).days >= token_stats.MAX_RANGE_DAYS:
        raise HTTPException(
            422,
            {
                "code": "invalid_date_range",
                "message": "日期范围须为 1 至 93 天",
                "meta": {"start_date": str(start), "end_date": str(end)},
            },
        )
    try:
        return await token_stats.hourly_usage(start, end, user_id, model)
    except token_stats.TokenStatsUnavailable as exc:
        raise HTTPException(
            503,
            {
                "code": "token_stats_unavailable",
                "message": "Token 统计存储暂不可用",
                "meta": {"source": "trace"},
            },
        ) from exc


@api_router.get("/admin/stats/tokens", dependencies=[Depends(admin_identity)])
async def summary(
    days: int = Query(default=7, ge=1, le=token_stats.MAX_RANGE_DAYS),
    user_id: str | None = None,
    model: str | None = None,
):
    """返回最近 N 个北京时间自然日的模型用量。"""
    end = beijing_today()
    items = await query_usage(end - timedelta(days=days - 1), end, user_id, model)
    return {"days": days, **token_stats.summarize(items)}


@api_router.get("/admin/stats/tokens/daily", dependencies=[Depends(admin_identity)])
async def daily(
    date: Annotated[date, Query()], user_id: str | None = None, model: str | None = None
):
    """按模型汇总指定自然日，保持页面现有契约。"""
    items = await query_usage(date, date, user_id, model)
    return {
        "date": str(date),
        "items": list(token_stats.summarize(items)["by_model"].values()),
    }


@api_router.get("/admin/stats/tokens/hourly", dependencies=[Depends(admin_identity)])
async def hourly(
    start_date: date | None = None,
    end_date: date | None = None,
    user_id: str | None = None,
    model: str | None = None,
):
    """返回日期、小时、用户、模型四个维度的统计。"""
    end = end_date or beijing_today()
    start = start_date or end
    items = await query_usage(start, end, user_id, model)
    totals = token_stats.summarize(items)
    return {
        "start_date": str(start),
        "end_date": str(end),
        "items": items,
        "hours": [f"{hour:02}" for hour in range(24)],
        "total_tokens": totals["total_tokens"],
        "total_requests": totals["total_requests"],
    }
