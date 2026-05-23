from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_crop_template():
    """测试创建作物模板。"""
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
    """测试获取作物模板列表。"""
    response = client.get("/crops/templates")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
