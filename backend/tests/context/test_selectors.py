"""Context selectors 单元测试。"""

from datetime import date
from decimal import Decimal

import pytest

import app.context.selectors.core as selector_core
import app.infra.repository_runtime as repository_runtime
from app.context.selectors import (
    ConversationSelector,
    FarmSelector,
    LedgerSelector,
    RetrievalSelector,
    UserSettingsSelector,
)
from app.context.selectors.memory import MemorySelector
from app.context.selectors.planting import (
    CostCategorySelector,
    OperationWorkOrderSelector,
    PlantingUnitSelector,
    UnpaidLaborSummarySelector,
    WorkerSelector,
)
from app.memory.models import (
    KeyFactMemory,
    LongTermMemoryContext,
    MemoryContext,
    MemoryMessage,
    PendingActionSnapshot,
    UserPreferenceMemory,
)
from app.domains.conversation.models import Conversation, ConversationMessage
from app.domains.finance.cost_models import CostRecord
from app.domains.finance.cost_category_models import CostCategory
from app.domains.planting.crop_models import CropTemplate
from app.domains.planting.cycle_models import CropCycle
from app.domains.farm.models import Farm
from app.domains.planting.models import (
    LaborEntry,
    OperationWorkOrder,
    PlantingUnit,
    Worker,
)
from app.domains.users.settings_models import UserSetting


@pytest.fixture(autouse=True)
def _use_mysql_conversation_message_repository(monkeypatch) -> None:
    monkeypatch.setattr(
        repository_runtime.settings.storage,
        "conversation_messages",
        "mysql",
    )
    repository_runtime.clear_missing_table_cache()


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


def test_conversation_selector_injects_conversation_summary_block(db_session) -> None:
    conversation = Conversation(
        farm_id=1,
        user_id="test-user-001",
        session_id="summary-session",
        summary="用户正在确认西棚黄瓜预算 200 元。",
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    db_session.add(
        ConversationMessage(
            conversation_id=conversation.id,
            role="user",
            content="西棚黄瓜预算是多少？",
        )
    )
    db_session.commit()

    blocks = ConversationSelector().select(
        db_session,
        farm_id=1,
        session_id="summary-session",
    )

    blocks_by_key = {block.key: block for block in blocks}
    assert set(blocks_by_key) == {"conversation", "conversation_summary"}
    summary = blocks_by_key["conversation_summary"]
    assert summary.source == "conversation.summary"
    assert summary.priority == 50
    assert summary.compressible is True
    assert summary.min_tokens == 64
    assert summary.metadata == {"layer": "working", "cache_scope": "session"}
    assert "西棚黄瓜预算 200 元" in summary.content


def test_conversation_selector_omits_empty_summary_block(db_session) -> None:
    conversation = Conversation(
        farm_id=1,
        user_id="test-user-001",
        session_id="empty-summary-session",
        summary="",
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    db_session.add(
        ConversationMessage(
            conversation_id=conversation.id,
            role="assistant",
            content="已记录浇水。",
        )
    )
    db_session.commit()

    blocks = ConversationSelector().select(
        db_session,
        farm_id=1,
        session_id="empty-summary-session",
    )

    assert [block.key for block in blocks] == ["conversation"]


def test_conversation_selector_omits_null_summary_block(db_session) -> None:
    conversation = Conversation(
        farm_id=1,
        user_id="test-user-001",
        session_id="null-summary-session",
        summary=None,
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    db_session.add(
        ConversationMessage(
            conversation_id=conversation.id,
            role="assistant",
            content="已记录施肥。",
        )
    )
    db_session.commit()

    blocks = ConversationSelector().select(
        db_session,
        farm_id=1,
        session_id="null-summary-session",
    )

    assert [block.key for block in blocks] == ["conversation"]


def test_conversation_selector_reads_messages_through_repository(
    db_session, monkeypatch
) -> None:
    conversation = Conversation(
        farm_id=1,
        user_id="test-user-001",
        session_id="repository-session",
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)

    class FakeRepository:
        def __init__(self) -> None:
            self.kwargs = None

        def get_recent(self, **kwargs):
            self.kwargs = kwargs
            return [
                ConversationMessage(role="user", content="今晚要浇水吗？"),
                ConversationMessage(role="assistant", content="建议先看土壤湿度。"),
            ]

    repo = FakeRepository()
    monkeypatch.setattr(
        selector_core,
        "get_conversation_message_repository",
        lambda db: repo,
    )

    blocks = ConversationSelector().select(
        db_session,
        farm_id=1,
        session_id="repository-session",
    )

    assert repo.kwargs == {
        "farm_id": 1,
        "conversation_id": conversation.id,
        "limit": 6,
    }
    assert [block.key for block in blocks] == ["conversation"]
    assert blocks[0].content == "user：今晚要浇水吗？\nassistant：建议先看土壤湿度。"


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


def test_memory_selector_injects_confirmed_long_term_memory() -> None:
    memory_context = MemoryContext(
        user_id="user-1",
        farm_id=1,
        session_id="session-1",
        long_term=LongTermMemoryContext(
            user_preferences=[
                UserPreferenceMemory(
                    key="preference",
                    value="以后面积单位用亩",
                    confidence=1.0,
                )
            ],
            key_facts=[
                KeyFactMemory(
                    fact="老王就是农资店老板",
                    source="user_explicit",
                    confidence=1.0,
                )
            ],
        ),
    )

    blocks = MemorySelector().select(memory_context=memory_context)
    blocks_by_key = {block.key: block for block in blocks}

    assert blocks_by_key["long_term_memory"].source == "memory.long_term"
    assert blocks_by_key["long_term_memory"].priority == 55
    assert blocks_by_key["long_term_memory"].metadata["layer"] == "working"
    assert "偏好：以后面积单位用亩" in blocks_by_key["long_term_memory"].content
    assert "事实：老王就是农资店老板" in blocks_by_key["long_term_memory"].content


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
