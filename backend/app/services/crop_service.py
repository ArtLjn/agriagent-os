import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.infra.repository_runtime import (
    get_agent_record_repository,
    run_maybe_awaitable,
)
from app.models.cost import CostRecord
from app.models.crop import CropTemplate, GrowthStage
from app.models.cycle import CropCycle
from app.models.log import FarmLog
from app.schemas.crop import CropTemplateCreate


@dataclass(frozen=True)
class ImportSystemTemplateResult:
    """系统模板导入结果。"""

    template_id: int
    already_exists: bool


def _normalize_key_tasks(key_tasks: str | None) -> str | None:
    if key_tasks is None:
        return None
    return re.sub(r"\s+", " ", key_tasks.strip())


def _stage_compare_value(stage: Any) -> tuple[str, int, str | None]:
    return (
        getattr(stage, "name"),
        getattr(stage, "duration_days"),
        _normalize_key_tasks(getattr(stage, "key_tasks", None)),
    )


def _normalize_stages_for_compare(
    stages: Iterable[Any],
) -> tuple[tuple[str, int, str | None], ...]:
    """规范化阶段内容，顺序无关但保留重复阶段数量。"""
    stage_counts = Counter(_stage_compare_value(stage) for stage in stages)
    return tuple(sorted(stage_counts.elements()))


def find_exact_duplicate(
    db: Session,
    farm_id: int,
    name: str,
    variety: str | None,
    stages: Iterable[Any],
) -> CropTemplate | None:
    """按 name、variety 和规范化 stages 查找完全重复的用户模板。"""
    query = db.query(CropTemplate).filter(
        CropTemplate.farm_id == farm_id,
        CropTemplate.name == name,
    )
    if variety is None:
        query = query.filter(CropTemplate.variety.is_(None))
    else:
        query = query.filter(CropTemplate.variety == variety)

    expected_stages = _normalize_stages_for_compare(stages)
    for candidate in query.all():
        if _normalize_stages_for_compare(candidate.stages) == expected_stages:
            return candidate
    return None


def find_template_by_name(
    db: Session, crop_name: str, farm_id: int
) -> CropTemplate | None:
    """根据作物名称模糊搜索模板（LIKE '%crop_name%'）。"""
    return (
        db.query(CropTemplate)
        .filter(
            CropTemplate.farm_id == farm_id,
            CropTemplate.name.ilike(f"%{crop_name}%"),
        )
        .first()
    )


def create_crop_template(
    db: Session, template: CropTemplateCreate, farm_id: int
) -> CropTemplate:
    """创建作物模板及其生长阶段。"""
    db_template = CropTemplate(
        name=template.name,
        variety=template.variety,
        category=template.category,
        farm_id=farm_id,
    )
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


