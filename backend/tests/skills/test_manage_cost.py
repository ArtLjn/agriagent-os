"""manage_cost 聚合 Skill 测试。"""

import importlib
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from skillify.core.context import SkillContext

from app.domains.finance.cost_models import CostRecord
from app.domains.planting.models import LaborEntry, OperationWorkOrder, Worker
from app.domains.finance.debt_service import SUBTYPE_DEBT

_manage_cost_mod = importlib.import_module("app.skills.manage-cost.scripts.main")
_records_mod = importlib.import_module("app.skills.manage-cost.scripts.records")
_debt_mod = importlib.import_module("app.skills.manage-cost.scripts.debt")

ManageCostSkill = _manage_cost_mod.ManageCostSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


def test_manage_cost_metadata_and_schema():
    skill = ManageCostSkill()
    schema = skill.parameters_schema()

    assert skill.name() == "manage_cost"
    assert "operation" in schema["required"]
    assert "create_record" in schema["properties"]["operation"]["enum"]
    assert "settle_debt" in schema["properties"]["operation"]["enum"]


@pytest.mark.asyncio
@patch.object(_records_mod, "SessionLocal")
@patch.object(_records_mod, "create_cost_record")
async def test_create_record_operation(mock_create, mock_session, ctx):
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    mock_create.return_value = MagicMock(
        record_type="cost",
        category="化肥",
        amount=Decimal("200"),
        record_date=date(2026, 5, 25),
        note=None,
    )

    result = await ManageCostSkill().execute(
        {
            "operation": "create_record",
            "amount": 200,
            "category": "化肥",
            "record_date": "2026-05-25",
        },
        ctx,
    )

    assert result.status.value == "success"
    assert "化肥" in result.reply
    record_create = mock_create.call_args[0][1]
    assert record_create.record_type == "cost"
    assert record_create.record_date == date(2026, 5, 25)
    mock_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_create_record_repayment_route_needs_clarify(ctx):
    result = await ManageCostSkill().execute(
        {
            "operation": "create_record",
            "amount": 500,
            "category": "还款",
            "record_type": "income",
            "note": "还张三",
        },
        ctx,
    )

    assert result.status.value == "need_clarify"
    assert "settle_debt" in result.reply


@pytest.mark.asyncio
async def test_unknown_operation_needs_clarify(ctx):
    result = await ManageCostSkill().execute({}, ctx)

    assert result.status.value == "need_clarify"
    assert "记账" in result.reply


@pytest.mark.asyncio
async def test_delete_record_operation(monkeypatch, db_session, ctx):
    monkeypatch.setattr(_records_mod, "SessionLocal", lambda: db_session)
    record = CostRecord(
        farm_id=1,
        record_type="cost",
        category="化肥",
        amount=Decimal("120"),
        record_date=date(2026, 6, 1),
    )
    db_session.add(record)
    db_session.commit()

    result = await ManageCostSkill().execute(
        {"operation": "delete_record", "record_id": record.id},
        ctx,
    )

    assert result.status.value == "success"
    saved = db_session.get(CostRecord, record.id)
    assert saved.deleted_at is not None


def _add_debt(
    db,
    *,
    counterparty: str,
    amount: str,
    settled_amount: str = "0",
    record_type: str = "cost",
    category: str = "种子",
) -> CostRecord:
    record = CostRecord(
        farm_id=1,
        record_type=record_type,
        category=category,
        amount=Decimal(amount),
        settled_amount=Decimal(settled_amount),
        record_date=date(2026, 6, 8),
        record_subtype=SUBTYPE_DEBT,
        counterparty=counterparty,
        note=f"{counterparty}赊账",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _add_labor_payable(db, *, worker_name: str, unpaid_amount: str) -> LaborEntry:
    worker = Worker(
        farm_id=1,
        name=worker_name,
        default_pay_type="daily",
        status="active",
    )
    db.add(worker)
    db.flush()
    work_order = OperationWorkOrder(
        farm_id=1,
        cycle_id=None,
        operation_type="定植",
        operation_date=date(2026, 6, 8),
        scope_type="cycle",
    )
    db.add(work_order)
    db.flush()
    amount = Decimal(unpaid_amount)
    entry = LaborEntry(
        farm_id=1,
        work_order_id=work_order.id,
        worker_id=worker.id,
        quantity=1,
        unit_price=amount,
        payable_amount=amount,
        paid_amount=0,
        unpaid_amount=amount,
        settlement_status="unpaid",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@pytest.mark.asyncio
async def test_query_debt_operation_reports_remaining_payable(
    monkeypatch, db_session, ctx
):
    monkeypatch.setattr(_debt_mod, "SessionLocal", lambda: db_session)
    _add_debt(db_session, counterparty="张三", amount="2000", settled_amount="500")

    result = await ManageCostSkill().execute(
        {"operation": "query_debt", "counterparty": "张三"},
        ctx,
    )

    assert result.status.value == "success"
    assert "赊账欠款汇总" in result.reply
    assert "剩余1500.00元" in result.reply
    assert result.data["total_remaining"] == "1500.00"


@pytest.mark.asyncio
async def test_query_debt_total_payable_includes_labor(monkeypatch, db_session, ctx):
    monkeypatch.setattr(_debt_mod, "SessionLocal", lambda: db_session)
    _add_debt(db_session, counterparty="张三", amount="2000", settled_amount="500")
    _add_labor_payable(db_session, worker_name="哈哈哈", unpaid_amount="100")

    result = await ManageCostSkill().execute(
        {"operation": "query_debt", "scope": "total_payable"},
        ctx,
    )

    assert result.status.value == "success"
    assert "您目前总欠款为 1600.00 元" in result.reply
    assert "普通赊账：1500.00 元" in result.reply
    assert "未付人工：100.00 元" in result.reply


@pytest.mark.asyncio
@patch.object(_debt_mod, "SessionLocal")
@patch("app.domains.finance.debt_service.settle_debt")
async def test_settle_debt_operation(mock_settle, mock_session, ctx):
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    mock_settle.return_value = MagicMock(
        amount=Decimal("1000"),
        category="大棚膜",
        settled_amount=Decimal("1000"),
        unsettled_amount=Decimal("0"),
        settlement_status="settled",
        record_date=date(2026, 5, 20),
    )

    result = await ManageCostSkill().execute(
        {"operation": "settle_debt", "counterparty": "老王", "amount": 1000},
        ctx,
    )

    assert result.status.value == "success"
    assert "老王" in result.reply
    mock_settle.assert_called_once_with(
        mock_db,
        farm_id=1,
        counterparty="老王",
        amount=Decimal("1000"),
        note=None,
    )
    mock_db.close.assert_called_once()
