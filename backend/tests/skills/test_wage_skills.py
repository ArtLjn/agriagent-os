"""工资记录 Skill 测试。"""

import importlib
from datetime import date
from decimal import Decimal

import pytest
from skillify.core.context import SkillContext

from app.models.cost import CostRecord
from app.models.crop import CropTemplate, GrowthStage
from app.models.cycle import CropCycle, CycleStage
from app.models.planting import LaborEntry

_manage_labor_payment_mod = importlib.import_module(
    "app.agent.skills.manage-labor-payment.scripts.main"
)

ManageLaborPaymentSkill = _manage_labor_payment_mod.ManageLaborPaymentSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


@pytest.fixture
def wage_skill_session(monkeypatch, db_session):
    monkeypatch.setattr(_manage_labor_payment_mod, "SessionLocal", lambda: db_session)
    return db_session


def _create_cycle(db) -> CropCycle:
    template = CropTemplate(farm_id=1, name="玉米")
    db.add(template)
    db.flush()
    db.add(
        GrowthStage(
            crop_template_id=template.id,
            name="播种期",
            duration_days=10,
            order_index=0,
        )
    )
    db.flush()
    cycle = CropCycle(
        farm_id=1,
        name="夏季玉米",
        crop_template_id=template.id,
        start_date=date(2026, 6, 1),
        total_area_mu=Decimal("12.5"),
        season="夏季",
        status="active",
    )
    db.add(cycle)
    db.flush()
    db.add(
        CycleStage(
            cycle_id=cycle.id,
            name="播种期",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 10),
            duration_days=10,
            order_index=0,
            is_current=True,
        )
    )
    db.commit()
    db.refresh(cycle)
    return cycle


@pytest.mark.asyncio
async def test_manage_labor_payment_saves_wage_and_cost(wage_skill_session, ctx):
    cycle = _create_cycle(wage_skill_session)

    result = await ManageLaborPaymentSkill().execute(
        {
            "operation": "manage_wage",
            "action": "save",
            "cycle_id": cycle.id,
            "operation_type": "采收",
            "worker_name": "老王",
            "quantity": 2,
            "unit_price": 180,
            "paid_amount": 100,
            "work_date": "2026-06-04",
        },
        ctx,
    )

    assert result.status.value == "success"
    assert "已保存工资" in result.reply
    entry = wage_skill_session.query(LaborEntry).one()
    assert entry.payable_amount == Decimal("360.00")
    assert entry.paid_amount == Decimal("100.00")
    cost = wage_skill_session.query(CostRecord).one()
    assert cost.amount == Decimal("360.00")
    assert cost.source_type == "labor_entry"


@pytest.mark.asyncio
async def test_manage_labor_payment_requires_date_for_new_wage(
    wage_skill_session, ctx
):
    cycle = _create_cycle(wage_skill_session)

    result = await ManageLaborPaymentSkill().execute(
        {
            "operation": "manage_wage",
            "action": "save",
            "cycle_id": cycle.id,
            "operation_type": "采收",
            "worker_name": "老王",
            "unit_price": 180,
        },
        ctx,
    )

    assert result.status.value == "need_clarify"
    assert "明确日期" in result.reply


@pytest.mark.asyncio
async def test_manage_labor_payment_updates_existing_wage(wage_skill_session, ctx):
    cycle = _create_cycle(wage_skill_session)
    saved = await ManageLaborPaymentSkill().execute(
        {
            "operation": "manage_wage",
            "action": "save",
            "cycle_id": cycle.id,
            "operation_type": "采收",
            "worker_name": "老王",
            "quantity": 1,
            "unit_price": 180,
            "paid_amount": 0,
            "work_date": "2026-06-04",
        },
        ctx,
    )
    assert saved.status.value == "success"
    entry = wage_skill_session.query(LaborEntry).one()

    result = await ManageLaborPaymentSkill().execute(
        {
            "operation": "manage_wage",
            "action": "update",
            "labor_entry_id": entry.id,
            "unit_price": 200,
            "paid_amount": 50,
        },
        ctx,
    )

    assert result.status.value == "success"
    assert "已更新工资" in result.reply
    entry = wage_skill_session.query(LaborEntry).filter(LaborEntry.id == entry.id).one()
    assert entry.payable_amount == Decimal("200.00")
    assert entry.paid_amount == Decimal("50.00")
    cost = wage_skill_session.query(CostRecord).one()
    assert cost.amount == Decimal("200.00")


@pytest.mark.asyncio
async def test_manage_labor_payment_update_requires_labor_entry_id(
    wage_skill_session, ctx
):
    result = await ManageLaborPaymentSkill().execute(
        {"operation": "manage_wage", "action": "update", "unit_price": 200},
        ctx,
    )

    assert result.status.value == "need_clarify"
    assert "工资记录 ID" in result.reply


@pytest.mark.asyncio
async def test_legacy_wage_fields_infer_manage_wage(wage_skill_session, ctx):
    cycle = _create_cycle(wage_skill_session)

    result = await ManageLaborPaymentSkill().execute(
        {
            "cycle_id": cycle.id,
            "operation_type": "压瓜",
            "worker_name": "李海",
            "quantity": 15,
            "unit_price": 180,
            "work_date": "2026-06-04",
        },
        ctx,
    )

    assert result.status.value == "success"
    assert "已保存工资" in result.reply
