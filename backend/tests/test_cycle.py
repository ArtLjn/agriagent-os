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
            {
                "name": "定植期",
                "duration_days": 1,
                "order_index": 1,
                "key_tasks": "浇定根水",
            },
            {
                "name": "伸蔓期",
                "duration_days": 20,
                "order_index": 2,
                "key_tasks": "整枝压蔓",
            },
        ],
    }
    response = client.post("/crops/templates", json=payload)
    return response.json()["id"]


def test_create_crop_cycle(watermelon_template_id):
    """测试创建茬口并验证阶段日期推算。"""
    payload = {
        "name": "1号棚西瓜",
        "crop_template_id": watermelon_template_id,
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


def test_list_crop_cycles(watermelon_template_id):
    """测试获取茬口列表。"""
    payload = {
        "name": "2号棚西瓜",
        "crop_template_id": watermelon_template_id,
        "start_date": "2025-03-15",
        "field_name": "2号大棚",
    }
    client.post("/cycles", json=payload)

    response = client.get("/cycles")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "2号棚西瓜"


def test_update_crop_cycle(watermelon_template_id):
    """测试更新茬口基本信息。"""
    create_payload = {
        "name": "1号棚西瓜",
        "crop_template_id": watermelon_template_id,
        "start_date": "2025-03-15",
        "field_name": "1号大棚",
    }
    create_resp = client.post("/cycles", json=create_payload)
    cycle_id = create_resp.json()["id"]

    update_payload = {
        "name": "1号棚改良西瓜",
        "crop_template_id": watermelon_template_id,
        "start_date": "2025-03-20",
        "field_name": "1号温室",
    }
    response = client.put(f"/cycles/{cycle_id}", json=update_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "1号棚改良西瓜"
    assert data["start_date"] == "2025-03-20"
    assert data["field_name"] == "1号温室"


def test_update_cycle_not_found(watermelon_template_id):
    """测试更新不存在的茬口返回 400。"""
    payload = {
        "name": "不存在",
        "crop_template_id": watermelon_template_id,
        "start_date": "2025-03-15",
    }
    response = client.put("/cycles/99999", json=payload)
    assert response.status_code == 400


def test_delete_crop_cycle(watermelon_template_id):
    """测试删除茬口。"""
    create_payload = {
        "name": "临时茬口",
        "crop_template_id": watermelon_template_id,
        "start_date": "2025-03-15",
    }
    create_resp = client.post("/cycles", json=create_payload)
    cycle_id = create_resp.json()["id"]

    response = client.delete(f"/cycles/{cycle_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "删除成功"

    get_resp = client.get(f"/cycles/{cycle_id}")
    assert get_resp.status_code == 404


def test_delete_cycle_not_found():
    """测试删除不存在的茬口返回 404。"""
    response = client.delete("/cycles/99999")
    assert response.status_code == 404


def test_advance_stage(watermelon_template_id):
    """测试推进茬口阶段。"""
    create_payload = {
        "name": "1号棚西瓜",
        "crop_template_id": watermelon_template_id,
        "start_date": "2025-03-15",
    }
    create_resp = client.post("/cycles", json=create_payload)
    cycle_id = create_resp.json()["id"]

    # 初始阶段：育苗期 is_current=True
    get_resp = client.get(f"/cycles/{cycle_id}")
    stages = get_resp.json()["stages"]
    assert stages[0]["is_current"] is True
    assert stages[1]["is_current"] is False

    # 推进到下一阶段
    response = client.post(f"/cycles/{cycle_id}/advance-stage")
    assert response.status_code == 200
    data = response.json()
    stages = data["stages"]
    assert stages[0]["is_current"] is False
    assert stages[1]["is_current"] is True


def test_advance_stage_last_stage(watermelon_template_id):
    """测试推进到最后一个阶段后再推进返回 400。"""
    create_payload = {
        "name": "1号棚西瓜",
        "crop_template_id": watermelon_template_id,
        "start_date": "2025-03-15",
    }
    create_resp = client.post("/cycles", json=create_payload)
    cycle_id = create_resp.json()["id"]

    # 推进两次到最后一阶段（西瓜模板有3个阶段）
    client.post(f"/cycles/{cycle_id}/advance-stage")
    client.post(f"/cycles/{cycle_id}/advance-stage")

    # 第三次推进应失败
    response = client.post(f"/cycles/{cycle_id}/advance-stage")
    assert response.status_code == 400


def test_advance_stage_not_found():
    """测试对不存在的茬口推进阶段返回 400。"""
    response = client.post("/cycles/99999/advance-stage")
    assert response.status_code == 400


def test_parse_cycle_returns_422_on_invalid_data():
    """当 LLM 返回不合法数据时，应返回 422 而非 500。"""
    from unittest.mock import patch
    from app.schemas.cycle import CycleParseResponse

    with patch("app.api.cycle._parse_cycle_with_llm") as mock_parse:
        mock_parse.return_value = CycleParseResponse(
            name="", crop_template_id=None, start_date=""
        )
        response = client.post("/cycles/parse", json={"description": "hhhhhh"})

    assert response.status_code == 422
    assert "无法识别茬口信息" in response.json()["detail"]
