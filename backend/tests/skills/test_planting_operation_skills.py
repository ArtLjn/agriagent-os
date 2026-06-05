"""种植运营 Skill 与服务测试。"""

import importlib
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from skillify.core.context import SkillContext

from app.agent.runtime.tool_executor import _parallel_tool_node
from app.agent.skills import _attach_skill_metadata
from app.infra.pending_actions import get_pending, remove_pending
from app.models.cost import CostRecord
from app.models.crop import CropTemplate, GrowthStage
from app.models.cycle import CropCycle, CycleStage
from app.models.planting import LaborEntry, OperationWorkOrder, PlantingUnit, Worker
from app.schemas.planting import (
    LaborEntryCreate,
    OperationWorkOrderCreate,
    OperationWorkOrderUpdate,
)
from app.services import planting_read_service, planting_service

_get_orders_mod = importlib.import_module(
    "app.agent.skills.get-operation-work-orders.scripts.main"
)
_update_order_mod = importlib.import_module(
    "app.agent.skills.update-operation-work-order.scripts.main"
)
_get_payables_mod = importlib.import_module(
    "app.agent.skills.get-labor-payables.scripts.main"
)
_settle_payment_mod = importlib.import_module(
    "app.agent.skills.settle-labor-payment.scripts.main"
)

GetOperationWorkOrdersSkill = _get_orders_mod.GetOperationWorkOrdersSkill
UpdateOperationWorkOrderSkill = _update_order_mod.UpdateOperationWorkOrderSkill
GetLaborPayablesSkill = _get_payables_mod.GetLaborPayablesSkill
SettleLaborPaymentSkill = _settle_payment_mod.SettleLaborPaymentSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


@pytest.fixture(autouse=True)
def clean_pending():
    remove_pending(1)
    yield
    remove_pending(1)


@pytest.fixture
def skill_sessions(monkeypatch, db_session):
    """让新增 Skill 使用当前测试会话。"""
    for module in (
        _get_orders_mod,
        _update_order_mod,
        _get_payables_mod,
        _settle_payment_mod,
    ):
        monkeypatch.setattr(module, "SessionLocal", lambda: db_session)
    return db_session


def _create_cycle(
    db,
    *,
    name: str = "夏季玉米",
    crop_name: str = "玉米",
    status: str = "active",
) -> CropCycle:
    template = CropTemplate(farm_id=1, name=crop_name)
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
        name=name,
        crop_template_id=template.id,
        start_date=date(2026, 6, 1),
        total_area_mu=Decimal("12.5"),
        season="夏季",
        batch_note="原备注",
        status=status,
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


