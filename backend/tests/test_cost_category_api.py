"""成本分类 API 测试。"""

import pytest
from fastapi.testclient import TestClient

from app.shared.database import get_db
from app.modules.farm.dependencies import get_current_farm
from app.models.farm import Farm


@pytest.fixture
def client(db_session):
    """创建测试客户端。"""
    from app.api.cost_categories import router

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        yield db_session

    def override_get_current_farm():
        return db_session.get(Farm, 1)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_farm] = override_get_current_farm
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestGetCategories:
    """测试获取分类列表接口。"""

    def test_get_categories_empty_farm(self, client):
        """测试空农场自动初始化预设分类。"""
        response = client.get("/cost-categories?farm_id=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert all(cat["farm_id"] == 1 for cat in data)
        assert any(cat["name"] == "种子" and cat["type"] == "cost" for cat in data)

    def test_get_categories_after_init(self, client):
        """测试获取已有分类列表。"""
        # 先初始化
        client.get("/cost-categories?farm_id=1")

        # 再次获取
        response = client.get("/cost-categories?farm_id=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0


class TestCreateCategory:
    """测试创建分类接口。"""

    def test_create_category(self, client):
        """测试创建自定义分类。"""
        payload = {
            "name": "测试分类",
            "type": "cost",
            "icon": "test",
            "sort_order": 10,
        }

        response = client.post("/cost-categories?farm_id=1", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "测试分类"
        assert data["type"] == "cost"
        assert data["icon"] == "test"
        assert data["sort_order"] == 10
        assert data["farm_id"] == 1
        assert data["is_default"] is False
        assert "id" in data

    def test_create_category_invalid_type(self, client):
        """测试拒绝无效类型（422）。"""
        payload = {
            "name": "测试分类",
            "type": "invalid_type",
            "icon": "test",
            "sort_order": 10,
        }

        response = client.post("/cost-categories?farm_id=1", json=payload)

        assert response.status_code == 422
        assert "type" in str(response.json())


class TestDeleteCategory:
    """测试删除分类接口。"""

    def test_delete_custom_category(self, client):
        """测试删除自定义分类。"""
        # 先创建一个自定义分类
        create_payload = {
            "name": "临时分类",
            "type": "cost",
            "icon": "temp",
            "sort_order": 99,
        }
        create_response = client.post("/cost-categories?farm_id=1", json=create_payload)
        category_id = create_response.json()["id"]

        # 删除
        response = client.delete(f"/cost-categories/{category_id}?farm_id=1")

        assert response.status_code == 200
        assert response.json() == {"message": "删除成功"}

    def test_delete_default_category_forbidden(self, client):
        """测试禁止删除系统预设分类（400）。"""
        # 先初始化默认分类
        client.get("/cost-categories?farm_id=1")

        # 获取第一个默认分类
        list_response = client.get("/cost-categories?farm_id=1")
        default_category = next(
            cat for cat in list_response.json() if cat["is_default"] is True
        )
        category_id = default_category["id"]

        # 尝试删除
        response = client.delete(f"/cost-categories/{category_id}?farm_id=1")

        assert response.status_code == 400
        assert "不能删除系统预设分类" in response.json()["detail"]


class TestFarmIsolation:
    """测试农场隔离。"""

    def test_get_categories_farm_isolation(self, client):
        """测试验证农场隔离。"""
        # 获取农场1的分类
        response1 = client.get("/cost-categories?farm_id=1")
        assert response1.status_code == 200
        data1 = response1.json()

        # 所有分类都属于农场1
        assert all(cat["farm_id"] == 1 for cat in data1)
