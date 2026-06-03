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
    payload = {
        "name": "1号棚西瓜",
        "crop_template_id": watermelon_template_id,
        "start_date": "2025-03-15",
    }
    response = client.post("/cycles", json=payload)
    return response.json()["id"]


def test_create_cost_record(cycle_id):
    payload = {
        "cycle_id": cycle_id,
        "record_type": "cost",
        "category": "肥料",
        "amount": "800.00",
        "record_date": "2025-03-10",
        "note": "高钾肥20袋",
    }
    response = client.post("/costs", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "肥料"
    assert data["amount"] == "800.00"
    assert data["created_at"]


def test_create_income_record(cycle_id):
    payload = {
        "cycle_id": cycle_id,
        "record_type": "income",
        "category": "批发",
        "amount": "5000.00",
        "record_date": "2025-06-15",
        "note": "卖给王老板，2000斤",
    }
    response = client.post("/costs", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["record_type"] == "income"
    assert data["category"] == "批发"
    assert data["amount"] == "5000.00"
    assert data["note"] == "卖给王老板，2000斤"


def test_cycle_profit(cycle_id):
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "肥料",
            "amount": "800.00",
            "record_date": "2025-03-10",
        },
    )
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "income",
            "category": "批发",
            "amount": "5000.00",
            "record_date": "2025-06-15",
        },
    )

    response = client.get(f"/costs/cycles/{cycle_id}/profit")
    assert response.status_code == 200
    data = response.json()
    assert "total_cost" in data
    assert "total_income" in data
    assert "net_profit" in data
    assert data["total_cost"] == "800.00"
    assert data["total_income"] == "5000.00"
    assert data["net_profit"] == "4200.00"


def test_yearly_summary(cycle_id):
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "种子",
            "amount": "200.00",
            "record_date": "2025-03-01",
        },
    )
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "income",
            "category": "零售",
            "amount": "3000.00",
            "record_date": "2025-06-20",
        },
    )

    response = client.get("/costs/summary/2025")
    assert response.status_code == 200
    data = response.json()
    assert data["year"] == 2025
    assert data["total_cost"] == "200.00"
    assert data["total_income"] == "3000.00"
    assert data["net_profit"] == "2800.00"
    assert "by_category" in data


def test_cycle_profit_empty():
    response = client.get("/costs/cycles/99999/profit")
    assert response.status_code == 200
    data = response.json()
    assert data["total_cost"] == "0"
    assert data["total_income"] == "0"
    assert data["net_profit"] == "0"


def test_parse_cost_record():
    """测试 AI 帮记解析接口（需要 LLM 配置，默认跳过）。"""
    pytest.skip("需要 LLM 配置")


def test_parse_cost_record_returns_422_on_invalid_amount():
    """当 LLM 返回不合法 amount 时，应返回 422 而非 500。"""
    from unittest.mock import patch
    from app.schemas.cost import CostParseResult

    with patch("app.api.cost._parse_cost_with_llm") as mock_parse:
        mock_parse.return_value = CostParseResult(
            record_type="cost",
            category="其他",
            amount="未知",
            record_date="2025-06-01",
        )
        response = client.post("/costs/parse", json={"description": "hhhhhh"})

    assert response.status_code == 422
    assert "无法识别记账内容" in response.json()["detail"]
