"""Farm aggregate service — SQL 实现。

返回 farm snapshot：active crop cycles + recent logs + weather。
镜像 archive/app/domains/farm/context_service.py:build_summary，但只读 MySQL。
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from business.config import settings
from business.db import DEFAULT_FARM_ID, session_scope
from business.models import CropCycle, CycleStage, Farm, FarmLog, FarmLogWorker, Worker
from business.services import log_service, weather_service

logger = logging.getLogger(__name__)


def _load_farm(db) -> Farm:
    farm = db.get(Farm, DEFAULT_FARM_ID)
    if farm is None:
        raise RuntimeError(f"farm id={DEFAULT_FARM_ID} not found in MySQL")
    return farm


def _load_active_cycles(db) -> list[dict[str, Any]]:
    """加载 farm 下的活跃茬口，附当前阶段名。"""
    stmt = (
        select(CropCycle)
        .where(
            CropCycle.farm_id == DEFAULT_FARM_ID,
            CropCycle.status == "active",
        )
        .order_by(CropCycle.start_date.desc())
    )
    cycles = db.scalars(stmt).all()
    result = []
    for c in cycles:
        # 当前阶段：is_current=1 的 cycle_stage，否则取第一个
        stages = sorted(c.stages, key=lambda s: s.order_index)
        current_stage = next((s for s in stages if s.is_current), None) or (
            stages[-1] if stages else None
        )
        # 作物名（crop_template 关联）
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


def build_summary() -> dict:
    """Aggregate farm snapshot for agent consumption."""
    with session_scope() as db:
        farm = _load_farm(db)
        cycles = _load_active_cycles(db)

    recent_logs = log_service.query_logs(days=7, limit=5)
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
    }
