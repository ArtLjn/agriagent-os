"""成本分类 Service（从 archive cost_category_service.py 直接复用）。

提供：
  - init_default_categories: 农场首次访问时初始化系统预设分类（幂等）
  - get_categories: 获取农场分类列表
  - create_category: 创建用户自定义分类
  - delete_category: 删除分类（系统预设分类禁止删除）

直接复用 archive 代码，无需改造（无外部依赖）。
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from business.models import CostCategory

logger = logging.getLogger(__name__)

# 系统预设分类模板（与 archive 保持一致）
DEFAULT_CATEGORIES = [
    # 支出分类
    {"name": "种子", "type": "cost", "icon": "leaf", "sort_order": 1},
    {"name": "化肥", "type": "cost", "icon": "flask", "sort_order": 2},
    {"name": "农药", "type": "cost", "icon": "shield-alert", "sort_order": 3},
    {"name": "人工", "type": "cost", "icon": "users", "sort_order": 4},
    {"name": "水电", "type": "cost", "icon": "droplet", "sort_order": 5},
    {"name": "地租", "type": "cost", "icon": "home", "sort_order": 6},
    {"name": "其他", "type": "cost", "icon": "more-horizontal", "sort_order": 99},
    # 收入分类
    {"name": "销售", "type": "income", "icon": "shopping-cart", "sort_order": 1},
    {"name": "补贴", "type": "income", "icon": "hand-coins", "sort_order": 2},
    {"name": "其他", "type": "income", "icon": "more-horizontal", "sort_order": 99},
]


def init_default_categories(db: Session, farm_id: int) -> list[CostCategory]:
    """初始化系统预设分类（幂等）。

    已存在分类则跳过，不重复创建。注册用户时调用。

    Args:
        db: 数据库会话
        farm_id: 农场 ID

    Returns:
        新创建的分类列表（已存在则返回空列表）
    """
    existing = (
        db.query(CostCategory).filter_by(farm_id=farm_id, is_default=True).first()
    )
    if existing:
        logger.info("农场 %s 的默认分类已存在，跳过初始化", farm_id)
        return []

    categories = []
    for cat_data in DEFAULT_CATEGORIES:
        category = CostCategory(
            farm_id=farm_id,
            name=cat_data["name"],
            type=cat_data["type"],
            icon=cat_data["icon"],
            sort_order=cat_data["sort_order"],
            is_default=True,
        )
        db.add(category)
        categories.append(category)

    db.flush()
    logger.info("为农场 %s 初始化了 %d 个默认分类", farm_id, len(categories))
    return categories


def get_categories(db: Session, farm_id: int) -> list[CostCategory]:
    """获取农场的分类列表，按 sort_order 和 id 排序。"""
    return (
        db.query(CostCategory)
        .filter_by(farm_id=farm_id)
        .order_by(CostCategory.sort_order, CostCategory.id)
        .all()
    )


def create_category(
    db: Session,
    *,
    farm_id: int,
    name: str,
    type: str,
    icon: str = "tag",
    sort_order: int = 0,
) -> CostCategory:
    """创建用户自定义分类。

    Args:
        db: 数据库会话
        farm_id: 农场 ID
        name: 分类名
        type: cost 或 income
        icon: 图标名（默认 tag）
        sort_order: 排序（默认 0）

    Returns:
        新创建的 CostCategory 实例
    """
    category = CostCategory(
        farm_id=farm_id,
        name=name,
        type=type,
        icon=icon,
        sort_order=sort_order,
        is_default=False,
    )
    db.add(category)
    db.flush()
    return category


def delete_category(db: Session, category_id: int, farm_id: int) -> None:
    """删除分类。

    Args:
        db: 数据库会话
        category_id: 分类 ID
        farm_id: 农场 ID

    Raises:
        ValueError: 分类不存在或为系统预设分类时抛出。
    """
    category = (
        db.query(CostCategory)
        .filter_by(id=category_id, farm_id=farm_id)
        .first()
    )

    if not category:
        raise ValueError(f"分类 {category_id} 不存在")

    if category.is_default:
        raise ValueError("不能删除系统预设分类")

    db.delete(category)
    db.flush()
    logger.info("删除分类 %s（农场 %s）", category_id, farm_id)


def update_category(
    db: Session,
    *,
    category_id: int,
    farm_id: int,
    changes: dict,
) -> CostCategory:
    """更新分类字段。

    支持字段：name / type / icon / sort_order。
    系统预设分类只允许修改 name / icon / sort_order，不允许修改 type。
    """
    category = (
        db.query(CostCategory)
        .filter_by(id=category_id, farm_id=farm_id)
        .first()
    )
    if not category:
        raise ValueError(f"分类 {category_id} 不存在")

    editable = {"name", "type", "icon", "sort_order"}
    for key, value in changes.items():
        if key not in editable:
            continue
        if key == "type" and category.is_default:
            raise ValueError("系统预设分类不允许修改 type")
        setattr(category, key, value)

    db.flush()
    logger.info("更新分类 %s（农场 %s）", category_id, farm_id)
    return category


def find_category(
    db: Session, farm_id: int, category_name: str, record_type: str
) -> CostCategory | None:
    """按农场、分类名和收支类型查找分类。

    供 cost_service / labor_service 内部使用。
    """
    return (
        db.query(CostCategory)
        .filter(
            CostCategory.farm_id == farm_id,
            CostCategory.name == category_name,
            CostCategory.type == record_type,
        )
        .first()
    )


__all__ = [
    "DEFAULT_CATEGORIES",
    "init_default_categories",
    "get_categories",
    "create_category",
    "update_category",
    "delete_category",
    "find_category",
]
