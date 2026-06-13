from datetime import date
from decimal import Decimal

import pytest

from app.models.cost import CostRecord
from app.models.crop import CropTemplate
from app.models.cycle import CropCycle, CycleStage
from app.models.farm import Farm
from app.models.log import FarmLog
from app.models.planting import LaborEntry, OperationWorkOrder, Worker
from app.models.user_setting import UserSetting
from app.services import report_data_service
from app.services.report_data_service import _get_month_range, _get_week_range


def test_natural_week_and_month_ranges():
    assert _get_week_range(date(2026, 6, 13)) == (
        date(2026, 6, 8),
        date(2026, 6, 14),
    )
    assert _get_month_range(date(2026, 6, 13)) == (
        date(2026, 6, 1),
        date(2026, 6, 30),
    )


@pytest.mark.asyncio
async def test_report_data_collects_work_orders_labor_and_source_refs(
    db_session, monkeypatch
):
    cycle = _create_cycle_with_stage(db_session)
    db_session.add(Farm(id=2, name="其他农场"))
    db_session.flush()
    worker = Worker(
        farm_id=1,
        name="张三",
        default_pay_type="daily",
        default_unit_price=Decimal("120.00"),
    )
    db_session.add(worker)
    db_session.flush()

    work_order = OperationWorkOrder(
        farm_id=1,
        cycle_id=cycle.id,
        operation_type="打药",
        operation_date=date(2026, 6, 10),
        scope_type="cycle",
        note="白粉病预防",
    )
    other_farm_order = OperationWorkOrder(
        farm_id=2,
        operation_type="施肥",
        operation_date=date(2026, 6, 10),
        scope_type="farm",
    )
    db_session.add_all([work_order, other_farm_order])
    db_session.flush()

    db_session.add(
        LaborEntry(
            farm_id=1,
            work_order_id=work_order.id,
            worker_id=worker.id,
            pay_type="daily",
            quantity=Decimal("2.00"),
            unit_price=Decimal("120.00"),
            payable_amount=Decimal("240.00"),
            paid_amount=Decimal("100.00"),
            unpaid_amount=Decimal("140.00"),
            settlement_status="partial",
        )
    )
    db_session.add(
        CostRecord(
            farm_id=1,
            cycle_id=cycle.id,
            record_type="cost",
            category="农药",
            amount=Decimal("88.00"),
            record_date=date(2026, 6, 11),
        )
    )
    db_session.add(
        FarmLog(
            farm_id=1,
            cycle_id=cycle.id,
            operation_type="巡田",
            operation_date=date(2026, 6, 12),
        )
    )
    db_session.add(
        UserSetting(
            user_id="test-user-001",
            default_city="苏州",
            default_lat=31.2,
            default_lon=120.6,
        )
    )
    db_session.commit()

    async def fake_fetch_weather(**_kwargs):
        return {"warnings": ["未来三天有明显降雨"]}

    monkeypatch.setattr(report_data_service.weather_service, "fetch_weather", fake_fetch_weather)

    data = await report_data_service.build_report_data_for_period(
        db_session,
        farm_id=1,
        period_start=date(2026, 6, 8),
        period_end=date(2026, 6, 14),
        report_type="weekly",
    )

    assert data.period == {
        "granularity": "week",
        "start": date(2026, 6, 8),
        "end": date(2026, 6, 14),
        "label": "2026-06-08 ~ 2026-06-14",
    }
    assert [item["operation_type"] for item in data.operation_work_orders] == ["打药"]
    assert data.labor_summary == {
        "entry_count": 1,
        "worker_count": 1,
        "payable_amount": "240",
        "paid_amount": "100",
        "unpaid_amount": "140",
        "labor_cost": "240",
    }
    assert data.metric_facts["work_order_count"] == 1
    assert data.metric_facts["labor"]["worker_count"] == 1
    assert [metric["label"] for metric in data.metrics] == [
        "农事记录",
        "作业单",
        "净收支",
        "人工成本",
    ]
    section_types = [section["type"] for section in data.sections]
    assert section_types == [
        "weekly_snapshot",
        "operation_review",
        "work_order_status",
        "crop_stage_updates",
        "finance_flow",
        "weather_risks",
        "next_actions",
    ]
    assert data.sections[0]["source_ref_ids"]
    assert data.weather["available"] is True
    weather_section = next(
        section for section in data.sections if section["type"] == "weather_risks"
    )
    assert weather_section["data"]["risk_level"] == "medium"
    assert "明显降雨" in weather_section["data"]["summary"]
    assert weather_section["data"]["action_hint"]
    assert weather_section["items"][0]["title"] == "明显降雨"
    assert weather_section["items"][0]["priority"] == 2
    assert weather_section["items"][0]["suggested_action"]
    next_actions = next(
        section for section in data.sections if section["type"] == "next_actions"
    )
    assert any(item["source"] == "weather" for item in next_actions["items"])

    source_types = {ref["source_type"] for ref in data.source_refs}
    assert {
        "crop_cycle",
        "cycle_stage",
        "farm_log",
        "operation_work_order",
        "cost_record",
        "labor_entry",
        "worker",
        "farm",
        "user_setting",
        "weather_service",
    } <= source_types
    assert any(
        ref["id"] == f"operation_work_order:{work_order.id}"
        and ref["occurred_on"] == date(2026, 6, 10)
        for ref in data.source_refs
    )


@pytest.mark.asyncio
async def test_monthly_report_marks_missing_previous_baseline(db_session, monkeypatch):
    cycle = _create_cycle_with_stage(db_session)
    db_session.add(
        CostRecord(
            farm_id=1,
            cycle_id=cycle.id,
            record_type="income",
            category="销售",
            amount=Decimal("500.00"),
            record_date=date(2026, 6, 15),
        )
    )
    db_session.commit()

    async def failing_weather(**_kwargs):
        raise RuntimeError("天气服务不可用")

    monkeypatch.setattr(report_data_service.weather_service, "fetch_weather", failing_weather)

    data = await report_data_service.build_report_data_for_period(
        db_session,
        farm_id=1,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        report_type="monthly",
    )

    assert data.previous_period["period"] == {
        "granularity": "month",
        "start": date(2026, 5, 1),
        "end": date(2026, 5, 31),
        "label": "2026-05-01 ~ 2026-05-31",
    }
    assert data.previous_period["has_baseline"] is False
    assert data.previous_period["changes"] == {}
    section_types = [section["type"] for section in data.sections]
    assert section_types == [
        "monthly_kpis",
        "period_comparison",
        "cost_structure",
        "cycle_portfolio",
        "operation_distribution",
        "labor_summary",
        "finance_exceptions",
        "next_month_plan",
    ]
    comparison = next(
        section for section in data.sections if section["type"] == "period_comparison"
    )
    assert comparison["data"]["has_baseline"] is False
    assert data.weather["available"] is False
    assert data.weather["error"]


def _create_cycle_with_stage(db_session) -> CropCycle:
    template = CropTemplate(name="番茄", variety="粉果")
    db_session.add(template)
    db_session.flush()
    cycle = CropCycle(
        farm_id=1,
        name="一号棚番茄",
        crop_template_id=template.id,
        start_date=date(2026, 6, 1),
        field_name="一号棚",
        status="active",
    )
    db_session.add(cycle)
    db_session.flush()
    db_session.add(
        CycleStage(
            cycle_id=cycle.id,
            name="开花期",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            order_index=1,
            duration_days=30,
            is_current=True,
        )
    )
    db_session.flush()
    farm = db_session.get(Farm, 1)
    farm.location = "江苏苏州"
    return cycle
