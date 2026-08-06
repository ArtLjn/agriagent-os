"""成本分类 Service，提供分类管理业务逻辑。"""

import logging

from sqlalchemy.orm import Session

from app.domains.finance.cost_category_models import CostCategory
from app.domains.finance.cost_category_schemas import CostCategoryCreate

logger = logging.getLogger(__name__)

# 系统预设分类模板
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
    """初始化系统预设分类。

    幂等操作：已存在分类则跳过，不重复创建。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。

    Returns:
        新创建的分类列表（如果已存在则返回空列表）。
    """
    # 检查是否已存在默认分类
    existing = (
        db.query(CostCategory).filter_by(farm_id=farm_id, is_default=True).first()
    )
    if existing:
        logger.info(f"农场 {farm_id} 的默认分类已存在，跳过初始化")
        return []

    # 创建默认分类
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

    db.commit()
    for cat in categories:
        db.refresh(cat)

    logger.info(f"为农场 {farm_id} 初始化了 {len(categories)} 个默认分类")
    return categories


def get_categories(db: Session, farm_id: int) -> list[CostCategory]:
    """获取农场的分类列表。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。

    Returns:
        分类列表，按 sort_order 和 id 排序。
    """
    return (
        db.query(CostCategory)
        .filter_by(farm_id=farm_id)
        .order_by(CostCategory.sort_order, CostCategory.id)
        .all()
    )


def create_category(
    db: Session, data: CostCategoryCreate, farm_id: int
) -> CostCategory:
    """创建用户自定义分类。

    Args:
        db: 数据库会话。
        data: 分类创建数据。
        farm_id: 农场 ID。

    Returns:
        新创建的分类实例。
    """
    category = CostCategory(
        farm_id=farm_id,
        name=data.name,
        type=data.type,
        icon=data.icon,
        sort_order=data.sort_order,
        is_default=False,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category_id: int, farm_id: int) -> None:
    """删除分类。

    Args:
        db: 数据库会话。
        category_id: 分类 ID。
        farm_id: 农场 ID。

    Raises:
        ValueError: 分类不存在或为系统预设分类时抛出。
    """
    category = db.query(CostCategory).filter_by(id=category_id, farm_id=farm_id).first()

    if not category:
        raise ValueError(f"分类 {category_id} 不存在")

    if category.is_default:
        raise ValueError("不能删除系统预设分类")

    db.delete(category)
    db.commit()
    logger.info(f"删除分类 {category_id}（农场 {farm_id}）")


__all__ = [
    "init_default_categories",
    "get_categories",
    "create_category",
    "delete_category",
]
