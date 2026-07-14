"""创建农事作业单 Skill 测试。"""

import importlib
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from skillify.core.context import SkillContext

_mod = importlib.import_module("app.agent.skills.manage-work-orders.scripts.main")
ManageWorkOrdersSkill = _mod.ManageWorkOrdersSkill


@pytest.fixture
def ctx():
    return SkillContext(farm_id=1)


def test_skill_meta():
    skill = ManageWorkOrdersSkill()

    assert skill.name() == "manage_work_orders"
    assert "授粉" in skill.description()
    assert "operation" in skill.parameters_schema()["required"]


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

    result = await ManageWorkOrdersSkill().execute(
        {
            "operation": "create_work_order",
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
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.planting_service, "create_work_order")
@patch.object(_mod.planting_read_service, "to_work_order_response")
async def test_create_work_order_normalizes_common_llm_aliases(
    mock_to_response, mock_create, mock_session, ctx
):
    """兼容模型常吐的 worker_name/work_date/planting_unit_name 等别名。"""
    db = MagicMock()
    mock_session.return_value = db
    cycle = MagicMock(id=8, name="水稻")
    unit = MagicMock(id=4, name="1号棚")
    worker = MagicMock(id=6, name="李丽")
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = cycle
    db.query.return_value.filter.return_value.all.return_value = [unit]
    db.query.return_value.filter.return_value.first.return_value = worker

    response = MagicMock(
        operation_type="采收",
        operation_date=date(2026, 6, 8),
        unit_names=["1号棚"],
        labor_entries=[MagicMock()],
        total_payable_amount=Decimal("100"),
        total_paid_amount=Decimal("0"),
        total_unpaid_amount=Decimal("100"),
    )
    mock_create.return_value = MagicMock()
    mock_to_response.return_value = response

    result = await ManageWorkOrdersSkill().execute(
        {
            "operation": "create_work_order",
            "operation_type": "采收",
            "work_date": "2026-06-08",
            "crop_cycle_name": "水稻",
            "planting_unit_name": "1号棚",
            "worker_name": "李丽",
            "payment_method": "daily",
            "unit_price": 100,
        },
        ctx,
    )

    assert result.status.value == "success"
    work_order_create = mock_create.call_args.args[1]
    assert work_order_create.cycle_id == 8
    assert work_order_create.operation_date == date(2026, 6, 8)
    assert work_order_create.scope_type == "unit"
    assert work_order_create.unit_ids == [4]
    assert work_order_create.labor_entries[0].worker_id == 6
    assert work_order_create.labor_entries[0].pay_type == "daily"
    assert work_order_create.labor_entries[0].unit_price == Decimal("100")


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.planting_service, "create_work_order")
@patch.object(_mod.planting_read_service, "to_work_order_response")
async def test_create_work_order_uses_worker_default_wage_when_unit_price_missing(
    mock_to_response, mock_create, mock_session, ctx
):
    db = MagicMock()
    mock_session.return_value = db
    cycle = MagicMock(id=8, name="水稻")
    worker = MagicMock(
        id=6,
        name="李丽",
        default_unit_price=Decimal("100"),
        default_pay_type="daily",
    )
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = cycle
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = worker

    response = MagicMock(
        operation_type="采收",
        operation_date=date(2026, 6, 8),
        unit_names=[],
        labor_entries=[MagicMock()],
        total_payable_amount=Decimal("100"),
        total_paid_amount=Decimal("0"),
        total_unpaid_amount=Decimal("100"),
    )
    mock_create.return_value = MagicMock()
    mock_to_response.return_value = response

    result = await ManageWorkOrdersSkill().execute(
        {
            "operation": "create_work_order",
            "operation_type": "采收",
            "worker_name": "李丽",
        },
        ctx,
    )

    assert result.status.value == "success"
    work_order_create = mock_create.call_args.args[1]
    assert work_order_create.labor_entries[0].unit_price == Decimal("100")
    assert work_order_create.labor_entries[0].pay_type == "daily"


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.planting_service, "create_work_order")
@patch.object(_mod.planting_read_service, "to_work_order_response")
async def test_create_work_order_no_wage_false_string_uses_default_wage(
    mock_to_response, mock_create, mock_session, ctx
):
    db = MagicMock()
    mock_session.return_value = db
    cycle = MagicMock(id=8, name="水稻")
    worker = MagicMock(
        id=6,
        name="李丽",
        default_unit_price=Decimal("100"),
        default_pay_type="daily",
    )
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = cycle
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = worker
    mock_create.return_value = MagicMock()
    mock_to_response.return_value = MagicMock(
        operation_type="采收",
        operation_date=date(2026, 6, 8),
        unit_names=[],
        labor_entries=[MagicMock()],
        total_payable_amount=Decimal("100"),
        total_paid_amount=Decimal("0"),
        total_unpaid_amount=Decimal("100"),
    )

    result = await ManageWorkOrdersSkill().execute(
        {
            "operation": "create_work_order",
            "operation_type": "采收",
            "worker_name": "李丽",
            "no_wage": "false",
        },
        ctx,
    )

    assert result.status.value == "success"
    work_order_create = mock_create.call_args.args[1]
    assert work_order_create.labor_entries[0].unit_price == Decimal("100")


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
async def test_create_work_order_asks_wage_when_missing_everywhere(mock_session, ctx):
    db = MagicMock()
    mock_session.return_value = db
    cycle = MagicMock(id=8, name="水稻")
    worker = MagicMock(
        id=6,
        name="李丽",
        default_unit_price=None,
        default_pay_type="daily",
    )
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = cycle
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = worker

    result = await ManageWorkOrdersSkill().execute(
        {
            "operation": "create_work_order",
            "operation_type": "采收",
            "worker_name": "李丽",
        },
        ctx,
    )

    assert result.status.value == "need_clarify"
    assert "工资" in result.reply
    assert "不会默认记为0" in result.reply


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
async def test_create_work_order_asks_wage_when_unit_price_is_not_finite(
    mock_session, ctx
):
    db = MagicMock()
    mock_session.return_value = db
    cycle = MagicMock(id=8, name="水稻")
    worker = MagicMock(
        id=6,
        name="李丽",
        default_unit_price=None,
        default_pay_type="daily",
    )
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = cycle
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = worker

    result = await ManageWorkOrdersSkill().execute(
        {
            "operation": "create_work_order",
            "operation_type": "采收",
            "worker_name": "李丽",
            "unit_price": "NaN",
        },
        ctx,
    )

    assert result.status.value == "need_clarify"
    assert "不会默认记为0" in result.reply


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.planting_service, "create_work_order")
@patch.object(_mod.planting_read_service, "to_work_order_response")
async def test_create_work_order_allows_explicit_no_wage(
    mock_to_response, mock_create, mock_session, ctx
):
    db = MagicMock()
    mock_session.return_value = db
    cycle = MagicMock(id=8, name="水稻")
    worker = MagicMock(
        id=6,
        name="李丽",
        default_unit_price=None,
        default_pay_type="daily",
    )
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = cycle
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = worker
    mock_create.return_value = MagicMock()
    mock_to_response.return_value = MagicMock(
        operation_type="采收",
        operation_date=date(2026, 6, 8),
        unit_names=[],
        labor_entries=[MagicMock()],
        total_payable_amount=Decimal("0"),
        total_paid_amount=Decimal("0"),
        total_unpaid_amount=Decimal("0"),
    )

    result = await ManageWorkOrdersSkill().execute(
        {
            "operation": "create_work_order",
            "operation_type": "采收",
            "worker_name": "李丽",
            "no_wage": True,
        },
        ctx,
    )

    assert result.status.value == "success"
    work_order_create = mock_create.call_args.args[1]
    assert work_order_create.labor_entries[0].unit_price == Decimal("0")


