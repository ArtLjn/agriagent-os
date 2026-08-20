"""作物模板 Service（从 archive/backend/app/domains/planting/crop_service.py 复用）。

复用来源：archive/backend/app/domains/planting/crop_service.py

改造点：
  - 导入路径：app.domains.planting.{crop,cycle,log}_models + finance.cost_models
    → business.models；app.infra.repository_runtime 丢弃（trace 相关，业务 MCP 不需要）
  - 用 dict + 显式关键字参数替代 CropTemplateCreate schema；stages 为 list[dict]，
    每项含 name/duration_days/order_index/key_tasks
  - 返回 dict 而非 ORM 对象（_crop_template_to_dict / _growth_stage_to_dict）
  - 保留 db: Session 第一参数；内部 db.commit()/rollback() 改为 db.flush()，
    由上层 session_scope 统一 commit
  - delete_crop_template 移除 clear_cycle_reference 调用，保留删除
    FarmLog/CostRecord/阶段/茬口 的逻辑
  - CropTemplate.stages → CropTemplate.growth_stages（agri_backend_v2 模型关系名）
  - find_exact_duplicate 为内部辅助，仍返回 ORM（import_system_template 需要 .id）
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from business.models import (
    CostRecord,
    CropCycle,
    CropTemplate,
    FarmLog,
    GrowthStage,
)


@dataclass(frozen=True)
class ImportSystemTemplateResult:
    """系统模板导入结果。"""

    template_id: int
    already_exists: bool


# ─────────────────────────────────────────────────────────────
# 序列化辅助
# ─────────────────────────────────────────────────────────────


def _growth_stage_to_dict(stage: GrowthStage) -> dict[str, Any]:
    return {
        "id": stage.id,
        "crop_template_id": stage.crop_template_id,
        "name": stage.name,
        "duration_days": stage.duration_days,
        "order_index": stage.order_index,
        "key_tasks": stage.key_tasks,
    }


def _crop_template_to_dict(template: CropTemplate) -> dict[str, Any]:
    return {
        "id": template.id,
        "farm_id": template.farm_id,
        "name": template.name,
        "variety": template.variety,
        "category": template.category,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "stages": [_growth_stage_to_dict(s) for s in template.growth_stages],
    }


# ─────────────────────────────────────────────────────────────
# 阶段比对辅助（用于查重）
# ─────────────────────────────────────────────────────────────


def _normalize_key_tasks(key_tasks: str | None) -> str | None:
    if key_tasks is None:
        return None
    return re.sub(r"\s+", " ", key_tasks.strip())


def _stage_compare_value(stage: Any) -> tuple[str, int, str | None]:
    if isinstance(stage, Mapping):
        return (
            str(stage["name"]),
            int(stage["duration_days"]),
            _normalize_key_tasks(stage.get("key_tasks")),
        )
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
    """按 name、variety 和规范化 stages 查找完全重复的用户模板。

    返回 ORM 对象供 import_system_template 取 .id；为内部辅助函数。
    """
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
        if _normalize_stages_for_compare(candidate.growth_stages) == expected_stages:
            return candidate
    return None


def find_template_by_name(
    db: Session, crop_name: str, farm_id: int
) -> dict[str, Any] | None:
    """根据作物名称模糊搜索模板（LIKE '%crop_name%'）。"""
    template = (
        db.query(CropTemplate)
        .filter(
            CropTemplate.farm_id == farm_id,
            CropTemplate.name.ilike(f"%{crop_name}%"),
        )
        .first()
    )
    return _crop_template_to_dict(template) if template else None


def normalize_crop_name(value: str | None) -> str:
    """规范化作物名称，供模板绑定校验使用。

    这里只处理 Unicode 兼容字符和空白，不做同义词猜测；避免把橘子等近似
    作物当成用户指定作物。
    """
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", "", text).strip().lower()


def find_local_template_match(
    db: Session,
    *,
    farm_id: int,
    crop_name: str,
    variety: str | None = None,
) -> dict[str, Any] | None:
    """按规范化作物名精确查找当前农场模板。"""
    query = db.query(CropTemplate).filter(CropTemplate.farm_id == farm_id)
    if variety is not None:
        query = query.filter(CropTemplate.variety == variety)
    for template in query.all():
        if normalize_crop_name(template.name) == normalize_crop_name(crop_name):
            return _crop_template_to_dict(template)
    return None


# ─────────────────────────────────────────────────────────────
# 用户模板 CRUD
# ─────────────────────────────────────────────────────────────


def create_crop_template(
    db: Session,
    *,
    farm_id: int,
    name: str,
    variety: str | None = None,
    category: str | None = None,
    stages: list[dict] | None = None,
) -> dict[str, Any]:
    """创建作物模板及其生长阶段。

    Args:
        stages: list[dict]，每项含 name/duration_days/order_index/key_tasks
    """
    db_template = CropTemplate(
        name=name,
        variety=variety,
        category=category,
        farm_id=farm_id,
    )
    db.add(db_template)
    db.flush()

    for stage in stages or []:
        db.add(
            GrowthStage(
                crop_template_id=db_template.id,
                name=stage["name"],
                duration_days=stage["duration_days"],
                order_index=stage["order_index"],
                key_tasks=stage.get("key_tasks"),
            )
        )

    db.flush()
    db.refresh(db_template, attribute_names=["growth_stages"])
    return _crop_template_to_dict(db_template)


def get_crop_templates(
    db: Session, farm_id: int, skip: int = 0, limit: int = 100
) -> list[dict[str, Any]]:
    """获取指定农场的作物模板列表（分页）。"""
    templates = (
        db.query(CropTemplate)
        .filter(CropTemplate.farm_id == farm_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_crop_template_to_dict(t) for t in templates]


def count_crop_templates(db: Session, farm_id: int) -> int:
    """获取指定农场的作物模板总数。"""
    return db.query(CropTemplate).filter(CropTemplate.farm_id == farm_id).count()


def get_crop_template(
    db: Session, template_id: int, farm_id: int
) -> dict[str, Any] | None:
    """根据 ID 获取指定农场的单个作物模板。"""
    template = _load_crop_template_orm(db, template_id, farm_id)
    return _crop_template_to_dict(template) if template else None


def _load_crop_template_orm(
    db: Session, template_id: int, farm_id: int
) -> CropTemplate | None:
    """按 ID + farm_id 加载 ORM 模板（供 update/delete 复用）。"""
    return (
        db.query(CropTemplate)
        .filter(CropTemplate.id == template_id, CropTemplate.farm_id == farm_id)
        .first()
    )


def update_crop_template(
    db: Session,
    template_id: int,
    *,
    farm_id: int,
    name: str,
    variety: str | None = None,
    stages: list[dict],
) -> dict[str, Any]:
    """更新作物模板及其生长阶段（stages 全量替换）。

    注意：不更新 category（沿用 archive 行为，与 update_system_crop_template 不同）。
    """
    _raise_if_system_template(db, template_id)
    template = _load_crop_template_orm(db, template_id, farm_id)
    if not template:
        raise ValueError(f"模板 {template_id} 不存在")

    template.name = name
    template.variety = variety

    for stage in list(template.growth_stages):
        db.delete(stage)
    # growth_stages 对 (crop_template_id, order_index) 有唯一约束。
    # 先提交删除，再插入同序号的新阶段，避免同一 flush 内 INSERT 先于 DELETE。
    db.flush()

    for stage in stages:
        db.add(
            GrowthStage(
                crop_template_id=template.id,
                name=stage["name"],
                duration_days=stage["duration_days"],
                order_index=stage["order_index"],
                key_tasks=stage.get("key_tasks"),
            )
        )

    db.flush()
    db.refresh(template, attribute_names=["growth_stages"])
    return _crop_template_to_dict(template)


def delete_crop_template(db: Session, template_id: int, farm_id: int) -> None:
    """删除作物模板及其关联的阶段、茬口、农事日志、成本记录。"""
    _raise_if_system_template(db, template_id)
    template = _load_crop_template_orm(db, template_id, farm_id)
    if not template:
        raise ValueError(f"模板 {template_id} 不存在")

    related_cycles = (
        db.query(CropCycle).filter(CropCycle.crop_template_id == template_id).all()
    )
    for cycle in related_cycles:
        db.query(FarmLog).filter(FarmLog.cycle_id == cycle.id).delete(
            synchronize_session=False
        )
        db.query(CostRecord).filter(CostRecord.cycle_id == cycle.id).delete(
            synchronize_session=False
        )
        for stage in list(cycle.stages):
            db.delete(stage)
        db.delete(cycle)
    db.flush()

    for stage in list(template.growth_stages):
        db.delete(stage)
    db.delete(template)
    db.flush()


# ─────────────────────────────────────────────────────────────
# 系统模板
# ─────────────────────────────────────────────────────────────


def list_system_templates(
    db: Session, category: str | None = None
) -> list[dict[str, Any]]:
    """获取系统作物模板（farm_id 为空），可按分类筛选。"""
    query = db.query(CropTemplate).filter(CropTemplate.farm_id.is_(None))
    if category is not None:
        query = query.filter(CropTemplate.category == category)
    return [_crop_template_to_dict(t) for t in query.all()]


def get_system_template(db: Session, template_id: int) -> dict[str, Any] | None:
    """根据 ID 获取系统模板。"""
    template = _load_system_template_orm(db, template_id)
    return _crop_template_to_dict(template) if template else None


def _load_system_template_orm(db: Session, template_id: int) -> CropTemplate | None:
    """按 ID 加载系统模板 ORM（farm_id 为空）。"""
    return _system_template_query(db, template_id).first()


def find_system_template_match(
    db: Session, name: str, variety: str | None
) -> dict[str, Any] | None:
    """按规范化作物名和品种精确匹配系统模板。"""
    query = db.query(CropTemplate).filter(CropTemplate.farm_id.is_(None))
    if variety is not None:
        query = query.filter(CropTemplate.variety == variety)
    for template in query.all():
        if normalize_crop_name(template.name) == normalize_crop_name(name):
            return _crop_template_to_dict(template)
    return None


def import_system_template(
    db: Session, system_template_id: int, farm_id: int
) -> ImportSystemTemplateResult:
    """将系统模板深拷贝到指定农场，重复时返回已有模板 ID（幂等）。"""
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
        stages=system_template.growth_stages,
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

    for stage in system_template.growth_stages:
        db.add(
            GrowthStage(
                crop_template_id=imported.id,
                name=stage.name,
                duration_days=stage.duration_days,
                order_index=stage.order_index,
                key_tasks=stage.key_tasks,
            )
        )

    db.flush()
    db.refresh(imported, attribute_names=["growth_stages"])
    return ImportSystemTemplateResult(template_id=imported.id, already_exists=False)


def _system_template_query(db: Session, template_id: int):
    return db.query(CropTemplate).filter(
        CropTemplate.id == template_id,
        CropTemplate.farm_id.is_(None),
    )


def create_system_crop_template(
    db: Session,
    *,
    name: str,
    variety: str | None = None,
    category: str | None = None,
    stages: list[dict] | None = None,
) -> dict[str, Any]:
    """创建系统作物模板（farm_id 为空）。"""
    db_template = CropTemplate(
        farm_id=None,
        name=name,
        variety=variety,
        category=category,
    )
    db.add(db_template)
    db.flush()

    for stage in stages or []:
        db.add(
            GrowthStage(
                crop_template_id=db_template.id,
                name=stage["name"],
                duration_days=stage["duration_days"],
                order_index=stage["order_index"],
                key_tasks=stage.get("key_tasks"),
            )
        )

    db.flush()
    db.refresh(db_template, attribute_names=["growth_stages"])
    return _crop_template_to_dict(db_template)


def update_system_crop_template(
    db: Session,
    template_id: int,
    *,
    name: str,
    variety: str | None = None,
    category: str | None = None,
    stages: list[dict],
) -> dict[str, Any]:
    """更新系统作物模板（含 stages 全量替换）。"""
    template = _load_system_template_orm(db, template_id)
    if template is None:
        raise ValueError(f"系统模板 {template_id} 不存在")

    template.name = name
    template.variety = variety
    template.category = category

    for stage in list(template.growth_stages):
        db.delete(stage)

    for stage in stages:
        db.add(
            GrowthStage(
                crop_template_id=template.id,
                name=stage["name"],
                duration_days=stage["duration_days"],
                order_index=stage["order_index"],
                key_tasks=stage.get("key_tasks"),
            )
        )

    db.flush()
    db.refresh(template, attribute_names=["growth_stages"])
    return _crop_template_to_dict(template)


def count_farm_template_imports(db: Session, name: str, variety: str | None) -> int:
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
    template = _load_system_template_orm(db, template_id)
    if template is None:
        raise ValueError(f"系统模板 {template_id} 不存在")

    farm_count = count_farm_template_imports(
        db, name=template.name, variety=template.variety
    )
    if farm_count > 0:
        raise ValueError(
            f"系统模板 {template_id} 已被 {farm_count} 个农场导入，禁止删除"
        )

    for stage in list(template.growth_stages):
        db.delete(stage)
    db.delete(template)
    db.flush()


def _get_any_crop_template(db: Session, template_id: int) -> CropTemplate | None:
    return db.query(CropTemplate).filter(CropTemplate.id == template_id).first()


def _raise_if_system_template(db: Session, template_id: int) -> None:
    template = _get_any_crop_template(db, template_id)
    if template is not None and template.farm_id is None:
        raise ValueError(f"系统模板 {template_id} 不允许修改")


__all__ = [
    "ImportSystemTemplateResult",
    "create_crop_template",
    "get_crop_templates",
    "count_crop_templates",
    "get_crop_template",
    "update_crop_template",
    "delete_crop_template",
    "find_template_by_name",
    "normalize_crop_name",
    "find_local_template_match",
    "find_exact_duplicate",
    "list_system_templates",
    "get_system_template",
    "import_system_template",
    "find_system_template_match",
    "create_system_crop_template",
    "update_system_crop_template",
    "count_farm_template_imports",
    "delete_system_crop_template",
]
