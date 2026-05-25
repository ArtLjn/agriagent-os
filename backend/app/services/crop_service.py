from sqlalchemy.orm import Session

from app.models.crop import CropTemplate, GrowthStage
from app.schemas.crop import CropTemplateCreate


def create_crop_template(db: Session, template: CropTemplateCreate, farm_id: int) -> CropTemplate:
    """创建作物模板及其生长阶段。"""
    db_template = CropTemplate(name=template.name, variety=template.variety, farm_id=farm_id)
    db.add(db_template)
    db.flush()

    for stage in template.stages:
        db_stage = GrowthStage(
            crop_template_id=db_template.id,
            name=stage.name,
            duration_days=stage.duration_days,
            order_index=stage.order_index,
            key_tasks=stage.key_tasks,
        )
        db.add(db_stage)

    try:
        db.commit()
        db.refresh(db_template)
    except Exception:
        db.rollback()
        raise
    return db_template


def get_crop_templates(db: Session, farm_id: int) -> list[CropTemplate]:
    """获取指定农场的所有作物模板。"""
    return db.query(CropTemplate).filter(CropTemplate.farm_id == farm_id).all()


def get_crop_template(db: Session, template_id: int, farm_id: int) -> CropTemplate | None:
    """根据 ID 获取指定农场的单个作物模板。"""
    return db.query(CropTemplate).filter(CropTemplate.id == template_id, CropTemplate.farm_id == farm_id).first()


def update_crop_template(
    db: Session, template_id: int, update: CropTemplateCreate, farm_id: int
) -> CropTemplate:
    """更新作物模板及其生长阶段。"""
    template = get_crop_template(db, template_id, farm_id)
    if not template:
        raise ValueError(f"模板 {template_id} 不存在")

    template.name = update.name
    template.variety = update.variety

    for stage in template.stages:
        db.delete(stage)

    for stage in update.stages:
        db_stage = GrowthStage(
            crop_template_id=template.id,
            name=stage.name,
            duration_days=stage.duration_days,
            order_index=stage.order_index,
            key_tasks=stage.key_tasks,
        )
        db.add(db_stage)

    try:
        db.commit()
        db.refresh(template)
    except Exception:
        db.rollback()
        raise
    return template


def delete_crop_template(db: Session, template_id: int, farm_id: int) -> None:
    """删除作物模板及其关联的阶段。"""
    template = get_crop_template(db, template_id, farm_id)
    if not template:
        raise ValueError(f"模板 {template_id} 不存在")

    for stage in template.stages:
        db.delete(stage)
    db.delete(template)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


__all__ = [
    "create_crop_template",
    "get_crop_templates",
    "get_crop_template",
    "update_crop_template",
    "delete_crop_template",
]
