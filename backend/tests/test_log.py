import pytest
from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import Base, engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Clean database before each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def watermelon_template_id():
    """创建西瓜模板并返回模板 ID。"""
    payload = {
        "name": "西瓜",
        "variety": "8424",
        "stages": [
            {"name": "育苗期", "duration_days": 30, "order_index": 0, "key_tasks": "温湿度管理"},
        ],
    }
    response = client.post("/crops/templates", json=payload)
    return response.json()["id"]


@pytest.fixture
def cycle_id(watermelon_template_id):
    """创建茬口并返回茬口 ID。"""
    payload = {
        "name": "1号棚西瓜",
        "crop_template_id": watermelon_template_id,
        "start_date": "2025-03-15",
    }
    response = client.post("/cycles", json=payload)
    return response.json()["id"]


def test_create_farm_log(cycle_id):
    """测试创建农事日志。"""
    payload = {
        "cycle_id": cycle_id,
        "operation_type": "浇水",
        "operation_date": "2025-05-20",
        "note": "早晨浇透水",
    }

    response = client.post("/logs", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["operation_type"] == "浇水"
    assert data["note"] == "早晨浇透水"


def test_list_logs_by_cycle(cycle_id):
    """测试按周期 ID 筛选农事日志列表。"""
    # 先创建一条日志
    payload = {
        "cycle_id": cycle_id,
        "operation_type": "施肥",
        "operation_date": "2025-05-21",
    }
    client.post("/logs", json=payload)

    response = client.get(f"/logs?cycle_id={cycle_id}")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["operation_type"] == "施肥"
