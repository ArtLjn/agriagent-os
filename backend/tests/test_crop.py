from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_crop_template():
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
            {
                "name": "定植期",
                "duration_days": 1,
                "order_index": 1,
                "key_tasks": "浇定根水",
            },
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
            {
                "name": "播种期",
                "duration_days": 7,
                "order_index": 0,
                "key_tasks": "浇水保湿",
            },
        ],
    }
    client.post("/crops/templates", json=payload)

    response = client.get("/crops/templates")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "豆角"


def test_get_template_not_found():
    response = client.get("/crops/templates/99999")
    assert response.status_code == 404


def test_update_crop_template():
    """测试更新作物模板。"""
    create_payload = {
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
    create_resp = client.post("/crops/templates", json=create_payload)
    template_id = create_resp.json()["id"]

    update_payload = {
        "name": "改良西瓜",
        "variety": "麒麟",
        "stages": [
            {
                "name": "育苗期",
                "duration_days": 25,
                "order_index": 0,
                "key_tasks": "改良温湿度管理",
            },
            {
                "name": "定植期",
                "duration_days": 1,
                "order_index": 1,
                "key_tasks": "浇定根水",
            },
        ],
    }
    response = client.put(f"/crops/templates/{template_id}", json=update_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "改良西瓜"
    assert data["variety"] == "麒麟"
    assert len(data["stages"]) == 2
    assert data["stages"][0]["duration_days"] == 25


def test_update_template_not_found():
    """测试更新不存在的模板返回 404。"""
    payload = {
        "name": "不存在",
        "variety": "无",
        "stages": [],
    }
    response = client.put("/crops/templates/99999", json=payload)
    assert response.status_code == 404


def test_delete_crop_template():
    """测试删除作物模板。"""
    create_payload = {
        "name": "临时作物",
        "variety": "测试",
        "stages": [],
    }
    create_resp = client.post("/crops/templates", json=create_payload)
    template_id = create_resp.json()["id"]

    response = client.delete(f"/crops/templates/{template_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "删除成功"

    get_resp = client.get(f"/crops/templates/{template_id}")
    assert get_resp.status_code == 404


def test_delete_template_not_found():
    """测试删除不存在的模板返回 404。"""
    response = client.delete("/crops/templates/99999")
    assert response.status_code == 404
