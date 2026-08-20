"""茬口 Service（从 archive/backend/app/domains/planting/cycle_service.py 复用）。

复用来源：archive/backend/app/domains/planting/cycle_service.py

改造点：
  - 导入路径：app.domains.planting.{crop,cycle,log,planting}_models + finance.cost_models
    → business.models；app.context.runtime → business.context_runtime；
    app.infra.repository_runtime 丢弃（trace 相关，业务 MCP 不需要）
  - 用 dict + 显式关键字参数替代 CropCycleCreate schema
  - 返回 dict 而非 ORM 对象（_crop_cycle_to_dict / _cycle_stage_to_dict），
    CropCycle 序列化包含 stages 列表和 current_stage_name
  - 保留 db: Session 第一参数；内部 db.commit()/rollback() 改为 db.flush()，
    由上层 session_scope 统一 commit；invalidate_farm_context 调用保留
  - delete_crop_cycle 移除 clear_cycle_reference 调用，保留删除
    FarmLog/CostRecord/阶段 的逻辑
  - CropTemplate.stages → CropTemplate.growth_stages（agri_backend_v2 模型关系名）
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from business.context_runtime import invalidate_farm_context
from business.services import crop_service
from business.models import (
    CostRecord,
    CropCycle,
    CropTemplate,
    CycleStage,
    FarmLog,
    PlantingUnit,
)


# ─────────────────────────────────────────────────────────────
# 序列化辅助
# ─────────────────────────────────────────────────────────────


def _cycle_stage_to_dict(stage: CycleStage) -> dict[str, Any]:
    today = date.today()
    # 动态计算 is_current：今天落在阶段日期区间内则为当前阶段
    is_current = bool(
        stage.start_date
        and stage.end_date
        and stage.start_date <= today <= stage.end_date
    )
    return {
        "id": stage.id,
        "cycle_id": stage.cycle_id,
        "name": stage.name,
        "start_date": stage.start_date.isoformat() if stage.start_date else None,
        "end_date": stage.end_date.isoformat() if stage.end_date else None,
        "order_index": stage.order_index,
        "duration_days": stage.duration_days,
        "key_tasks": stage.key_tasks,
        "is_current": is_current,
    }


def _crop_cycle_to_dict(cycle: CropCycle) -> dict[str, Any]:
    stages = sorted(cycle.stages, key=lambda s: s.order_index)
    stage_dicts = [_cycle_stage_to_dict(s) for s in stages]
    # current_stage_name：第一个动态 is_current 的阶段；无则 None
    current_stage_name = next(
        (sd["name"] for sd in stage_dicts if sd["is_current"]), None
    )
    return {
        "id": cycle.id,
        "farm_id": cycle.farm_id,
        "name": cycle.name,
        "crop_template_id": cycle.crop_template_id,
        "start_date": cycle.start_date.isoformat() if cycle.start_date else None,
        "field_name": cycle.field_name,
        "total_area_mu": float(cycle.total_area_mu)
        if cycle.total_area_mu is not None
        else None,
        "season": cycle.season,
        "batch_note": cycle.batch_note,
        "status": cycle.status,
        "created_at": cycle.created_at.isoformat() if cycle.created_at else None,
        "stages": stage_dicts,
        "current_stage_name": current_stage_name,
    }


# ─────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────


def create_crop_cycle(
    db: Session,
    *,
    farm_id: int,
    name: str,
    crop_template_id: int,
    start_date: date,
    field_name: str | None = None,
    total_area_mu: Decimal | None = None,
    season: str | None = None,
    batch_note: str | None = None,
    expected_crop_name: str | None = None,
) -> dict[str, Any]:
    """创建茬口及其阶段，按模板阶段顺序推算日期。

    is_current 推断：阶段日期区间包含今天则标记为当前阶段
    （_recalculate_stages 同样遵循此规则）。
    """
    template = (
        db.query(CropTemplate)
        .filter(
            CropTemplate.id == crop_template_id,
            CropTemplate.farm_id == farm_id,
        )
        .first()
    )
    if not template:
        system_template = (
            db.query(CropTemplate)
            .filter(
                CropTemplate.id == crop_template_id,
                CropTemplate.farm_id.is_(None),
            )
            .first()
        )
        if system_template is not None:
            raise ValueError(
                "system_template_not_imported: "
                f"系统模板 {crop_template_id} 必须先导入当前农场"
            )
        raise ValueError("Crop template not found")
    if expected_crop_name is not None and crop_service.normalize_crop_name(
        template.name
    ) != crop_service.normalize_crop_name(expected_crop_name):
        raise ValueError(
            "crop_template_mismatch: "
            f"目标作物 {expected_crop_name!r} 与模板 {template.name!r} 不一致"
        )

    db_cycle = CropCycle(
        name=name,
        crop_template_id=crop_template_id,
        start_date=start_date,
        field_name=field_name,
        total_area_mu=total_area_mu,
        season=season,
        batch_note=batch_note,
        farm_id=farm_id,
    )
    db.add(db_cycle)
    db.flush()

    current_date = start_date
    stages = sorted(template.growth_stages, key=lambda s: s.order_index)

    today = date.today()
    for stage in stages:
        end_date = current_date + timedelta(days=stage.duration_days - 1)
        db.add(
            CycleStage(
                cycle_id=db_cycle.id,
                name=stage.name,
                start_date=current_date,
                end_date=end_date,
                order_index=stage.order_index,
                duration_days=stage.duration_days,
                key_tasks=stage.key_tasks,
                is_current=1 if current_date <= today <= end_date else 0,
            )
        )
        current_date = end_date + timedelta(days=1)

    db.flush()
    db.refresh(db_cycle, attribute_names=["stages"])
    invalidate_farm_context(farm_id)
    return _crop_cycle_to_dict(db_cycle)


def get_crop_cycles(
    db: Session,
    farm_id: int,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """获取指定农场的茬口列表（分页）。"""
    query = db.query(CropCycle).filter(CropCycle.farm_id == farm_id)
    if status is not None:
        query = query.filter(CropCycle.status == status)
    cycles = query.offset(skip).limit(limit).all()
    return [_crop_cycle_to_dict(c) for c in cycles]


def count_crop_cycles(db: Session, farm_id: int, status: str | None = None) -> int:
    """获取指定农场的茬口总数。"""
    query = db.query(CropCycle).filter(CropCycle.farm_id == farm_id)
    if status is not None:
        query = query.filter(CropCycle.status == status)
    return query.count()


def get_crop_cycle(db: Session, cycle_id: int, farm_id: int) -> dict[str, Any] | None:
    """根据 ID 获取指定农场的单个茬口。"""
    cycle = _load_crop_cycle_orm(db, cycle_id, farm_id)
    return _crop_cycle_to_dict(cycle) if cycle else None


def _load_crop_cycle_orm(db: Session, cycle_id: int, farm_id: int) -> CropCycle | None:
    """按 ID + farm_id 加载 ORM 茬口（供 update/delete/advance 复用）。"""
    return (
        db.query(CropCycle)
        .filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id)
        .first()
    )


def update_stage(
    db: Session,
    stage_id: int,
    duration_days: int | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """更新阶段信息，若修改 duration_days 则重新推算后续阶段日期。"""
    stage = db.query(CycleStage).filter(CycleStage.id == stage_id).first()
    if not stage:
        raise ValueError("Stage not found")
    farm_id = stage.cycle.farm_id if stage.cycle else None
    if farm_id is None:
        cycle = db.query(CropCycle).filter(CropCycle.id == stage.cycle_id).first()
        if not cycle:
            raise ValueError("Cycle not found")
        farm_id = cycle.farm_id

    if name is not None:
        stage.name = name
    if duration_days is not None:
        stage.duration_days = duration_days
        _recalculate_stages(db, stage.cycle_id)

    db.flush()
    invalidate_farm_context(farm_id)
    return _cycle_stage_to_dict(stage)


def _recalculate_stages(db: Session, cycle_id: int) -> None:
    """重新计算指定茬口下所有阶段的起止日期。"""
    cycle = db.query(CropCycle).filter(CropCycle.id == cycle_id).first()
    if not cycle:
        raise ValueError("Cycle not found")
    stages = sorted(cycle.stages, key=lambda s: s.order_index)
    current_date = cycle.start_date

    today = date.today()
    for stage in stages:
        stage.start_date = current_date
        stage.end_date = current_date + timedelta(days=stage.duration_days - 1)
        stage.is_current = 1 if stage.start_date <= today <= stage.end_date else 0
        current_date = stage.end_date + timedelta(days=1)


def update_crop_cycle(
    db: Session,
    cycle_id: int,
    *,
    farm_id: int,
    name: str,
    crop_template_id: int,
    start_date: date,
    field_name: str | None = None,
    total_area_mu: Decimal | None = None,
    season: str | None = None,
    batch_note: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """更新茬口基本信息。"""
    cycle = _load_crop_cycle_orm(db, cycle_id, farm_id)
    if not cycle:
        raise ValueError(f"茬口 {cycle_id} 不存在")

    cycle.name = name
    cycle.crop_template_id = crop_template_id
    cycle.start_date = start_date
    cycle.field_name = field_name
    cycle.total_area_mu = total_area_mu
    cycle.season = season
    cycle.batch_note = batch_note
    if status is not None:
        cycle.status = status

    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(cycle, attribute_names=["stages"])
    return _crop_cycle_to_dict(cycle)


def delete_crop_cycle(db: Session, cycle_id: int, farm_id: int) -> None:
    """删除茬口及其所有阶段、关联的农事日志、成本记录。"""
    cycle = _load_crop_cycle_orm(db, cycle_id, farm_id)
    if not cycle:
        raise ValueError(f"茬口 {cycle_id} 不存在")

    db.query(FarmLog).filter(FarmLog.cycle_id == cycle_id).delete(
        synchronize_session=False
    )
    db.query(CostRecord).filter(CostRecord.cycle_id == cycle_id).delete(
        synchronize_session=False
    )
    db.flush()

    for stage in list(cycle.stages):
        db.delete(stage)
    db.delete(cycle)
    db.flush()
    invalidate_farm_context(farm_id)


def advance_stage(db: Session, cycle_id: int, farm_id: int) -> dict[str, Any]:
    """推进茬口到下一个阶段。"""
    cycle = _load_crop_cycle_orm(db, cycle_id, farm_id)
    if not cycle:
        raise ValueError(f"茬口 {cycle_id} 不存在")

    stages = sorted(cycle.stages, key=lambda s: s.order_index)
    current_idx = next((i for i, s in enumerate(stages) if s.is_current), None)
    if current_idx is None:
        if stages:
            stages[0].is_current = 1
    elif current_idx < len(stages) - 1:
        stages[current_idx].is_current = 0
        stages[current_idx + 1].is_current = 1
    else:
        raise ValueError("已经是最后一个阶段，无法推进")

    db.flush()
    invalidate_farm_context(farm_id)
    db.refresh(cycle, attribute_names=["stages"])
    return _crop_cycle_to_dict(cycle)


def get_cycle_unit_stats(
    db: Session, cycle_ids: list[int], farm_id: int
) -> dict[int, dict]:
    """按批次汇总种植单元数量和面积。"""
    if not cycle_ids:
        return {}
    rows = (
        db.query(
            PlantingUnit.cycle_id,
            func.count(PlantingUnit.id),
            func.sum(PlantingUnit.area_mu),
        )
        .filter(PlantingUnit.farm_id == farm_id, PlantingUnit.cycle_id.in_(cycle_ids))
        .group_by(PlantingUnit.cycle_id)
        .all()
    )
    return {
        cycle_id: {"unit_count": count or 0, "unit_area_mu": area}
        for cycle_id, count, area in rows
    }


__all__ = [
    "create_crop_cycle",
    "get_crop_cycles",
    "count_crop_cycles",
    "get_crop_cycle",
    "update_stage",
    "_recalculate_stages",
    "update_crop_cycle",
    "delete_crop_cycle",
    "advance_stage",
    "get_cycle_unit_stats",
]
