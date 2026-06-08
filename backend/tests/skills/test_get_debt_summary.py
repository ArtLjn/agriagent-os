"""赊账统计 Skill 测试。"""

import importlib
from datetime import date
from decimal import Decimal

import pytest
from skillify.core.context import SkillContext

from app.models.cost import CostRecord
from app.models.planting import LaborEntry, OperationWorkOrder, Worker
from app.services.debt_service import SUBTYPE_DEBT

_get_debt_mod = importlib.import_module(
    "app.agent.skills.get-debt-summary.scripts.main"
)
GetDebtSummarySkill = _get_debt_mod.GetDebtSummarySkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


@pytest.fixture
def skill_sessions(monkeypatch, db_session):
    monkeypatch.setattr(_get_debt_mod, "SessionLocal", lambda: db_session)
    return db_session


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


def _add_labor_payable(
    db,
    *,
    worker_name: str,
    unpaid_amount: str,
) -> LaborEntry:
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
async def test_get_debt_summary_reports_remaining_payable(skill_sessions, ctx):
    _add_debt(
        skill_sessions,
        counterparty="张三",
        amount="2000",
        settled_amount="500",
    )

    result = await GetDebtSummarySkill().execute({"counterparty": "张三"}, ctx)

    assert result.status.value == "success"
    assert "赊账欠款汇总" in result.reply
    assert "张三" in result.reply
    assert "原欠2000.00元" in result.reply
    assert "已还500.00元" in result.reply
    assert "剩余1500.00元" in result.reply
    assert result.data["total_remaining"] == "1500.00"


@pytest.mark.asyncio
async def test_get_debt_summary_defaults_to_payables_only(skill_sessions, ctx):
    _add_debt(
        skill_sessions,
        counterparty="张三",
        amount="2000",
        settled_amount="500",
        record_type="cost",
    )
    _add_debt(
        skill_sessions,
        counterparty="收瓜商",
        amount="900",
        settled_amount="100",
        record_type="income",
        category="销售",
    )

    result = await GetDebtSummarySkill().execute({}, ctx)

    assert result.status.value == "success"
    assert "张三" in result.reply
    assert "收瓜商" not in result.reply
    assert result.data["total_remaining"] == "1500.00"


@pytest.mark.asyncio
async def test_get_debt_summary_can_query_receivables(skill_sessions, ctx):
    _add_debt(
        skill_sessions,
        counterparty="收瓜商",
        amount="900",
        settled_amount="100",
        record_type="income",
        category="销售",
    )

    result = await GetDebtSummarySkill().execute({"direction": "receivable"}, ctx)

    assert result.status.value == "success"
    assert "应收赊账汇总" in result.reply
    assert "收瓜商" in result.reply
    assert "剩余800.00元" in result.reply


@pytest.mark.asyncio
async def test_get_debt_summary_empty(skill_sessions, ctx):
    result = await GetDebtSummarySkill().execute({}, ctx)

    assert result.status.value == "success"
    assert "暂无未结赊账欠款" in result.reply
    assert result.data["total_remaining"] == "0.00"


@pytest.mark.asyncio
async def test_get_debt_summary_total_payable_includes_labor_when_no_debt(
    skill_sessions, ctx
):
    _add_labor_payable(skill_sessions, worker_name="哈哈哈", unpaid_amount="100")

    result = await GetDebtSummarySkill().execute({"scope": "total_payable"}, ctx)

    assert result.status.value == "success"
    assert "您目前总欠款为 100.00 元" in result.reply
    assert "普通赊账：0.00 元" in result.reply
    assert "未付人工：100.00 元" in result.reply
    assert "哈哈哈" in result.reply
    assert "| 欠款类型 |" not in result.reply
    assert "您目前没有未结清的普通赊账欠款" not in result.reply
    assert result.data["total_remaining"] == "100.00"
    assert result.data["labor_remaining"] == "100.00"


@pytest.mark.asyncio
async def test_get_debt_summary_total_payable_combines_debt_and_labor(
    skill_sessions, ctx
):
    _add_debt(
        skill_sessions,
        counterparty="张三",
        amount="2000",
        settled_amount="500",
    )
    _add_labor_payable(skill_sessions, worker_name="哈哈哈", unpaid_amount="100")

    result = await GetDebtSummarySkill().execute({"scope": "total_payable"}, ctx)

    assert result.status.value == "success"
    assert "您目前总欠款为 1600.00 元" in result.reply
    assert "普通赊账：1500.00 元" in result.reply
    assert "未付人工：100.00 元" in result.reply
    assert "普通赊账明细：" in result.reply
    assert "未付人工明细：" in result.reply
    assert "张三" in result.reply
    assert "哈哈哈" in result.reply
    assert "| 欠款类型 |" not in result.reply
    assert result.data["total_remaining"] == "1600.00"
