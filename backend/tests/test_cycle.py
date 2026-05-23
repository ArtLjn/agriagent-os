from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_watermelon_template():
    """创建西瓜模板并返回模板 ID。"""
    payload = {
        "name": "西瓜",
        "variety": "8424",
        "stages": [
            {"name": "育苗期", "duration_days": 30, "order_index": 0, "key_tasks": "温湿度管理"},
            {"name": "定植期", "duration_days": 1, "order_index": 1, "key_tasks": "浇定根水"},
            {"name": "伸蔓期", "duration_days": 20, "order_index": 2, "key_tasks": "整枝压蔓"},
        ],
    }
    response = client.post("/crops/templates", json=payload)
    return response.json()["id"]


def test_create_crop_cycle():
    """测试创建茬口并验证阶段日期推算。"""
    template_id = _create_watermelon_template()

    payload = {
        "name": "1号棚西瓜",
        "crop_template_id": template_id,
        "start_date": "2025-03-15",
        "field_name": "1号大棚",
    }

    response = client.post("/cycles", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "1号棚西瓜"
    assert len(data["stages"]) == 3
    assert data["stages"][0]["start_date"] == "2025-03-15"
    assert data["stages"][0]["end_date"] == "2025-04-13"
    assert data["stages"][1]["start_date"] == "2025-04-14"


def test_list_crop_cycles():
    """测试获取茬口列表。"""
    response = client.get("/cycles")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
