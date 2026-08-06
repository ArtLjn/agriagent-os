"""Skill function call 动态候选值。"""

import logging
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillCandidateSet:
    values: dict[str, list[str]] = field(default_factory=dict)
    labels: dict[str, dict[str, str]] = field(default_factory=dict)


_DEFAULT_CATEGORY_ENUM = ["化肥", "种子", "农药", "人工", "销售", "其他"]
_STATIC_CANDIDATES = {
    "type": ["cost", "income"],
    "record_type": ["cost", "income"],
}
_candidate_cache: dict[int, SkillCandidateSet] = {}


def load_skill_candidates(farm_id: int) -> SkillCandidateSet:
    """加载当前农场的候选值；任一领域读取失败时返回已取得的降级集合。"""
    if farm_id in _candidate_cache:
        return _candidate_cache[farm_id]

    values = {key: list(items) for key, items in _STATIC_CANDIDATES.items()}
    values["category"] = list(_DEFAULT_CATEGORY_ENUM)
    labels: dict[str, dict[str, str]] = {}
    db = None
    try:
        db = _session_local()()
        _merge_candidates(values, labels, "category", _load_categories, db, farm_id)
        _merge_candidates(values, labels, "cycle_id", _load_cycles, db, farm_id)
        _merge_candidates(values, labels, "worker_id", _load_workers, db, farm_id)
        _merge_candidates(values, labels, "unit_id", _load_units, db, farm_id)
        _merge_candidates(
            values, labels, "work_order_id", _load_work_orders, db, farm_id
        )
        _merge_candidates(
            values, labels, "crop_template_id", _load_crop_templates, db, farm_id
        )
    except Exception as exc:
        logger.warning(
            "加载 Skill 候选值失败，使用降级候选 | farm_id=%s error=%s",
            farm_id,
            exc,
        )
    finally:
        if db is not None:
            db.close()

    _add_aliases(values)
    candidate_set = SkillCandidateSet(values=values, labels=labels)
    _candidate_cache[farm_id] = candidate_set
    return candidate_set


def get_category_enum(farm_id: int) -> list[str]:
    """保留原分类 enum 行为，供现有 tool schema 复用。"""
    categories = load_skill_candidates(farm_id).values.get("category")
    return list(categories or _DEFAULT_CATEGORY_ENUM)


def clear_skill_candidate_cache(farm_id: int | None = None) -> None:
    """清除候选缓存。farm_id=None 时清除全部。"""
    if farm_id is None:
        _candidate_cache.clear()
    else:
        _candidate_cache.pop(farm_id, None)


def _merge_candidates(
    values: dict[str, list[str]],
    labels: dict[str, dict[str, str]],
    field_name: str,
    loader: Callable[[Any, int], tuple[list[str], dict[str, str]]],
    db: Any,
    farm_id: int,
) -> None:
    try:
        loaded_values, loaded_labels = loader(db, farm_id)
    except Exception as exc:
        logger.warning(
            "加载 Skill 候选字段失败 | farm_id=%s field=%s error=%s",
            farm_id,
            field_name,
            exc,
        )
        return
    if loaded_values:
        values[field_name] = loaded_values
    if loaded_labels:
        labels[field_name] = loaded_labels


def _load_categories(db: Any, farm_id: int) -> tuple[list[str], dict[str, str]]:
    categories = _cost_category_service().get_categories(db, farm_id)
    names = [str(category.name) for category in categories if category.name]
    return names or list(_DEFAULT_CATEGORY_ENUM), {}


def _session_local():
    skills_module = sys.modules.get("app.skills")
    patched = getattr(skills_module, "SessionLocal", None) if skills_module else None
    if patched is not None:
        return patched
    from app.shared.database import SessionLocal

    return SessionLocal


def _cost_category_service():
    skills_module = sys.modules.get("app.skills")
    patched = (
        getattr(skills_module, "cost_category_service", None) if skills_module else None
    )
    if patched is not None:
        return patched
    from app.domains.finance import cost_category_service

    return cost_category_service


def _merge_unique(primary: list[str], fallback: list[str]) -> list[str]:
    merged: list[str] = []
    for item in [*primary, *fallback]:
        if item and item not in merged:
            merged.append(item)
    return merged


def _load_cycles(db: Any, farm_id: int) -> tuple[list[str], dict[str, str]]:
    from app.domains.planting import cycle_service

    cycles = cycle_service.get_crop_cycles(db, farm_id=farm_id, limit=100)
    return _id_name_values(cycles, name_attrs=("name",))


def _load_workers(db: Any, farm_id: int) -> tuple[list[str], dict[str, str]]:
    from app.domains.planting import service as planting_service

    workers = planting_service.list_workers(db, farm_id, active_only=True)
    return _id_name_values(workers, name_attrs=("name",))


def _load_units(db: Any, farm_id: int) -> tuple[list[str], dict[str, str]]:
    from app.domains.planting import service as planting_service

    units = planting_service.list_units(db, farm_id)
    return _id_name_values(units, name_attrs=("name",))


def _load_work_orders(db: Any, farm_id: int) -> tuple[list[str], dict[str, str]]:
    from app.domains.planting import service as planting_service

    work_orders = planting_service.list_work_orders(db, farm_id, limit=100)
    return _id_name_values(work_orders, name_attrs=("operation_type",))


def _load_crop_templates(db: Any, farm_id: int) -> tuple[list[str], dict[str, str]]:
    from app.domains.planting import crop_service

    templates = crop_service.get_crop_templates(db, farm_id=farm_id, limit=100)
    return _id_name_values(templates, name_attrs=("name",))


def _id_name_values(
    items: list[Any],
    *,
    name_attrs: tuple[str, ...],
) -> tuple[list[str], dict[str, str]]:
    values = []
    labels = {}
    for item in items:
        item_id = getattr(item, "id", None)
        name = _first_text_attr(item, name_attrs)
        if item_id in (None, ""):
            continue
        key = str(item_id)
        label = f"{item_id}:{name}" if name else key
        values.append(label)
        labels[key] = label
        if name:
            labels[name] = label
    return values, labels


def _first_text_attr(item: Any, attrs: tuple[str, ...]) -> str:
    for attr in attrs:
        value = getattr(item, attr, None)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _add_aliases(values: dict[str, list[str]]) -> None:
    if "worker_id" in values:
        values.setdefault("worker_name", list(values["worker_id"]))
        values.setdefault("workers", list(values["worker_id"]))
        values.setdefault("worker", list(values["worker_id"]))
    if "cycle_id" in values:
        values.setdefault("cycle", list(values["cycle_id"]))
    if "unit_id" in values:
        values.setdefault("unit_names", list(values["unit_id"]))
        values.setdefault("planting_unit", list(values["unit_id"]))
