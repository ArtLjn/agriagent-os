"""种植批次、作业单和轻量用工 API 测试。"""

from datetime import date
from decimal import Decimal


def _create_watermelon_template(client) -> int:
    response = client.post(
        "/crops/templates",
        json={
            "name": "西瓜",
            "variety": "8424",
            "stages": [
                {
                    "name": "播种育苗期",
                    "duration_days": 10,
                    "order_index": 0,
                    "key_tasks": "育苗",
                },
                {
                    "name": "伸蔓期",
                    "duration_days": 20,
                    "order_index": 1,
                    "key_tasks": "压蔓",
                },
            ],
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_watermelon_cycle(client) -> int:
    template_id = _create_watermelon_template(client)
    response = client.post(
        "/cycles",
        json={
            "name": "2026 春茬 8424 西瓜",
            "crop_template_id": template_id,
            "start_date": "2026-03-01",
            "field_name": "东大棚",
            "total_area_mu": "18.00",
            "season": "春茬",
            "batch_note": "兼容旧地块字段，后续拆分为棚",
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_cycle_list_shows_batch_area_and_unit_count(client):
    """批次列表展示面积、单元数和旧 field_name 兼容信息。"""
    cycle_id = _create_watermelon_cycle(client)
    for name, area in [("东大棚 1-3 号", "9.00"), ("东大棚 4-6 号", "9.00")]:
        response = client.post(
            "/planting/units",
            json={"cycle_id": cycle_id, "name": name, "area_mu": area},
        )
        assert response.status_code == 200

    response = client.get("/cycles")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["name"] == "2026 春茬 8424 西瓜"
    assert item["total_area_mu"] == "18.00"
    assert item["unit_area_mu"] == "18.00"
    assert item["unit_count"] == 2
    assert item["field_name"] == "东大棚"
    assert item["season"] == "春茬"


def test_create_work_order_with_labor_generates_cost_record(client):
    """作业单可选择多个棚和多个工人，并自动生成人工成本。"""
    cycle_id = _create_watermelon_cycle(client)
    unit_ids = []
    for name in ["东大棚 1-3 号", "东大棚 4-6 号"]:
        response = client.post(
            "/planting/units",
            json={"cycle_id": cycle_id, "name": name, "area_mu": "9.00"},
        )
        unit_ids.append(response.json()["id"])

    worker_ids = []
    for name in ["老王", "老李", "老张", "小赵"]:
        response = client.post(
            "/planting/workers",
            json={
                "name": name,
                "default_pay_type": "daily",
                "default_unit_price": "200.00",
            },
        )
        assert response.status_code == 200
        worker_ids.append(response.json()["id"])

    labor_entries = [
        {
            "worker_id": worker_ids[0],
            "pay_type": "daily",
            "quantity": "1",
            "unit_price": "200.00",
            "paid_amount": "200.00",
        },
        *[
            {
                "worker_id": worker_id,
                "pay_type": "daily",
                "quantity": "1",
                "unit_price": "200.00",
                "paid_amount": "0.00",
            }
            for worker_id in worker_ids[1:]
        ],
    ]

    response = client.post(
        "/planting/work-orders",
        json={
            "cycle_id": cycle_id,
            "operation_type": "人工授粉",
            "operation_date": date.today().isoformat(),
            "scope_type": "unit",
            "unit_ids": unit_ids,
            "note": "东大棚 4 个工人给西瓜授粉，每人 200，先付老王 200",
            "labor_entries": labor_entries,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["operation_type"] == "人工授粉"
    assert data["unit_names"] == ["东大棚 1-3 号", "东大棚 4-6 号"]
    assert data["total_payable_amount"] == "800.00"
    assert data["total_paid_amount"] == "200.00"
    assert data["total_unpaid_amount"] == "600.00"
    assert data["labor_cost_record_id"] is not None
    assert data["labor_entries"][0]["settlement_status"] == "settled"
    assert data["labor_entries"][1]["settlement_status"] == "unpaid"

    costs = client.get(f"/costs?cycle_id={cycle_id}&category=人工").json()["items"]
    assert len(costs) == 1
    assert costs[0]["amount"] == "800.00"
    assert costs[0]["source_type"] == "operation_work_order"
    assert costs[0]["source_id"] == data["id"]
    assert costs[0]["source_label"] == "来自农事作业单"

    profit = client.get(f"/costs/cycles/{cycle_id}/profit").json()
    assert Decimal(profit["total_cost"]) == Decimal("800.00")


def test_operation_types_prioritize_watermelon_templates(client):
    """西瓜批次优先展示西瓜高频作业类型。"""
    response = client.get("/planting/operation-types?crop_name=西瓜")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "压蔓" in names
    assert "人工授粉" in names
    assert "垫瓜/翻瓜" in names
    assert "装车" in names


def test_recent_operations_merges_work_orders_and_legacy_logs(client):
    """近期农事合并新作业单和旧 farm_logs。"""
    cycle_id = _create_watermelon_cycle(client)
    worker = client.post("/planting/workers", json={"name": "老王"}).json()
    client.post(
        "/planting/work-orders",
        json={
            "cycle_id": cycle_id,
            "operation_type": "压蔓",
            "operation_date": date.today().isoformat(),
            "scope_type": "cycle",
            "labor_entries": [
                {
                    "worker_id": worker["id"],
                    "quantity": "1",
                    "unit_price": "200.00",
                }
            ],
        },
    )
    client.post(
        "/logs",
        json={
            "cycle_id": cycle_id,
            "operation_type": "浇水",
            "operation_date": date.today().isoformat(),
        },
    )

    response = client.get(f"/planting/recent-operations?cycle_id={cycle_id}")

    assert response.status_code == 200
    sources = {item["source_type"] for item in response.json()}
    operations = {item["operation_type"] for item in response.json()}
    assert {"operation_work_order", "farm_log"} <= sources
    assert {"压蔓", "浇水"} <= operations


def test_unsettled_labor_summary(client):
    """未结人工按工人汇总。"""
    cycle_id = _create_watermelon_cycle(client)
    worker = client.post("/planting/workers", json={"name": "老王"}).json()
    client.post(
        "/planting/work-orders",
        json={
            "cycle_id": cycle_id,
            "operation_type": "人工授粉",
            "operation_date": date.today().isoformat(),
            "scope_type": "cycle",
            "labor_entries": [
                {
                    "worker_id": worker["id"],
                    "quantity": "1",
                    "unit_price": "200.00",
                    "paid_amount": "50.00",
                }
            ],
        },
    )

    response = client.get("/planting/labor/unsettled-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["total_unpaid"] == 150
    assert data["workers"][0]["worker_name"] == "老王"
    assert data["workers"][0]["unpaid_amount"] == 150
