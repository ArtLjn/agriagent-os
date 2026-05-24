import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_crop_template():
    payload = {
        "name": "西瓜",
        "variety": "8424",
        "stages": [
            {"name": "育苗期", "duration_days": 30, "order_index": 0, "key_tasks": "温湿度管理"},
            {"name": "定植期", "duration_days": 1, "order_index": 1, "key_tasks": "浇定根水"},
        ],
    }
    response = client.post("/crops/templates", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "西瓜"
    assert len(data["stages"]) == 2
    assert data["stages"][0]["name"] == "育苗期"


def test_list_crop_templates():
    payload = {
        "name": "豆角",
        "variety": "长豆角",
        "stages": [
            {"name": "播种期", "duration_days": 7, "order_index": 0, "key_tasks": "浇水保湿"},
        ],
    }
    client.post("/crops/templates", json=payload)

    response = client.get("/crops/templates")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "豆角"


def test_get_template_not_found():
    response = client.get("/crops/templates/99999")
    assert response.status_code == 404
