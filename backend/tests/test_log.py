import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def watermelon_template_id():
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
    payload = {
        "name": "1号棚西瓜",
        "crop_template_id": watermelon_template_id,
        "start_date": "2025-03-15",
    }
    response = client.post("/cycles", json=payload)
    return response.json()["id"]


def test_create_farm_log(cycle_id):
    payload = {
        "cycle_id": cycle_id,
        "operation_type": "浇水",
        "operation_date": "2025-05-20",
        "operation_time": "2025-05-20T08:30:00",
        "note": "早晨浇透水",
    }
    response = client.post("/logs", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["operation_type"] == "浇水"
    assert data["operation_date"] == "2025-05-20"
    assert data["operation_time"] == "2025-05-20T08:30:00"
    assert data["note"] == "早晨浇透水"
    assert data["cycle_id"] == cycle_id


def test_list_logs_by_cycle(cycle_id):
    client.post("/logs", json={
        "cycle_id": cycle_id,
        "operation_type": "施肥",
        "operation_date": "2025-05-21",
    })

    response = client.get(f"/logs?cycle_id={cycle_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["operation_type"] == "施肥"


def test_list_logs_by_operation_type(cycle_id):
    client.post("/logs", json={
        "cycle_id": cycle_id,
        "operation_type": "浇水",
        "operation_date": "2025-05-20",
    })
    client.post("/logs", json={
        "cycle_id": cycle_id,
        "operation_type": "施肥",
        "operation_date": "2025-05-21",
    })

    response = client.get(f"/logs?cycle_id={cycle_id}&operation_type=浇水")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["operation_type"] == "浇水"


def test_create_log_invalid_cycle():
    payload = {
        "cycle_id": 99999,
        "operation_type": "浇水",
        "operation_date": "2025-05-20",
    }
    response = client.post("/logs", json=payload)
    assert response.status_code == 400


def test_update_farm_log(cycle_id):
    """测试更新农事日志。"""
    create_payload = {
        "cycle_id": cycle_id,
        "operation_type": "浇水",
        "operation_date": "2025-05-20",
        "note": "早晨浇透水",
    }
    create_resp = client.post("/logs", json=create_payload)
    log_id = create_resp.json()["id"]

    update_payload = {
        "cycle_id": cycle_id,
        "operation_type": "施肥",
        "operation_date": "2025-05-21",
        "note": "下午施复合肥",
    }
    response = client.put(f"/logs/{log_id}", json=update_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["operation_type"] == "施肥"
    assert data["operation_date"] == "2025-05-21"
    assert data["note"] == "下午施复合肥"


def test_update_log_invalid_cycle(cycle_id):
    """测试更新日志时指定不存在的 cycle 返回 400。"""
    create_payload = {
        "cycle_id": cycle_id,
        "operation_type": "浇水",
        "operation_date": "2025-05-20",
    }
    create_resp = client.post("/logs", json=create_payload)
    log_id = create_resp.json()["id"]

    update_payload = {
        "cycle_id": 99999,
        "operation_type": "施肥",
        "operation_date": "2025-05-21",
    }
    response = client.put(f"/logs/{log_id}", json=update_payload)
    assert response.status_code == 400


def test_update_log_not_found(cycle_id):
    """测试更新不存在的日志返回 400。"""
    payload = {
        "cycle_id": cycle_id,
        "operation_type": "浇水",
        "operation_date": "2025-05-20",
    }
    response = client.put("/logs/99999", json=payload)
    assert response.status_code == 400


def test_delete_farm_log(cycle_id):
    """测试删除农事日志。"""
    create_payload = {
        "cycle_id": cycle_id,
        "operation_type": "浇水",
        "operation_date": "2025-05-20",
    }
    create_resp = client.post("/logs", json=create_payload)
    log_id = create_resp.json()["id"]

    response = client.delete(f"/logs/{log_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "删除成功"

    list_resp = client.get(f"/logs?cycle_id={cycle_id}")
    assert len(list_resp.json()) == 0


def test_delete_log_not_found():
    """测试删除不存在的日志返回 404。"""
    response = client.delete("/logs/99999")
    assert response.status_code == 404
