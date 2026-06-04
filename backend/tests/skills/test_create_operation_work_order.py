"""创建农事作业单 Skill 测试。"""

import importlib
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from skillify.core.context import SkillContext

_mod = importlib.import_module(
    "app.agent.skills.create-operation-work-order.scripts.main"
)
CreateOperationWorkOrderSkill = _mod.CreateOperationWorkOrderSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


def test_skill_meta():
    skill = CreateOperationWorkOrderSkill()

    assert skill.name() == "create_operation_work_order"
    assert "授粉" in skill.description()
    assert "operation_type" in skill.parameters_schema()["required"]


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.planting_service, "create_work_order")
@patch.object(_mod.planting_read_service, "to_work_order_response")
async def test_create_pollination_work_order_with_labor(
    mock_to_response, mock_create, mock_session, ctx
):
    """自然语言提取后可写入授粉作业单和用工。"""
    db = MagicMock()
    mock_session.return_value = db
    cycle = MagicMock(id=9)
    unit = MagicMock(id=3, name="东大棚 1-3 号")
    worker = MagicMock(id=5, name="老王")
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = cycle
    db.query.return_value.filter.return_value.all.return_value = [unit]
    db.query.return_value.filter.return_value.first.return_value = worker

    response = MagicMock(
        operation_type="人工授粉",
        operation_date=date(2026, 6, 4),
        unit_names=["东大棚 1-3 号"],
        labor_entries=[MagicMock()],
        total_payable_amount=Decimal("200"),
        total_paid_amount=Decimal("200"),
        total_unpaid_amount=Decimal("0"),
    )
    mock_create.return_value = MagicMock()
    mock_to_response.return_value = response

    result = await CreateOperationWorkOrderSkill().execute(
        {
            "operation_type": "人工授粉",
            "operation_date": "2026-06-04",
            "unit_names": "东大棚 1-3 号",
            "workers": "老王",
            "unit_price": 200,
            "paid_worker": "老王",
            "paid_amount": 200,
        },
        ctx,
    )

    assert result.status.value == "success"
    assert "人工授粉" in result.reply
    work_order_create = mock_create.call_args.args[1]
    assert work_order_create.cycle_id == 9
    assert work_order_create.scope_type == "unit"
    assert work_order_create.unit_ids == [3]
    assert work_order_create.labor_entries[0].worker_id == 5
    assert work_order_create.labor_entries[0].paid_amount == Decimal("200")


@pytest.mark.asyncio
async def test_missing_operation_type(ctx):
    result = await CreateOperationWorkOrderSkill().execute({}, ctx)

    assert result.status.value == "failed"
    assert "作业类型" in result.reply
