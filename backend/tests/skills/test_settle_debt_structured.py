"""还赊账 Skill 结构化字段升级测试。"""

import importlib
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.database import Base, engine, SessionLocal
from app.models.cost import CostRecord
from app.models.farm import Farm
from app.schemas.cost import CostRecordCreate
from app.services.cost_service import create_record

_settle_mod = importlib.import_module("app.agent.skills.settle-debt.scripts.main")
SettleDebtSkill = _settle_mod.SettleDebtSkill


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前清理并重置数据库并播种默认农场。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()
    yield


@pytest.fixture
def db():
    """提供一个数据库会话。"""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def structured_debt(db: Session) -> CostRecord:
    """创建一条结构化赊账记录。"""
    record = CostRecordCreate(
        record_type="cost",
        category="化肥",
        amount=Decimal("300"),
        record_date=date.today(),
        record_subtype="赊账",
        counterparty="老王农资店",
        due_date=date.today() + timedelta(days=30),
    )
    return create_record(db, record, farm_id=1)


class TestSettleDebtSkillStructured:
    """结构化赊账记录查询与还款测试。"""

    @pytest.mark.asyncio
    async def test_find_by_counterparty_structured(
        self, db: Session, structured_debt: CostRecord
    ):
        """通过 counterparty 模糊匹配找到结构化赊账记录。"""
        skill = SettleDebtSkill()

        records = skill._find_debt_records(db, farm_id=1, counterparty="老王")

        assert len(records) == 1
        assert records[0].counterparty == "老王农资店"

    @pytest.mark.asyncio
    async def test_settle_structured_debt(
        self, db: Session, structured_debt: CostRecord
    ):
        """全额还清结构化赊账记录。"""
        skill = SettleDebtSkill()
        context = type("Context", (), {"farm_id": 1})()

        result = await skill.execute(
            {"counterparty": "老王农资店"},
            context,
        )

        assert result.status.value == "success"
        assert "300" in result.reply

    @pytest.mark.asyncio
    async def test_settle_structured_debt_sets_parent_id(
        self, db: Session, structured_debt: CostRecord
    ):
        """全额还款后原记录 settled_at 被设置，还款记录带 parent_record_id。"""
        skill = SettleDebtSkill()
        context = type("Context", (), {"farm_id": 1})()

        result = await skill.execute(
            {"counterparty": "老王农资店"},
            context,
        )

        assert result.status.value == "success"
        db.refresh(structured_debt)
        assert structured_debt.settled_at is not None

    @pytest.mark.asyncio
    async def test_structured_not_match_settled_record(
        self, db: Session, structured_debt: CostRecord
    ):
        """已结清的记录不应再被匹配到。"""
        structured_debt.settled_at = date.today()
        db.commit()
        skill = SettleDebtSkill()

        records = skill._find_debt_records(db, farm_id=1, counterparty="老王")

        assert len(records) == 0

    @pytest.mark.asyncio
    async def test_fallback_to_note_for_legacy_records(self, db: Session):
        """无结构化字段的旧数据通过 note 回退匹配。"""
        record = CostRecordCreate(
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            record_date=date.today(),
            note="赊账-老王农资店",
        )
        create_record(db, record, farm_id=1)
        skill = SettleDebtSkill()

        records = skill._find_debt_records(db, farm_id=1, counterparty="老王")

        assert len(records) == 1
        assert records[0].note == "赊账-老王农资店"

    @pytest.mark.asyncio
    async def test_structured_takes_priority_over_legacy(
        self, db: Session, structured_debt: CostRecord
    ):
        """同时存在结构化和旧记录时优先返回结构化记录。"""
        legacy = CostRecordCreate(
            record_type="cost",
            category="农药",
            amount=Decimal("100"),
            record_date=date.today(),
            note="赊账-老王农资店",
        )
        create_record(db, legacy, farm_id=1)
        skill = SettleDebtSkill()

        records = skill._find_debt_records(db, farm_id=1, counterparty="老王")

        assert len(records) == 1
        assert records[0].record_subtype == "赊账"
