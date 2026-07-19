"""种植批次、作业单和轻量用工 API 测试。"""

from datetime import date
from decimal import Decimal

from app.domains.finance.cost_models import CostRecord
from app.domains.planting.models import LaborEntry


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
    assert response.status_code == 201
    return response.json()["id"]


def test_labor_entry_client_request_id_unique_per_farm():
    """工资幂等号必须有数据库唯一防线，避免并发重复记账。"""
    constraint = next(
        item
        for item in LaborEntry.__table__.constraints
        if item.name == "uq_labor_entries_farm_client_request"
    )

    assert [column.name for column in constraint.columns] == [
        "farm_id",
        "client_request_id",
    ]


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


def _create_cycle(client, crop_name: str, cycle_name: str) -> int:
    response = client.post(
        "/crops/templates",
        json={
            "name": crop_name,
            "variety": "常规",
            "stages": [
                {
                    "name": "生长期",
                    "duration_days": 30,
                    "order_index": 0,
                    "key_tasks": "日常管理",
                }
            ],
        },
    )
    assert response.status_code == 201
    template_id = response.json()["id"]
    response = client.post(
        "/cycles",
        json={
            "name": cycle_name,
            "crop_template_id": template_id,
            "start_date": "2026-03-01",
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


def test_create_work_order_with_labor_generates_cost_record(client, db_session):
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
    assert costs[0]["settled_amount"] == "200.00"
    assert costs[0]["unsettled_amount"] == "600.00"
    assert costs[0]["settlement_status"] == "partial"
    assert costs[0]["source_type"] == "operation_work_order"
    assert costs[0]["source_id"] == data["id"]
    assert costs[0]["source_label"] == "来自农事作业单"

    profit = client.get(f"/costs/cycles/{cycle_id}/profit").json()
    assert Decimal(profit["total_cost"]) == Decimal("800.00")

    overpaid_response = client.post(
        "/planting/work-orders",
        json={
            "cycle_id": cycle_id,
            "operation_type": "绑蔓",
            "operation_date": date.today().isoformat(),
            "scope_type": "unit",
            "unit_ids": unit_ids,
            "labor_entries": [
                {
                    "worker_id": worker_ids[0],
                    "pay_type": "daily",
                    "quantity": "1",
                    "unit_price": "100.00",
                    "paid_amount": "130.00",
                }
            ],
        },
    )

    assert overpaid_response.status_code == 200
    overpaid_work_order = overpaid_response.json()
    assert overpaid_work_order["total_payable_amount"] == "100.00"
    assert overpaid_work_order["total_paid_amount"] == "130.00"
    assert overpaid_work_order["total_unpaid_amount"] == "0.00"

    overpaid_cost = client.get(
        f"/costs?cycle_id={cycle_id}&category=人工"
        f"&source_type=operation_work_order&source_id={overpaid_work_order['id']}"
    ).json()["items"][0]
    assert overpaid_cost["amount"] == "100.00"
    assert overpaid_cost["settled_amount"] == "100.00"
    assert overpaid_cost["unsettled_amount"] == "0.00"
    assert overpaid_cost["settlement_status"] == "settled"

    stored_cost = (
        db_session.query(CostRecord)
        .filter(
            CostRecord.source_type == "operation_work_order",
            CostRecord.source_id == overpaid_work_order["id"],
        )
        .one()
    )
    assert stored_cost.amount == Decimal("100.00")
    assert stored_cost.settled_amount == Decimal("100.00")


def test_save_wage_reuses_worker_across_cycles_and_groups_history(client):
    """独立记工资按姓名复用全场工人，并按茬口返回用工历史。"""
    watermelon_cycle_id = _create_cycle(client, "西瓜", "2026 春茬西瓜")
    bean_cycle_id = _create_cycle(client, "豆角", "2026 春茬豆角")

    for cycle_id, operation_type in [
        (watermelon_cycle_id, "人工授粉"),
        (bean_cycle_id, "采收"),
    ]:
        response = client.post(
            "/planting/labor/wages",
            json={
                "cycle_id": cycle_id,
                "operation_type": operation_type,
                "worker_name": "老王",
                "quantity": "1",
                "unit_price": "200.00",
                "paid_amount": "50.00",
                "work_date": "2026-04-01",
                "client_request_id": f"老王-{cycle_id}-{operation_type}",
            },
        )
        assert response.status_code == 200

    workers = client.get("/planting/workers/summary").json()

    assert workers["total"] == 1
    worker = workers["items"][0]
    assert worker["name"] == "老王"
    assert worker["total_payable"] == "400.00"
    assert worker["total_paid"] == "100.00"
    assert worker["total_unpaid"] == "300.00"
    assert {item["cycle_id"] for item in worker["cycle_summaries"]} == {
        watermelon_cycle_id,
        bean_cycle_id,
    }


def test_save_wage_generates_single_traceable_labor_cost(client, db_session):
    """保存工资生成一条可追溯到工资记录的人工成本账单。"""
    cycle_id = _create_watermelon_cycle(client)

    response = client.post(
        "/planting/labor/wages",
        json={
            "cycle_id": cycle_id,
            "operation_type": "整枝打杈",
            "worker_name": "老王",
            "quantity": "2",
            "unit_price": "180.00",
            "paid_amount": "100.00",
            "note": "两天工资，先付 100",
            "work_date": "2026-04-02",
            "recorded_at": "2026-04-02T09:35:00+08:00",
            "client_request_id": "整枝打杈-老王-20260402",
        },
    )

    assert response.status_code == 200
    wage = response.json()
    assert wage["worker_name"] == "老王"
    assert wage["payable_amount"] == "360.00"
    assert wage["paid_amount"] == "100.00"
    assert wage["unpaid_amount"] == "260.00"
    assert wage["cost_record_id"] is not None

    costs = client.get(
        f"/costs?cycle_id={cycle_id}&category=人工&source_type=labor_entry"
    ).json()
    assert costs["total"] == 1
    cost = costs["items"][0]
    assert cost["amount"] == "360.00"
    assert cost["settled_amount"] == "100.00"
    assert cost["unsettled_amount"] == "260.00"
    assert cost["settlement_status"] == "partial"
    assert cost["source_type"] == "labor_entry"
    assert cost["source_id"] == wage["id"]
    assert cost["source_label"] == "来自工资记录"
    assert cost["recorded_at"] == "2026-04-02T09:35:00+08:00"

    overpaid_response = client.post(
        "/planting/labor/wages",
        json={
            "cycle_id": cycle_id,
            "operation_type": "压蔓",
            "worker_name": "老李",
            "quantity": "1",
            "unit_price": "120.00",
            "paid_amount": "150.00",
            "work_date": "2026-04-03",
            "client_request_id": "压蔓-老李-20260403",
        },
    )

    assert overpaid_response.status_code == 200
    overpaid_wage = overpaid_response.json()
    assert overpaid_wage["payable_amount"] == "120.00"
    assert overpaid_wage["paid_amount"] == "150.00"
    assert overpaid_wage["unpaid_amount"] == "0.00"

    overpaid_cost = client.get(
        f"/costs?cycle_id={cycle_id}&category=人工&source_type=labor_entry"
        f"&source_id={overpaid_wage['id']}"
    ).json()["items"][0]
    assert overpaid_cost["amount"] == "120.00"
    assert overpaid_cost["settled_amount"] == "120.00"
    assert overpaid_cost["unsettled_amount"] == "0.00"
    assert overpaid_cost["settlement_status"] == "settled"

    stored_cost = (
        db_session.query(CostRecord)
        .filter(
            CostRecord.source_type == "labor_entry",
            CostRecord.source_id == overpaid_wage["id"],
        )
        .one()
    )
    assert stored_cost.amount == Decimal("120.00")
    assert stored_cost.settled_amount == Decimal("120.00")


def test_duplicate_wage_save_updates_source_cost_without_duplicate_expense(client):
    """使用同一来源重复保存工资时更新原人工账单，利润支出不翻倍。"""
    cycle_id = _create_watermelon_cycle(client)
    payload = {
        "cycle_id": cycle_id,
        "operation_type": "采收",
        "worker_name": "老王",
        "quantity": "1",
        "unit_price": "200.00",
        "paid_amount": "0.00",
        "work_date": "2026-04-03",
        "client_request_id": "采收-老王-20260403",
    }

    first = client.post("/planting/labor/wages", json=payload)
    second = client.post(
        "/planting/labor/wages",
        json={**payload, "quantity": "2", "paid_amount": "150.00"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["payable_amount"] == "400.00"
    assert second.json()["paid_amount"] == "150.00"
    assert second.json()["unpaid_amount"] == "250.00"

    costs = client.get(f"/costs?cycle_id={cycle_id}&category=人工").json()
    assert costs["total"] == 1
    assert costs["items"][0]["amount"] == "400.00"
    assert costs["items"][0]["settled_amount"] == "150.00"
    assert costs["items"][0]["unsettled_amount"] == "250.00"
    assert costs["items"][0]["settlement_status"] == "partial"

    profit = client.get(f"/costs/cycles/{cycle_id}/profit").json()
    assert Decimal(profit["total_cost"]) == Decimal("400.00")


def test_save_wage_requires_client_request_id(client):
    """独立记工资必须带客户端幂等键。"""
    cycle_id = _create_watermelon_cycle(client)

    response = client.post(
        "/planting/labor/wages",
        json={
            "cycle_id": cycle_id,
            "operation_type": "采收",
            "worker_name": "老王",
            "quantity": "1",
            "unit_price": "200.00",
            "paid_amount": "0.00",
            "work_date": "2026-04-03",
        },
    )

    assert response.status_code == 422


def test_update_wage_syncs_labor_entry_context_and_cost(client):
    """按工资记录更新金额和上下文时，同步用工记录与人工账单。"""
    cycle_id = _create_watermelon_cycle(client)
    created = client.post(
        "/planting/labor/wages",
        json={
            "cycle_id": cycle_id,
            "operation_type": "采收",
            "worker_name": "老王",
            "quantity": "1",
            "unit_price": "200.00",
            "paid_amount": "0.00",
            "work_date": "2026-04-03",
            "client_request_id": "更新工资-老王-20260403",
        },
    ).json()

    response = client.patch(
        f"/planting/labor/wages/{created['id']}",
        json={
            "operation_type": "装车",
            "quantity": "2",
            "unit_price": "180.00",
            "paid_amount": "120.00",
            "note": "改为两天装车工资",
            "work_date": "2026-04-04",
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["operation_type"] == "装车"
    assert updated["payable_amount"] == "360.00"
    assert updated["paid_amount"] == "120.00"
    assert updated["unpaid_amount"] == "240.00"

    costs = client.get(
        f"/costs?cycle_id={cycle_id}&source_type=labor_entry&source_id={created['id']}"
    ).json()
    assert costs["total"] == 1
    assert costs["items"][0]["amount"] == "360.00"
    assert costs["items"][0]["note"] == "老王装车工资"

    profit = client.get(f"/costs/cycles/{cycle_id}/profit").json()
    assert Decimal(profit["total_cost"]) == Decimal("360.00")


def test_update_wage_to_zero_soft_deletes_existing_labor_cost(client):
    """工资金额更新为 0 后软删除原人工账单，利润不残留旧金额。"""
    cycle_id = _create_watermelon_cycle(client)
    created = client.post(
        "/planting/labor/wages",
        json={
            "cycle_id": cycle_id,
            "operation_type": "采收",
            "worker_name": "老王",
            "quantity": "1",
            "unit_price": "200.00",
            "paid_amount": "0.00",
            "work_date": "2026-04-03",
            "client_request_id": "归零工资-老王-20260403",
        },
    ).json()

    response = client.patch(
        f"/planting/labor/wages/{created['id']}",
        json={"quantity": "1", "unit_price": "0.00", "paid_amount": "0.00"},
    )

    assert response.status_code == 200
    assert response.json()["payable_amount"] == "0.00"

    costs = client.get(
        f"/costs?cycle_id={cycle_id}&source_type=labor_entry&source_id={created['id']}"
    ).json()
    assert costs["total"] == 0
    profit = client.get(f"/costs/cycles/{cycle_id}/profit").json()
    assert Decimal(profit["total_cost"]) == Decimal("0")


def test_profit_total_expense_equals_filtered_ledger_sum_for_labor(client):
    """利润总支出等于同茬口账单支出合计，人工成本只统计一次。"""
    cycle_id = _create_watermelon_cycle(client)
    client.post(
        "/planting/labor/wages",
        json={
            "cycle_id": cycle_id,
            "operation_type": "采收",
            "worker_name": "老王",
            "quantity": "3",
            "unit_price": "120.00",
            "paid_amount": "360.00",
            "work_date": "2026-04-04",
            "client_request_id": "采收-老王-20260404",
        },
    )
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "肥料",
            "amount": "80.00",
            "record_date": "2026-04-04",
        },
    )

    ledger = client.get(f"/costs?cycle_id={cycle_id}").json()
    ledger_total = sum(Decimal(item["amount"]) for item in ledger["items"])
    profit = client.get(f"/costs/cycles/{cycle_id}/profit").json()
    labor_ledger = client.get(
        f"/costs?cycle_id={cycle_id}&category=人工&source_type=labor_entry"
    ).json()

    assert Decimal(profit["total_cost"]) == ledger_total
    assert Decimal(profit["total_cost"]) == Decimal("440.00")
    assert labor_ledger["total"] == 1
    assert labor_ledger["items"][0]["amount"] == "360.00"


def test_profit_labor_breakdown_includes_wage_and_work_order_labor(client):
    """利润统计返回工资记录和作业单两类人工成本拆分。"""
    cycle_id = _create_watermelon_cycle(client)
    worker = client.post("/planting/workers", json={"name": "老李"}).json()
    client.post(
        "/planting/labor/wages",
        json={
            "cycle_id": cycle_id,
            "operation_type": "采收",
            "worker_name": "老王",
            "quantity": "2",
            "unit_price": "150.00",
            "paid_amount": "300.00",
            "work_date": "2026-04-05",
            "client_request_id": "利润拆分-工资-20260405",
        },
    )
    client.post(
        "/planting/work-orders",
        json={
            "cycle_id": cycle_id,
            "operation_type": "装车",
            "operation_date": "2026-04-05",
            "scope_type": "cycle",
            "labor_entries": [
                {
                    "worker_id": worker["id"],
                    "quantity": "1",
                    "unit_price": "200.00",
                    "paid_amount": "200.00",
                }
            ],
        },
    )
    client.post(
        "/costs",
        json={
            "cycle_id": cycle_id,
            "record_type": "cost",
            "category": "肥料",
            "amount": "80.00",
            "record_date": "2026-04-05",
        },
    )

    profit = client.get(f"/costs/cycles/{cycle_id}/profit").json()

    assert profit["total_cost"] == "580.00"
    assert profit["labor_cost"] == "500.00"
    assert profit["labor_entry_cost"] == "300.00"
    assert profit["operation_labor_cost"] == "200.00"


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