def get_crop_templates(
    db: Session, farm_id: int, skip: int = 0, limit: int = 100
) -> list[CropTemplate]:
    """获取指定农场的作物模板列表（分页）。"""
    return (
        db.query(CropTemplate)
        .filter(CropTemplate.farm_id == farm_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_crop_templates(db: Session, farm_id: int) -> int:
    """获取指定农场的作物模板总数。"""
    return db.query(CropTemplate).filter(CropTemplate.farm_id == farm_id).count()


def get_crop_template(
    db: Session, template_id: int, farm_id: int
) -> CropTemplate | None:
    """根据 ID 获取指定农场的单个作物模板。"""
    return (
        db.query(CropTemplate)
        .filter(CropTemplate.id == template_id, CropTemplate.farm_id == farm_id)
        .first()
    )


def list_system_templates(
    db: Session, category: str | None = None
) -> list[CropTemplate]:
    """获取系统作物模板，可按分类筛选。"""
    query = db.query(CropTemplate).filter(CropTemplate.farm_id.is_(None))
    if category is not None:
        query = query.filter(CropTemplate.category == category)
    return query.all()


def get_system_template(db: Session, template_id: int) -> CropTemplate | None:
    """根据 ID 获取系统模板。"""
    return _system_template_query(db, template_id).first()


def find_system_template_match(
    db: Session, name: str, variety: str | None
) -> CropTemplate | None:
    """按 name 和 variety 精确匹配系统模板。"""
    query = db.query(CropTemplate).filter(
        CropTemplate.farm_id.is_(None),
        CropTemplate.name == name,
    )
    if variety is None:
        query = query.filter(CropTemplate.variety.is_(None))
    else:
        query = query.filter(CropTemplate.variety == variety)
    return query.first()


def import_system_template(
    db: Session, system_template_id: int, farm_id: int
) -> ImportSystemTemplateResult:
    """将系统模板深拷贝到指定农场，重复时返回已有模板 ID。"""
    system_template = (
        _system_template_query(db, system_template_id).with_for_update().first()
    )
    if system_template is None:
        raise ValueError(f"系统模板 {system_template_id} 不存在")

    duplicate = find_exact_duplicate(
        db,
        farm_id=farm_id,
        name=system_template.name,
        variety=system_template.variety,
        stages=system_template.stages,
    )
    if duplicate is not None:
        return ImportSystemTemplateResult(template_id=duplicate.id, already_exists=True)

    imported = CropTemplate(
        farm_id=farm_id,
        name=system_template.name,
        variety=system_template.variety,
        category=system_template.category,
    )
    db.add(imported)
    db.flush()

    for stage in system_template.stages:
        db.add(
            GrowthStage(
                crop_template_id=imported.id,
                name=stage.name,
                duration_days=stage.duration_days,
                order_index=stage.order_index,
                key_tasks=stage.key_tasks,
            )
        )

    try:
        db.commit()
        db.refresh(imported)
    except Exception:
        db.rollback()
        raise
    return ImportSystemTemplateResult(template_id=imported.id, already_exists=False)


def _system_template_query(db: Session, template_id: int):
    return db.query(CropTemplate).filter(
        CropTemplate.id == template_id,
        CropTemplate.farm_id.is_(None),
    )


def create_system_crop_template(
    db: Session, template: CropTemplateCreate
) -> CropTemplate:
    """创建系统作物模板（farm_id 为空）。"""
    db_template = CropTemplate(
        farm_id=None,
        name=template.name,
        variety=template.variety,
        category=template.category,
    )
    db.add(db_template)
    db.flush()

    for stage in template.stages:
        db.add(
            GrowthStage(
                crop_template_id=db_template.id,
                name=stage.name,
                duration_days=stage.duration_days,
                order_index=stage.order_index,
                key_tasks=stage.key_tasks,
            )
        )

    try:
        db.commit()
        db.refresh(db_template)
    except Exception:
        db.rollback()
        raise
    return db_template


def update_system_crop_template(
    db: Session, template_id: int, update: CropTemplateCreate
) -> CropTemplate:
    """更新系统作物模板（含 stages 全量替换）。"""
    template = get_system_template(db, template_id)
    if template is None:
        raise ValueError(f"系统模板 {template_id} 不存在")

    template.name = update.name
    template.variety = update.variety
    template.category = update.category

    for stage in template.stages:
        db.delete(stage)

    for stage in update.stages:
        db.add(
            GrowthStage(
                crop_template_id=template.id,
                name=stage.name,
                duration_days=stage.duration_days,
                order_index=stage.order_index,
                key_tasks=stage.key_tasks,
            )
        )

    try:
        db.commit()
        db.refresh(template)
    except Exception:
        db.rollback()
        raise
    return template


def count_farm_template_imports(
    db: Session, name: str, variety: str | None
) -> int:
    """统计农场副本中同名同品种的模板数量，用于删除前置检查。"""
    query = db.query(CropTemplate).filter(
        CropTemplate.farm_id.is_not(None),
        CropTemplate.name == name,
    )
    if variety is None:
        query = query.filter(CropTemplate.variety.is_(None))
    else:
        query = query.filter(CropTemplate.variety == variety)
    return query.count()


def delete_system_crop_template(db: Session, template_id: int) -> None:
    """删除系统作物模板；已被农场导入时拒绝。"""
    template = get_system_template(db, template_id)
    if template is None:
        raise ValueError(f"系统模板 {template_id} 不存在")

    farm_count = count_farm_template_imports(
        db, name=template.name, variety=template.variety
    )
    if farm_count > 0:
        raise ValueError(
            f"系统模板 {template_id} 已被 {farm_count} 个农场导入，禁止删除"
        )

    for stage in template.stages:
        db.delete(stage)
    db.delete(template)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _get_any_crop_template(db: Session, template_id: int) -> CropTemplate | None:
    return db.query(CropTemplate).filter(CropTemplate.id == template_id).first()


def _raise_if_system_template(db: Session, template_id: int) -> None:
    template = _get_any_crop_template(db, template_id)
    if template is not None and template.farm_id is None:
        raise ValueError(f"系统模板 {template_id} 不允许修改")


def update_crop_template(
    db: Session, template_id: int, update: CropTemplateCreate, farm_id: int
) -> CropTemplate:
    """更新作物模板及其生长阶段。"""
    _raise_if_system_template(db, template_id)
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
    """删除作物模板及其关联的阶段、茬口、农事日志、成本记录和Agent记录。"""
    _raise_if_system_template(db, template_id)
    template = get_crop_template(db, template_id, farm_id)
    if not template:
        raise ValueError(f"模板 {template_id} 不存在")

    related_cycles = (
        db.query(CropCycle).filter(CropCycle.crop_template_id == template_id).all()
    )
    for cycle in related_cycles:
        run_maybe_awaitable(
            get_agent_record_repository(db).clear_cycle_reference(cycle_id=cycle.id)
        )
        db.query(FarmLog).filter(FarmLog.cycle_id == cycle.id).delete(
            synchronize_session=False
        )
        db.query(CostRecord).filter(CostRecord.cycle_id == cycle.id).delete(
            synchronize_session=False
        )
        for stage in cycle.stages:
            db.delete(stage)
        db.delete(cycle)
    db.flush()

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
    "count_crop_templates",
    "get_crop_template",
    "update_crop_template",
    "delete_crop_template",
    "find_template_by_name",
    "find_exact_duplicate",
    "_normalize_stages_for_compare",
    "list_system_templates",
    "get_system_template",
    "import_system_template",
    "find_system_template_match",
    "create_system_crop_template",
    "update_system_crop_template",
    "count_farm_template_imports",
    "delete_system_crop_template",
    "ImportSystemTemplateResult",
]
