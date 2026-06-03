"""测试成本分类 Service。"""

import pytest

from app.models.cost_category import CostCategory
from app.schemas.cost_category import CostCategoryCreate
from app.services.cost_category_service import (
    create_category,
    delete_category,
    get_categories,
    init_default_categories,
)


@pytest.fixture
def db(db_session):
    """提供一个数据库会话。"""
    yield db_session


def test_init_default_categories(db):
    """测试初始化默认分类。"""
    farm_id = 1

    # 第一次初始化，创建 10 个默认分类
    categories = init_default_categories(db, farm_id)
    assert len(categories) == 10
    assert all(cat.is_default for cat in categories)

    # 验证类型分布：7 个支出，3 个收入
    cost_cats = [c for c in categories if c.type == "cost"]
    income_cats = [c for c in categories if c.type == "income"]
    assert len(cost_cats) == 7
    assert len(income_cats) == 3

    # 第二次初始化，幂等性检查（不应重复创建）
    categories_again = init_default_categories(db, farm_id)
    assert len(categories_again) == 0


def test_get_categories(db):
    """测试获取分类列表。"""
    farm_id = 1

    # 初始化默认分类
    init_default_categories(db, farm_id)

    # 获取分类列表
    categories = get_categories(db, farm_id)
    assert len(categories) == 10

    # 验证排序：按 sort_order, id 排序
    for i in range(len(categories) - 1):
        curr, next_ = categories[i], categories[i + 1]
        if curr.sort_order == next_.sort_order:
            assert curr.id < next_.id
        else:
            assert curr.sort_order < next_.sort_order


def test_create_category(db):
    """测试创建用户自定义分类。"""
    farm_id = 1
    data = CostCategoryCreate(
        name="自定义分类",
        type="cost",
        icon="custom-icon",
        sort_order=99,
    )

    category = create_category(db, data, farm_id)

    # 验证字段
    assert category.name == "自定义分类"
    assert category.type == "cost"
    assert category.icon == "custom-icon"
    assert category.sort_order == 99
    assert category.farm_id == farm_id
    assert category.is_default is False


def test_delete_custom_category(db):
    """测试删除用户自定义分类。"""
    farm_id = 1

    # 先创建一个自定义分类
    data = CostCategoryCreate(
        name="待删除分类",
        type="cost",
        icon="delete-icon",
        sort_order=100,
    )
    category = create_category(db, data, farm_id)
    category_id = category.id

    # 删除分类
    delete_category(db, category_id, farm_id)

    # 验证已删除
    deleted = db.query(CostCategory).filter_by(id=category_id).first()
    assert deleted is None


def test_prevent_delete_default_category(db):
    """测试禁止删除系统预设分类。"""
    farm_id = 1

    # 初始化默认分类
    categories = init_default_categories(db, farm_id)
    default_category = categories[0]

    # 尝试删除默认分类，应抛出 ValueError
    with pytest.raises(ValueError, match="不能删除系统预设分类"):
        delete_category(db, default_category.id, farm_id)
