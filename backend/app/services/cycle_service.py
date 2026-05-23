from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.crop import CropTemplate
from app.models.cycle import CropCycle, CycleStage
from app.schemas.cycle import CropCycleCreate


def create_crop_cycle(db: Session, cycle: CropCycleCreate) -> CropCycle:
    """创建茬口及其阶段，按模板阶段顺序推算日期。"""
    template = db.query(CropTemplate).filter(CropTemplate.id == cycle.crop_template_id).first()
    if not template:
        raise ValueError("Crop template not found")

    db_cycle = CropCycle(
        name=cycle.name,
        crop_template_id=cycle.crop_template_id,
        start_date=cycle.start_date,
        field_name=cycle.field_name,
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

    db.commit()
    db.refresh(db_cycle)
    return db_cycle


def get_crop_cycles(db: Session) -> list[CropCycle]:
    """获取所有茬口。"""
    return db.query(CropCycle).all()


def get_crop_cycle(db: Session, cycle_id: int) -> CropCycle | None:
    """根据 ID 获取单个茬口。"""
    return db.query(CropCycle).filter(CropCycle.id == cycle_id).first()


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

    db.commit()
    db.refresh(stage)
    return stage


def _recalculate_stages(db: Session, cycle_id: int) -> None:
    """重新计算指定茬口下所有阶段的起止日期。"""
    cycle = db.query(CropCycle).filter(CropCycle.id == cycle_id).first()
    stages = sorted(cycle.stages, key=lambda s: s.order_index)
    current_date = cycle.start_date

    today = date.today()
    for stage in stages:
        stage.start_date = current_date
        stage.end_date = current_date + timedelta(days=stage.duration_days - 1)
        stage.is_current = 1 if stage.start_date <= today <= stage.end_date else 0
        current_date = stage.end_date + timedelta(days=1)

    db.commit()


__all__ = [
    "create_crop_cycle",
    "get_crop_cycles",
    "get_crop_cycle",
    "update_stage",
    "_recalculate_stages",
]
