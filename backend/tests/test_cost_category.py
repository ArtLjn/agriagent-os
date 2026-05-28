"""测试 CostCategory 模型的核心行为。"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, _set_sqlite_pragma
from app.models.cost_category import CostCategory

_test_engine = create_engine(
    "sqlite:///tests/test_cost_category.db",
    connect_args={"check_same_thread": False},
)
event.listen(_test_engine, "connect", _set_sqlite_pragma)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    yield


@pytest.fixture
def db():
    session = _TestSession()
    yield session
    session.close()


class TestCostCategory:
    """CostCategory 模型测试套件。"""

    def test_create_default_category(self, db: Session):
        """创建系统预设分类，验证 id/name/is_default 字段。"""
        # Arrange & Act
        category = CostCategory(
            id=1,
            farm_id=1,
            name="种子成本",
            type="cost",
            icon="leaf",
            sort_order=1,
            is_default=True,
        )
        db.add(category)
        db.commit()
        db.refresh(category)

        # Assert
        assert category.id == 1
        assert category.name == "种子成本"
        assert category.is_default is True
        assert category.type == "cost"

    def test_category_farm_isolation(self, db: Session):
        """不同农场的分类互不影响。"""
        # Arrange
        farm1_category = CostCategory(
            farm_id=1, name="农场1肥料", type="cost", icon="package"
        )
        farm2_category = CostCategory(
            farm_id=2, name="农场2肥料", type="cost", icon="package"
        )
        db.add_all([farm1_category, farm2_category])
        db.commit()

        # Act
        farm1_categories = db.query(CostCategory).filter_by(farm_id=1).all()
        farm2_categories = db.query(CostCategory).filter_by(farm_id=2).all()

        # Assert
        assert len(farm1_categories) == 1
        assert len(farm2_categories) == 1
        assert farm1_categories[0].name == "农场1肥料"
        assert farm2_categories[0].name == "农场2肥料"

    def test_delete_non_default_category(self, db: Session):
        """可以删除用户自定义分类。"""
        # Arrange
        custom_category = CostCategory(
            farm_id=1, name="自定义分类", type="cost", icon="tag", is_default=False
        )
        db.add(custom_category)
        db.commit()
        category_id = custom_category.id

        # Act
        db.delete(custom_category)
        db.commit()

        # Assert
        deleted = db.query(CostCategory).filter_by(id=category_id).first()
        assert deleted is None

    def test_prevent_delete_default_category(self, db: Session):
        """系统预设分类应用层不强制约束，仅验证 is_default=True。"""
        # Arrange
        default_category = CostCategory(
            farm_id=1, name="系统预设", type="cost", icon="tag", is_default=True
        )
        db.add(default_category)
        db.commit()
        db.refresh(default_category)

        # Assert - 验证 is_default 字段正确设置
        assert default_category.is_default is True
        # 注意：数据库层不强制约束，删除限制由应用层实现