def _create_unit(db, cycle: CropCycle, name: str = "东棚1号") -> PlantingUnit:
    unit = PlantingUnit(
        farm_id=1,
        cycle_id=cycle.id,
        name=name,
        area_mu=Decimal("2.5"),
        status="active",
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def _create_worker(db, name: str) -> Worker:
    worker = Worker(
        farm_id=1,
        name=name,
        default_pay_type="daily",
        default_unit_price=Decimal("200"),
        status="active",
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


def _create_work_order(db) -> OperationWorkOrder:
    cycle = _create_cycle(db)
    unit = _create_unit(db, cycle)
    wang = _create_worker(db, "老王")
    li = _create_worker(db, "老李")
    work_order = planting_service.create_work_order(
        db,
        OperationWorkOrderCreate(
            cycle_id=cycle.id,
            operation_type="人工授粉",
            operation_date=date(2026, 6, 4),
            scope_type="unit",
            unit_ids=[unit.id],
            note="上午完成",
            labor_entries=[
                LaborEntryCreate(
                    worker_id=wang.id,
                    quantity=Decimal("1"),
                    unit_price=Decimal("200"),
                    paid_amount=Decimal("100"),
                ),
                LaborEntryCreate(
                    worker_id=li.id,
                    quantity=Decimal("1"),
                    unit_price=Decimal("180"),
                    paid_amount=Decimal("0"),
                ),
            ],
        ),
        farm_id=1,
    )
    db.refresh(work_order)
    return work_order


def test_list_operation_work_orders_filters_and_returns_payment_summary(db_session):
    work_order = _create_work_order(db_session)

    items = planting_read_service.list_operation_work_orders(
        db_session,
        farm_id=1,
        operation_type="授粉",
        worker_name="老王",
        payment_status="partial",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    assert [item.id for item in items] == [work_order.id]
    response = planting_read_service.to_work_order_response(items[0])
    assert response.operation_date == date(2026, 6, 4)
    assert response.unit_names == ["东棚1号"]
    assert response.total_payable_amount == Decimal("380.00")
    assert response.total_paid_amount == Decimal("100.00")
    assert response.total_unpaid_amount == Decimal("280.00")


def test_update_work_order_can_correct_scope_worker_and_payment(db_session):
    work_order = _create_work_order(db_session)
    new_unit = _create_unit(db_session, work_order.cycle, name="西棚2号")

    updated = planting_service.update_work_order(
        db_session,
        work_order.id,
        OperationWorkOrderUpdate(
            operation_type="压蔓",
            operation_date=date(2026, 6, 5),
            scope_type="unit",
            unit_ids=[new_unit.id],
            note="改为下午",
            labor_entries=[
                LaborEntryCreate(
                    worker_id=work_order.labor_entries[0].worker_id,
                    quantity=Decimal("1"),
                    unit_price=Decimal("220"),
                    paid_amount=Decimal("220"),
                )
            ],
        ),
        farm_id=1,
    )

    assert updated.operation_type == "压蔓"
    assert updated.operation_date == date(2026, 6, 5)
    assert [link.unit.name for link in updated.unit_links] == ["西棚2号"]
    assert len(updated.labor_entries) == 1
    assert updated.labor_entries[0].payable_amount == Decimal("220.00")
    assert updated.labor_entries[0].paid_amount == Decimal("220.00")
    assert updated.labor_entries[0].settlement_status == "settled"


def test_update_work_order_clears_labor_cost_when_labor_entries_removed(db_session):
    work_order = _create_work_order(db_session)
    assert work_order.labor_cost_record_id is not None
    cost_record_id = work_order.labor_cost_record_id

    updated = planting_service.update_work_order(
        db_session,
        work_order.id,
        OperationWorkOrderUpdate(labor_entries=[]),
        farm_id=1,
    )

    cost_record = db_session.get(CostRecord, cost_record_id)
    assert updated.labor_entries == []
    assert updated.labor_cost_record_id is None
    assert cost_record is not None
    assert cost_record.deleted_at is not None
    assert cost_record.source_active_key is None


def test_list_operation_work_orders_filters_payment_status_before_limit(db_session):
    for index in range(3):
        cycle = _create_cycle(db_session, name=f"无用工玉米{index}")
        planting_service.create_work_order(
            db_session,
            OperationWorkOrderCreate(
                cycle_id=cycle.id,
                operation_type="巡棚",
                operation_date=date(2026, 6, 10 + index),
                scope_type="cycle",
                labor_entries=[],
            ),
            farm_id=1,
        )
    matching = _create_work_order(db_session)

    items = planting_read_service.list_operation_work_orders(
        db_session,
        farm_id=1,
        payment_status="partial",
        limit=1,
    )

    assert [item.id for item in items] == [matching.id]


def test_list_and_settle_labor_payables(db_session):
    work_order = _create_work_order(db_session)

    payables = planting_read_service.list_labor_payables(
        db_session,
        farm_id=1,
        worker_name="老王",
    )
    assert len(payables) == 1
    assert payables[0].unpaid_amount == Decimal("100.00")

    result = planting_service.settle_labor_payment(
        db_session,
        farm_id=1,
        amount=Decimal("60"),
        worker_name="老王",
        work_order_id=work_order.id,
    )

    assert result["paid_amount"] == Decimal("60.00")
    entry = db_session.get(LaborEntry, payables[0].id)
    assert entry.paid_amount == Decimal("160.00")
    assert entry.unpaid_amount == Decimal("40.00")
    assert entry.settlement_status == "partial"


@pytest.mark.asyncio
async def test_get_operation_work_orders_skill(skill_sessions, ctx):
    _create_work_order(skill_sessions)

    result = await GetOperationWorkOrdersSkill().execute(
        {"operation_type": "授粉", "worker": "老王", "payment_status": "partial"},
        ctx,
    )

    assert result.status.value == "success"
    assert "人工授粉" in result.reply
    assert "东棚1号" in result.reply
    assert "应付380.00元" in result.reply
    assert "未付280.00元" in result.reply


@pytest.mark.asyncio
async def test_get_labor_payables_skill(skill_sessions, ctx):
    _create_work_order(skill_sessions)

    result = await GetLaborPayablesSkill().execute({"worker": "老王"}, ctx)

    assert result.status.value == "success"
    assert "老王" in result.reply
    assert "未付100.00元" in result.reply
    assert "人工授粉" in result.reply


@pytest.mark.asyncio
async def test_update_operation_work_order_skill(skill_sessions, ctx):
    work_order = _create_work_order(skill_sessions)

    result = await UpdateOperationWorkOrderSkill().execute(
        {
            "work_order_id": work_order.id,
            "operation_date": "2026-06-05",
            "operation_type": "压蔓",
            "workers": "老李",
            "unit_price": 210,
            "paid_amount": 210,
            "note": "纠正记录",
        },
        ctx,
    )

    assert result.status.value == "success"
    updated = skill_sessions.get(OperationWorkOrder, work_order.id)
    assert updated.operation_type == "压蔓"
    assert updated.operation_date == date(2026, 6, 5)
    assert [entry.worker.name for entry in updated.labor_entries] == ["老李"]
    assert updated.labor_entries[0].paid_amount == Decimal("210.00")


@pytest.mark.asyncio
async def test_settle_labor_payment_skill(skill_sessions, ctx):
    _create_work_order(skill_sessions)

    result = await SettleLaborPaymentSkill().execute(
        {"worker": "老王", "amount": 60},
        ctx,
    )

    assert result.status.value == "success"
    assert "已结算人工60.00元" in result.reply
    assert "剩余未付40.00元" in result.reply


@pytest.mark.asyncio
async def test_settle_labor_payment_skill_accepts_worker_name_alias(skill_sessions, ctx):
    _create_work_order(skill_sessions)

    result = await SettleLaborPaymentSkill().execute(
        {"worker_name": "老王", "amount": 60},
        ctx,
    )

    assert result.status.value == "success"
    assert "已结算人工60.00元" in result.reply
    payables = planting_read_service.list_labor_payables(
        skill_sessions,
        farm_id=1,
        worker_name="老李",
    )
    assert payables[0].unpaid_amount == Decimal("180.00")


@pytest.mark.asyncio
async def test_create_work_order_pending_context_includes_full_labor_details():
    tool = SimpleNamespace(
        name="create_operation_work_order",
        args_schema=None,
        ainvoke=AsyncMock(return_value="不应直接执行"),
    )
    _attach_skill_metadata(tool, SimpleNamespace(metadata=lambda: {
        "permission_level": "write_confirm",
        "risk_level": "medium",
        "context_dependencies": ["active_cycles", "planting_units", "workers"],
        "cache_invalidation": ["farm_logs", "cost_summary", "get_farm_status"],
        "confirmation_schema": {
            "target_fields": ["operation_type", "operation_date", "cycle_id"],
            "changed_fields": ["unit_names", "workers", "payable_amount"],
            "inferred_fields": ["operation_date", "cycle_id"],
            "editable_fields": [
                "operation_type",
                "operation_date",
                "cycle_id",
                "unit_names",
                "workers",
                "unit_price",
                "paid_worker",
                "paid_amount",
            ],
            "risk_notes": ["确认后会创建作业单和人工成本。"],
        },
        "evaluation_tags": ["write", "operation_work_order"],
    }))
    state = {
        "messages": [
            HumanMessage(content="昨天东棚授粉，老王老李各200，付老王200"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tc1",
                        "name": "create_operation_work_order",
                        "args": {
                            "operation_type": "人工授粉",
                            "operation_date": "2026-06-04",
                            "cycle_id": 9,
                            "unit_names": "东棚",
                            "workers": "老王,老李",
                            "unit_price": 200,
                            "paid_worker": "老王",
                            "paid_amount": 200,
                        },
                    }
                ],
            ),
        ],
        "farm_id": 1,
    }

    with patch(
        "app.agent.runtime.tool_executor.get_langchain_tools",
        return_value=[tool],
    ), patch(
        "app.agent.runtime.tool_executor.get_collector",
        return_value=MagicMock(),
    ):
        result = await _parallel_tool_node(state)

    pending = get_pending(1)
    assert pending is not None
    context = pending.confirmation_context
    assert context["target"]["operation_type"] == "人工授粉"
    assert context["target"]["operation_date"] == "2026-06-04"
    assert context["target"]["cycle_id"] == 9
    assert context["scope"]["units"] == ["东棚"]
    assert context["labor"]["workers"] == ["老王", "老李"]
    assert context["labor"]["payable_amount"] == "400.00"
    assert context["labor"]["paid_amount"] == "200.00"
    assert context["labor"]["unpaid_amount"] == "200.00"
    assert "paid_worker" in context["inferred_fields"]
    assert "workers" in context["editable_fields"]
    assert "人工：老王、老李" in result["messages"][0].content
