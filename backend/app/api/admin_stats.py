"""Admin Token 统计查询 API。"""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.token_stats import TokenDailyStats
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/stats", tags=["admin-stats"])


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


__all__ = ["router"]
