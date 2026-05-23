from sqlalchemy.orm import Session

from app.models.crop import CropTemplate, GrowthStage
from app.schemas.crop import CropTemplateCreate


def create_crop_template(db: Session, template: CropTemplateCreate) -> CropTemplate:
    """创建作物模板及其生长阶段。"""
    db_template = CropTemplate(name=template.name, variety=template.variety)
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

    db.commit()
    db.refresh(db_template)
    return db_template


def get_crop_templates(db: Session) -> list[CropTemplate]:
    """获取所有作物模板。"""
    return db.query(CropTemplate).all()


def get_crop_template(db: Session, template_id: int) -> CropTemplate | None:
    """根据 ID 获取单个作物模板。"""
    return db.query(CropTemplate).filter(CropTemplate.id == template_id).first()
