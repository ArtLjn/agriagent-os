"""Context selectors 单元测试。"""

from datetime import date
from decimal import Decimal

from app.context.selectors.conversation import ConversationSelector
from app.context.selectors.farm import FarmSelector
from app.context.selectors.ledger import LedgerSelector
from app.context.selectors.memory import MemorySelector
from app.context.selectors.planting import (
    CostCategorySelector,
    OperationWorkOrderSelector,
    PlantingUnitSelector,
    UnpaidLaborSummarySelector,
    WorkerSelector,
)
from app.context.selectors.retrieval import RetrievalSelector
from app.context.selectors.user_settings import UserSettingsSelector
from app.memory.models import MemoryContext, MemoryMessage, PendingActionSnapshot
from app.models.cost import CostRecord
from app.models.cost_category import CostCategory
from app.models.crop import CropTemplate
from app.models.cycle import CropCycle
from app.models.farm import Farm
from app.models.planting import LaborEntry, OperationWorkOrder, PlantingUnit, Worker
from app.models.user_setting import UserSetting


def test_farm_selector_returns_display_name_and_location(db_session) -> None:
    farm = db_session.query(Farm).filter(Farm.id == 1).first()
    farm.location = "苏州"
    db_session.add(farm)
    db_session.commit()

    blocks = FarmSelector().select(db_session, farm_id=1)

    assert blocks[0].key == "farm"
    assert "默认农场" in blocks[0].content
    assert "苏州" in blocks[0].content


def test_ledger_selector_summarizes_current_month_cost(db_session) -> None:
    db_session.add(
        CostRecord(
            farm_id=1,
            amount=Decimal("88.50"),
            record_type="cost",
            category="肥料",
            record_date=date.today(),
            note="复合肥",
        )
    )
    db_session.commit()

    blocks = LedgerSelector().select(db_session, farm_id=1)

    assert blocks[0].key == "ledger"
    assert "88.5元" in blocks[0].content


def test_user_settings_selector_uses_user_preferences(db_session) -> None:
    db_session.add(
        UserSetting(
            user_id="test-user-001",
            default_city="南京",
            default_lat=32.0603,
            default_lon=118.7969,
        )
    )
    db_session.commit()

    blocks = UserSettingsSelector().select(db_session, farm_id=1)

    assert blocks[0].key == "user_settings"
    assert "南京" in blocks[0].content
    assert "32.0603,118.7969" in blocks[0].content


def test_in_memory_selectors_are_independently_testable() -> None:
    conversation = ConversationSelector().select(
        messages=["用户：今天浇水了吗？", "助手：昨天已记录浇水。"]
    )
    memory = MemorySelector().select(memory_summary="用户偏好少用农药")
    retrieval = RetrievalSelector().select(results=["番茄开花期控水"])

    assert conversation[0].source == "conversation"
    assert memory[0].source == "memory"
    assert retrieval[0].source == "retrieval"


def test_memory_selector_returns_short_term_memory_blocks() -> None:
    memory_context = MemoryContext(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        recent_messages=[
            MemoryMessage(role="user", content="今天浇水了吗？"),
            MemoryMessage(role="assistant", content="昨天已记录浇水。"),
        ],
        session_summary="本轮正在确认农事记录。",
        pending_action=PendingActionSnapshot(
            action_id="act-1",
            name="create_log",
            payload={"content": "记录浇水"},
        ),
    )

    blocks = MemorySelector().select(memory_context=memory_context)
    blocks_by_key = {block.key: block for block in blocks}

    assert set(blocks_by_key) == {
        "short_term_recent",
        "short_term_summary",
        "pending_action",
    }
    assert "今天浇水了吗？" in blocks_by_key["short_term_recent"].content
    assert "create_log" in blocks_by_key["pending_action"].content
    assert "记录浇水" in blocks_by_key["pending_action"].content
    assert blocks_by_key["short_term_recent"].metadata["layer"] == "working"
    assert (
        blocks_by_key["short_term_recent"].metadata
        is not blocks_by_key["short_term_summary"].metadata
    )


def test_planting_selectors_summarize_units_work_orders_workers_and_unpaid_labor(
    db_session,
) -> None:
    template = CropTemplate(farm_id=1, name="玉米")
    db_session.add(template)
    db_session.flush()
    cycle = CropCycle(
        farm_id=1,
        crop_template_id=template.id,
        name="玉米秋茬",
        start_date=date(2026, 8, 1),
        status="active",
    )
    db_session.add(cycle)
    db_session.flush()
    unit = PlantingUnit(
        farm_id=1,
        cycle_id=cycle.id,
        name="1号棚",
        area_mu=Decimal("2.5"),
    )
    worker = Worker(
        farm_id=1,
        name="张三",
        default_pay_type="daily",
        default_unit_price=Decimal("200"),
    )
    db_session.add_all([unit, worker])
    db_session.flush()
    work_order = OperationWorkOrder(
        farm_id=1,
        cycle_id=cycle.id,
        operation_type="打药",
        operation_date=date(2026, 9, 1),
        scope_type="unit",
    )
    db_session.add(work_order)
    db_session.flush()
    entry = LaborEntry(
        farm_id=1,
        work_order_id=work_order.id,
        worker_id=worker.id,
        payable_amount=Decimal("300"),
        paid_amount=Decimal("100"),
        unpaid_amount=Decimal("200"),
        unit_price=Decimal("300"),
        quantity=Decimal("1"),
        settlement_status="partial",
    )
    db_session.add(entry)
    db_session.commit()

    assert "1号棚" in PlantingUnitSelector().select(db_session, farm_id=1)[0].content
    assert (
        "打药" in OperationWorkOrderSelector().select(db_session, farm_id=1)[0].content
    )
    worker_content = WorkerSelector().select(db_session, farm_id=1)[0].content
    assert f"张三(id={worker.id}" in worker_content
    unpaid = UnpaidLaborSummarySelector().select(db_session, farm_id=1)[0]
    assert unpaid.key == "unpaid_labor"
    assert "未付200元" in unpaid.content


def test_cost_category_selector_summarizes_categories(db_session) -> None:
    db_session.add(
        CostCategory(farm_id=1, name="肥料", type="cost", icon="tag", sort_order=1)
    )
    db_session.commit()

    blocks = CostCategorySelector().select(db_session, farm_id=1)

    assert blocks[0].key == "cost_categories"
    assert "肥料(cost)" in blocks[0].content
