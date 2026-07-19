from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.prompt.registry import get_registry
from app.domains.finance.cost_models import CostRecord
from app.domains.finance.cost_schemas import CostRecordUpdate
from app.domains.farm.report_data_service import _build_report_data

client = TestClient(app)
get_registry().reload(Path(__file__).parent.parent / "prompts")


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
    assert data["recorded_at"]


def test_create_cost_record_defaults_recorded_at_to_beijing_time(cycle_id, monkeypatch):
    fixed_time = datetime(2026, 6, 8, 9, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    monkeypatch.setattr("app.domains.finance.cost_service.beijing_now", lambda: fixed_time)
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
    assert data["recorded_at"] == fixed_time.isoformat()


def test_create_settled_cost_record_defaults_settlement_fields(cycle_id):
    payload = {
        "cycle_id": cycle_id,
        "record_type": "cost",
        "category": "肥料",
        "amount": "100.00",
        "record_date": "2025-03-10",
    }

    response = client.post("/costs", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == "100.00"
    assert data["settled_amount"] == "100.00"
    assert data["unsettled_amount"] == "0.00"
    assert data["settlement_status"] == "settled"


def test_create_record_rejects_settled_amount_greater_than_amount(cycle_id):
    payload = {
        "cycle_id": cycle_id,
        "record_type": "cost",
        "category": "肥料",
        "amount": "100.00",
        "settled_amount": "120.00",
        "record_date": "2025-03-10",
    }

    response = client.post("/costs", json=payload)

    assert response.status_code == 422


def test_cost_update_rejects_settled_amount_greater_than_amount():
    with pytest.raises(ValidationError):
        CostRecordUpdate(
            amount=Decimal("100.00"),
            settled_amount=Decimal("120.00"),
        )


def test_direct_cost_record_normalizes_settlement_fields(db_session):
    debt_record = CostRecord(
        farm_id=1,
        record_type="cost",
        category="肥料",
        amount="180.00",
        record_subtype="赊账",
        settlement_status="settled",
        record_date=date(2025, 3, 10),
    )
    labor_record = CostRecord(
        farm_id=1,
        record_type="cost",
        category="人工",
        amount="240.00",
        record_subtype="工资记录人工",
        record_date=date(2025, 3, 11),
    )

    db_session.add_all([debt_record, labor_record])
    db_session.commit()
    db_session.refresh(debt_record)
    db_session.refresh(labor_record)

    assert debt_record.settled_amount == Decimal("0.00")
    assert debt_record.unsettled_amount == debt_record.amount
    assert debt_record.settlement_status == "unsettled"
    assert labor_record.settled_amount == labor_record.amount
    assert labor_record.unsettled_amount == Decimal("0.00")
    assert labor_record.settlement_status == "settled"

    debt_record.settled_at = datetime.now(ZoneInfo("Asia/Shanghai"))
    db_session.commit()
    db_session.refresh(debt_record)

    assert debt_record.settled_amount == debt_record.amount
    assert debt_record.unsettled_amount == Decimal("0.00")
    assert debt_record.settlement_status == "settled"


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
    assert data["settled_cost"] == "800.00"
    assert data["unsettled_cost"] == "0.00"
    assert data["settled_income"] == "5000.00"
    assert data["unsettled_income"] == "0.00"
    assert data["labor_cost"] == "0"
    assert data["labor_entry_cost"] == "0"
    assert data["operation_labor_cost"] == "0"


def test_source_cost_record_unique_and_recreatable_after_delete(cycle_id):
    """普通账单 API 同来源活动账单不能重复，软删除后可重新创建。"""
    payload = {
        "cycle_id": cycle_id,
        "record_type": "cost",
        "category": "人工",
        "amount": "120.00",
        "record_date": "2025-03-10",
        "source_type": "labor_entry",
        "source_id": 98765,
    }
    first = client.post("/costs", json=payload)
    duplicate = client.post("/costs", json={**payload, "amount": "180.00"})

    assert first.status_code == 200
    assert first.json()["source_active_key"] == "active"
    assert duplicate.status_code == 409

    deleted = client.delete(f"/costs/{first.json()['id']}")
    recreated = client.post("/costs", json={**payload, "amount": "180.00"})

    assert deleted.status_code == 200
    assert deleted.json()["source_active_key"] is None
    assert recreated.status_code == 200
    assert recreated.json()["amount"] == "180.00"


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


def test_yearly_summary_separates_occurred_settled_and_unsettled(cycle_id):
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "肥料",
            "amount": "100.00",
            "record_date": "2025-03-01",
        },
    )
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "农资赊账",
            "amount": "80.00",
            "settled_amount": "0.00",
            "record_date": "2025-03-02",
        },
    )
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "income",
            "category": "批发未收款",
            "amount": "200.00",
            "settled_amount": "0.00",
            "record_date": "2025-03-03",
        },
    )

    response = client.get("/costs/summary/2025")

    assert response.status_code == 200
    data = response.json()
    assert data["total_cost"] == "180.00"
    assert data["settled_cost"] == "100.00"
    assert data["unsettled_cost"] == "80.00"
    assert data["total_income"] == "200.00"
    assert data["settled_income"] == "0.00"
    assert data["unsettled_income"] == "200.00"
    assert data["net_profit"] == "20.00"


