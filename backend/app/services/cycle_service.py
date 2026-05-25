from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.crop import CropTemplate
from app.models.cycle import CropCycle, CycleStage
from app.schemas.cycle import CropCycleCreate


def create_crop_cycle(db: Session, cycle: CropCycleCreate, farm_id: int) -> CropCycle:
    """创建茬口及其阶段，按模板阶段顺序推算日期。"""
    template = db.query(CropTemplate).filter(CropTemplate.id == cycle.crop_template_id, CropTemplate.farm_id == farm_id).first()
    if not template:
        raise ValueError("Crop template not found")

    db_cycle = CropCycle(
        name=cycle.name,
        crop_template_id=cycle.crop_template_id,
        start_date=cycle.start_date,
        field_name=cycle.field_name,
        farm_id=farm_id,
    )
    db.add(db_cycle)
    db.flush()

    current_date = cycle.start_date
    stages = sorted(template.stages, key=lambda s: s.order_index)

    for idx, stage in enumerate(stages):
        end_date = current_date + timedelta(days=stage.duration_days - 1)
        db_stage = CycleStage(
            cycle_id=db_cycle.id,
            name=stage.name,
            start_date=current_date,
            end_date=end_date,
            order_index=stage.order_index,
            duration_days=stage.duration_days,
            key_tasks=stage.key_tasks,
            is_current=1 if idx == 0 else 0,
        )
        db.add(db_stage)
        current_date = end_date + timedelta(days=1)

    try:
        db.commit()
        db.refresh(db_cycle)
    except Exception:
        db.rollback()
        raise
    return db_cycle


def get_crop_cycles(
    db: Session, farm_id: int, skip: int = 0, limit: int = 100
) -> list[CropCycle]:
    """获取指定农场的茬口列表（分页）。"""
    return (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_crop_cycles(db: Session, farm_id: int) -> int:
    """获取指定农场的茬口总数。"""
    return db.query(CropCycle).filter(CropCycle.farm_id == farm_id).count()


def get_crop_cycle(db: Session, cycle_id: int, farm_id: int) -> CropCycle | None:
    """根据 ID 获取指定农场的单个茬口。"""
    return db.query(CropCycle).filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id).first()


def update_stage(
    db: Session,
    stage_id: int,
    duration_days: int | None = None,
    name: str | None = None,
) -> CycleStage:
    """更新阶段信息，若修改 duration_days 则重新推算后续阶段日期。"""
    stage = db.query(CycleStage).filter(CycleStage.id == stage_id).first()
    if not stage:
        raise ValueError("Stage not found")

    if name is not None:
        stage.name = name
    if duration_days is not None:
        stage.duration_days = duration_days
        _recalculate_stages(db, stage.cycle_id)

    try:
        db.commit()
        db.refresh(stage)
    except Exception:
        db.rollback()
        raise
    return stage


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

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def update_crop_cycle(
    db: Session, cycle_id: int, update: CropCycleCreate, farm_id: int
) -> CropCycle:
    """更新茬口基本信息。"""
    cycle = get_crop_cycle(db, cycle_id, farm_id)
    if not cycle:
        raise ValueError(f"茬口 {cycle_id} 不存在")

    cycle.name = update.name
    cycle.crop_template_id = update.crop_template_id
    cycle.start_date = update.start_date
    cycle.field_name = update.field_name

    try:
        db.commit()
        db.refresh(cycle)
    except Exception:
        db.rollback()
        raise
    return cycle


def delete_crop_cycle(db: Session, cycle_id: int, farm_id: int) -> None:
    """删除茬口及其所有阶段。"""
    cycle = get_crop_cycle(db, cycle_id, farm_id)
    if not cycle:
        raise ValueError(f"茬口 {cycle_id} 不存在")

    for stage in cycle.stages:
        db.delete(stage)
    db.delete(cycle)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def advance_stage(db: Session, cycle_id: int, farm_id: int) -> CropCycle:
    """推进茬口到下一个阶段。"""
    cycle = get_crop_cycle(db, cycle_id, farm_id)
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

    try:
        db.commit()
        db.refresh(cycle)
    except Exception:
        db.rollback()
        raise
    return cycle


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
]
