"""分页功能测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def watermelon_template_id():
    """创建西瓜模板并返回模板 ID。"""
    payload = {
        "name": "西瓜",
        "variety": "8424",
        "stages": [
            {
                "name": "育苗期",
                "duration_days": 30,
                "order_index": 0,
                "key_tasks": "温湿度管理",
            },
        ],
    }
    response = client.post("/crops/templates", json=payload)
    return response.json()["id"]


@pytest.fixture
def cycle_id(watermelon_template_id):
    """创建茬口并返回 ID。"""
    payload = {
        "name": "1号棚西瓜",
        "crop_template_id": watermelon_template_id,
        "start_date": "2025-03-15",
    }
    response = client.post("/cycles", json=payload)
    return response.json()["id"]


class TestCropPagination:
    """作物模板分页测试。"""

    def test_paginated_response_structure(self):
        """测试分页响应包含 items 和 total 字段。"""
        response = client.get("/crops/templates")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    def test_pagination_with_multiple_items(self):
        """测试创建多个模板后分页返回正确总数。"""
        for i in range(3):
            client.post(
                "/crops/templates",
                json={
                    "name": f"作物{i}",
                    "variety": "测试",
                    "stages": [],
                },
            )

        response = client.get("/crops/templates")
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_pagination_limit(self):
        """测试 size 参数限制返回数量。"""
        for i in range(5):
            client.post(
                "/crops/templates",
                json={
                    "name": f"作物{i}",
                    "variety": "测试",
                    "stages": [],
                },
            )

        response = client.get("/crops/templates?page=1&size=2")
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

    def test_pagination_skip(self):
        """测试 page 参数正确跳过记录。"""
        for i in range(5):
            client.post(
                "/crops/templates",
                json={
                    "name": f"作物{i}",
                    "variety": "测试",
                    "stages": [],
                },
            )

        response = client.get("/crops/templates?page=2&size=2")
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

    def test_pagination_empty_result(self):
        """测试无数据时返回空列表和 total=0。"""
        response = client.get("/crops/templates")
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_pagination_invalid_page(self):
        """测试 page 小于 1 返回 422。"""
        response = client.get("/crops/templates?page=0")
        assert response.status_code == 422

    def test_pagination_invalid_size(self):
        """测试 size 超过最大值返回 422。"""
        response = client.get("/crops/templates?size=101")
        assert response.status_code == 422


class TestCyclePagination:
    """茬口分页测试。"""

    def test_paginated_response_structure(self, watermelon_template_id):
        """测试茬口分页响应结构。"""
        response = client.get("/cycles")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_pagination_with_cycles(self, watermelon_template_id):
        """测试多个茬口分页。"""
        for i in range(3):
            client.post(
                "/cycles",
                json={
                    "name": f"棚{i}西瓜",
                    "crop_template_id": watermelon_template_id,
                    "start_date": "2025-03-15",
                },
            )

        response = client.get("/cycles")
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3


class TestLogPagination:
    """日志分页测试。"""

    def test_paginated_response_structure(self, cycle_id):
        """测试日志分页响应结构。"""
        response = client.get(f"/logs?cycle_id={cycle_id}")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_pagination_with_filter(self, cycle_id):
        """测试带过滤条件的分页。"""
        for i in range(3):
            client.post(
                "/logs",
                json={
                    "cycle_id": cycle_id,
                    "operation_type": "浇水",
                    "operation_date": f"2025-05-{20 + i}",
                },
            )

        response = client.get(f"/logs?cycle_id={cycle_id}")
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_pagination_with_filter_and_size(self, cycle_id):
        """测试带过滤条件且限制返回数量。"""
        for i in range(5):
            client.post(
                "/logs",
                json={
                    "cycle_id": cycle_id,
                    "operation_type": "浇水",
                    "operation_date": f"2025-05-{20 + i}",
                },
            )

        response = client.get(f"/logs?cycle_id={cycle_id}&page=1&size=2")
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2


class TestCostPagination:
    """成本分页测试。"""

    def test_paginated_response_structure(self, cycle_id):
        """测试成本分页响应结构。"""
        response = client.get(f"/costs?cycle_id={cycle_id}")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_pagination_with_filter(self, cycle_id):
        """测试带过滤条件的成本分页。"""
        for i in range(3):
            client.post(
                "/costs",
                json={
                    "cycle_id": cycle_id,
                    "record_type": "cost",
                    "category": "肥料",
                    "amount": "100.00",
                    "record_date": f"2025-03-{10 + i}",
                },
            )

        response = client.get(f"/costs?cycle_id={cycle_id}")
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    def test_pagination_with_category_filter(self, cycle_id):
        """测试按类别过滤的分页。"""
        client.post(
            "/costs",
            json={
                "cycle_id": cycle_id,
                "record_type": "cost",
                "category": "肥料",
                "amount": "100.00",
                "record_date": "2025-03-10",
            },
        )
        client.post(
            "/costs",
            json={
                "cycle_id": cycle_id,
                "record_type": "cost",
                "category": "种子",
                "amount": "50.00",
                "record_date": "2025-03-11",
            },
        )

        response = client.get(f"/costs?cycle_id={cycle_id}&category=肥料")
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["category"] == "肥料"