def test_legacy_repayment_record_is_excluded_from_income_summary(cycle_id):
    debt_response = client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "农资赊账",
            "amount": "80.00",
            "settled_amount": "0.00",
            "record_date": "2025-03-01",
        },
    )
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "income",
            "category": "还款",
            "amount": "80.00",
            "record_date": "2025-03-02",
            "parent_record_id": debt_response.json()["id"],
        },
    )

    response = client.get("/costs/summary/2025")
    profit_response = client.get(f"/costs/cycles/{cycle_id}/profit")

    assert response.status_code == 200
    data = response.json()
    assert data["total_cost"] == "80.00"
    assert data["total_income"] == "0"
    assert data["net_profit"] == "-80.00"
    assert "income:还款" not in data["by_category"]

    assert profit_response.status_code == 200
    profit_data = profit_response.json()
    assert profit_data["total_income"] == "0"
    assert profit_data["net_profit"] == "-80.00"


def test_legacy_repayment_record_is_excluded_from_report_data(cycle_id, db_session):
    debt_response = client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "农资赊账",
            "amount": "80.00",
            "settled_amount": "0.00",
            "record_date": "2025-03-01",
        },
    )
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "income",
            "category": "还款",
            "amount": "80.00",
            "record_date": "2025-03-02",
            "parent_record_id": debt_response.json()["id"],
        },
    )

    report_data = _build_report_data(
        db_session,
        farm_id=1,
        period_start=date(2025, 3, 1),
        period_end=date(2025, 3, 31),
        report_type="monthly",
    )

    assert report_data.overview["total_cost"] == "80"
    assert report_data.overview["total_income"] == "0"
    assert report_data.overview["net_profit"] == "-80"
    assert all(cost["category"] != "还款" for cost in report_data.costs)


def test_recently_settled_old_debt_surfaces_in_cost_list(cycle_id):
    debt_response = client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "农资赊账",
            "amount": "80.00",
            "settled_amount": "0.00",
            "record_subtype": "赊账",
            "counterparty": "老王农资店",
            "record_date": "2025-03-01",
        },
    )
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "肥料",
            "amount": "120.00",
            "record_date": "2026-06-01",
        },
    )

    settle_response = client.post(
        "/debts/settle",
        json={"counterparty": "老王农资店"},
    )
    list_response = client.get("/costs", params={"page": 1, "size": 10})

    assert debt_response.status_code == 200
    assert settle_response.status_code == 200
    assert list_response.status_code == 200
    first = list_response.json()["items"][0]
    assert first["id"] == debt_response.json()["id"]
    assert first["settlement_status"] == "settled"
    assert first["settled_amount"] == "80.00"
    assert first["unsettled_amount"] == "0.00"
    assert first["settled_at"] is not None


def test_cost_list_filters_by_record_month_range(cycle_id):
    for category, record_date in [
        ("五月肥料", "2026-05-31"),
        ("六月肥料", "2026-06-01"),
        ("六月种子", "2026-06-30"),
        ("七月肥料", "2026-07-01"),
    ]:
        response = client.post(
            "/costs",
            json={
                "cycle_id": cycle_id,
                "record_type": "cost",
                "category": category,
                "amount": "100.00",
                "record_date": record_date,
            },
        )
        assert response.status_code == 200

    response = client.get(
        "/costs",
        params={
            "cycle_id": cycle_id,
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
            "page": 1,
            "size": 10,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert [item["category"] for item in data["items"]] == ["六月种子", "六月肥料"]


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
    from app.domains.finance.cost_schemas import CostParseResult

    with patch("app.application.smart_fill.parse_with_llm") as mock_parse:
        mock_parse.return_value = CostParseResult(
            record_type="cost",
            category="其他",
            amount="未知",
            record_date="2025-06-01",
        )
        response = client.post("/costs/parse", json={"description": "hhhhhh"})

    assert response.status_code == 422
    assert "无法识别记账内容" in response.json()["detail"]
