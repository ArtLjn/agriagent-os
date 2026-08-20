"""Farm aggregate service — SQL 实现。

返回 farm snapshot：active crop cycles + recent logs + weather + 工人/成本摘要。
镜像 archive/app/domains/farm/context_service.py:build_summary，但返回结构化 dict
（archive 返回自然语言文本供 prompt 使用，agri_backend_v2 供 MCP 工具和 REST 接口使用）。

改造点（相比 agri_backend_v2 早期版本）：
  - 接受 farm_id 参数，移除 DEFAULT_FARM_ID 全局变量依赖
  - 复用 archive 的 _get_current_stage / _format_amount 等辅助函数
  - 增加 workers_summary 和 cost_summary 字段（对应 API spec 的 GET /farms/{id}/status）
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import extract, func
from sqlalchemy.orm import Session, selectinload

from business.db import session_scope
from business.models import (
    CostRecord,
    CropCycle,
    CycleStage,
    Farm,
    FarmLog,
    FarmLogWorker,
    LaborEntry,
    OperationWorkOrder,
    Worker,
)
from business.services import log_service, weather_service

logger = logging.getLogger(__name__)


def _load_farm(db: Session, farm_id: int) -> Farm:
    """加载农场，不存在则抛错。"""
    farm = db.get(Farm, farm_id)
    if farm is None:
        raise ValueError(f"farm id={farm_id} not found in MySQL")
    return farm


def _get_current_stage(cycle: CropCycle) -> CycleStage | None:
    """获取茬口的当前阶段。

    推断优先级：
    1. is_current=1 且今天落在该 stage 区间内
    2. 今天落在某 stage 区间内
    3. 都不满足 → 返回 None
    """
    if not cycle.stages:
        return None
    today = date.today()
    sorted_stages = sorted(cycle.stages, key=lambda s: s.order_index)

    for stage in sorted_stages:
        if stage.is_current == 1 and _stage_contains(stage, today):
            return stage

    for stage in sorted_stages:
        if _stage_contains(stage, today):
            return stage

    return None


def _stage_contains(stage: CycleStage, today: date) -> bool:
    """判断 today 是否落在 stage 的 [start_date, end_date] 区间内。"""
    start = stage.start_date
    end = stage.end_date
    if start is None or end is None:
        return False
    try:
        return start <= today <= end
    except TypeError:
        return False


def _load_active_cycles(db: Session, farm_id: int) -> list[dict[str, Any]]:
    """加载 farm 下的活跃茬口，附当前阶段名。"""
    stmt = (
        # 使用 select 风格，与 archive 一致
        db.query(CropCycle)
        .filter(
            CropCycle.farm_id == farm_id,
            CropCycle.status == "active",
        )
        .order_by(CropCycle.start_date.desc())
    )
    cycles = stmt.all()
    result = []
    for c in cycles:
        current_stage = _get_current_stage(c)
        ct = c.crop_template
        crop_name = ct.name if ct else "未知作物"
        variety = ct.variety if ct else None
        result.append(
            {
                "cycle_id": c.id,
                "crop_template_id": c.crop_template_id,
                "crop": f"{crop_name}({variety})" if variety else crop_name,
                "area_mu": float(c.total_area_mu) if c.total_area_mu else None,
                "current_stage": current_stage.name if current_stage else None,
                "start_date": c.start_date.isoformat() if c.start_date else None,
                "field_name": c.field_name,
                "status": c.status,
            }
        )
    return result


def _load_workers_summary(db: Session, farm_id: int) -> dict[str, Any]:
    """加载工人概览：总数、活跃数、未结工资总额。"""
    total = (
        db.query(func.count(Worker.id))
        .filter(Worker.farm_id == farm_id)
        .scalar()
        or 0
    )
    active = (
        db.query(func.count(Worker.id))
        .filter(Worker.farm_id == farm_id, Worker.status == "active")
        .scalar()
        or 0
    )
    unsettled = (
        db.query(func.sum(LaborEntry.unpaid_amount))
        .filter(
            LaborEntry.farm_id == farm_id,
            LaborEntry.unpaid_amount > 0,
        )
        .scalar()
        or 0
    )
    return {
        "total": int(total),
        "active": int(active),
        "unsettled_wages": float(unsettled),
    }


def _load_cost_summary(db: Session, farm_id: int) -> dict[str, Any]:
    """加载月度收支摘要。"""
    today = date.today()
    month_cost = (
        db.query(func.sum(CostRecord.amount))
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.record_type == "cost",
            CostRecord.deleted_at.is_(None),
            extract("year", CostRecord.record_date) == today.year,
            extract("month", CostRecord.record_date) == today.month,
        )
        .scalar()
        or 0
    )
    month_income = (
        db.query(func.sum(CostRecord.amount))
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.record_type == "income",
            CostRecord.deleted_at.is_(None),
            extract("year", CostRecord.record_date) == today.year,
            extract("month", CostRecord.record_date) == today.month,
        )
        .scalar()
        or 0
    )
    year_cost = (
        db.query(func.sum(CostRecord.amount))
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.record_type == "cost",
            CostRecord.deleted_at.is_(None),
            extract("year", CostRecord.record_date) == today.year,
        )
        .scalar()
        or 0
    )
    year_income = (
        db.query(func.sum(CostRecord.amount))
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.record_type == "income",
            CostRecord.deleted_at.is_(None),
            extract("year", CostRecord.record_date) == today.year,
        )
        .scalar()
        or 0
    )
    return {
        "month_income": float(month_income),
        "month_cost": float(month_cost),
        "year_profit": float(year_income) - float(year_cost),
    }


def build_summary(farm_id: int) -> dict:
    """Aggregate farm snapshot for agent consumption.

    Args:
        farm_id: 农场 ID（由 MCP 工具的 X-Farm-Id header 或 REST 的 JWT payload 注入）

    Returns:
        {
            "farm_id", "name", "location", "today",
            "active_cycles": [...],
            "recent_logs_count", "recent_logs_preview": [...],
            "weather_today": {...},
            "workers_summary": {...},
            "cost_summary": {...}
        }
    """
    with session_scope() as db:
        farm = _load_farm(db, farm_id)
        cycles = _load_active_cycles(db, farm_id)
        workers_summary = _load_workers_summary(db, farm_id)
        cost_summary = _load_cost_summary(db, farm_id)

    # log_service.query_logs 已支持 farm_id（agri_backend_v2 早期版本用 DEFAULT_FARM_ID，需改造）
    recent_logs = log_service.query_logs(farm_id=farm_id, days=7, limit=5)
    weather = weather_service.fetch_weather(
        location=farm.location or "苏州",
        lat=None,
        lon=None,
        days=3,
    )
    return {
        "farm_id": farm.id,
        "name": farm.name,
        "location": farm.location,
        "today": date.today().isoformat(),
        "active_cycles": cycles,
        "recent_logs_count": recent_logs["count"],
        "recent_logs_preview": recent_logs["logs"][:3],
        "weather_today": weather["daily"][0] if weather.get("daily") else None,
        "workers_summary": workers_summary,
        "cost_summary": cost_summary,
    }


def build_summary_by_user(user_id: str) -> dict | None:
    """通过 user_id 查询农场并返回 snapshot。

    用于 agent 侧已知 user_id 但未解析 farm_id 的场景。
    """
    from business.services import farm_crud_service

    with session_scope() as db:
        farm = farm_crud_service.get_farm_by_user_id(db, user_id=user_id)
        if farm is None:
            return None
        farm_id = farm.id
    return build_summary(farm_id)