@pytest.mark.asyncio
async def test_missing_operation_type(ctx):
    result = await ManageWorkOrdersSkill().execute(
        {"operation": "create_work_order"}, ctx
    )

    assert result.status.value == "failed"
    assert "作业类型" in result.reply


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.planting_read_service, "list_operation_work_orders")
async def test_query_work_orders_operation_dispatches_to_read_service(
    mock_list, mock_session, ctx
):
    db = MagicMock()
    mock_session.return_value = db
    mock_list.return_value = []

    result = await ManageWorkOrdersSkill().execute(
        {
            "operation": "query_work_orders",
            "operation_type": "授粉",
            "limit": 5,
        },
        ctx,
    )

    assert result.status.value == "success"
    assert "未找到" in result.reply
    assert mock_list.call_args.kwargs["operation_type"] == "授粉"
    assert mock_list.call_args.kwargs["limit"] == 5


@pytest.mark.asyncio
@patch.object(_mod, "SessionLocal")
@patch.object(_mod.planting_service, "get_work_order")
@patch.object(_mod.planting_service, "update_work_order")
@patch.object(_mod.planting_read_service, "to_work_order_response")
async def test_update_work_order_operation_dispatches_to_write_service(
    mock_to_response, mock_update, mock_get, mock_session, ctx
):
    db = MagicMock()
    mock_session.return_value = db
    mock_get.return_value = MagicMock(cycle_id=8)
    mock_update.return_value = MagicMock()
    mock_to_response.return_value = MagicMock(
        id=12,
        operation_type="采收",
        operation_date=date(2026, 6, 9),
        unit_names=[],
        labor_entries=[],
    )

    result = await ManageWorkOrdersSkill().execute(
        {
            "operation": "update_work_order",
            "work_order_id": 12,
            "note": "改到明天",
        },
        ctx,
    )

    assert result.status.value == "success"
    assert "已更新农事作业单 #12" in result.reply
    update_payload = mock_update.call_args.args[2]
    assert update_payload.note == "改到明天"
