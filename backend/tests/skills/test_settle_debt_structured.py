"""还赊账 Skill 结构化字段升级测试。"""

import importlib
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.cost import CostRecord
from app.models.farm import Farm
from app.schemas.cost import CostRecordCreate
from app.services.cost_service import create_record


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


_settle_mod = importlib.import_module("app.agent.skills.settle-debt.scripts.main")
SettleDebtSkill = _settle_mod.SettleDebtSkill

_test_engine = create_engine(
    "sqlite:///tests/test_settle_debt.db",
    connect_args={"check_same_thread": False},
)
event.listen(_test_engine, "connect", _set_sqlite_pragma)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    db = _TestSession()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()
    with patch.object(_settle_mod, "SessionLocal", _TestSession):
        yield


@pytest.fixture
def db():
    session = _TestSession()
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
    """结构化赊账记录还款测试。"""

    @pytest.mark.asyncio
    async def test_execute_updates_structured_debt_without_creating_repayment_record(
        self, db: Session, structured_debt: CostRecord
    ):
        """Skill 复用 service 更新原账单，不创建 income/还款 或子记录。"""
        skill = SettleDebtSkill()
        context = type("Context", (), {"farm_id": 1})()

        result = await skill.execute(
            {"counterparty": "老王农资店", "amount": 120},
            context,
        )

        assert result.status.value == "success"
        db.refresh(structured_debt)
        assert structured_debt.id == 1
        assert structured_debt.record_type == "cost"
        assert structured_debt.record_subtype == "赊账"
        assert structured_debt.counterparty == "老王农资店"
        assert structured_debt.settled_amount == Decimal("120.00")
        assert structured_debt.unsettled_amount == Decimal("180.00")
        assert structured_debt.settlement_status == "partial"
        assert structured_debt.settled_at is None
        repayment_records = (
            db.query(CostRecord)
            .filter(CostRecord.record_type == "income")
            .filter(CostRecord.category == "还款")
            .all()
        )
        child_records = (
            db.query(CostRecord)
            .filter(CostRecord.parent_record_id == structured_debt.id)
            .all()
        )
        assert repayment_records == []
        assert child_records == []

    @pytest.mark.asyncio
    async def test_execute_full_settle_structured_debt_updates_original_record(
        self, db: Session, structured_debt: CostRecord
    ):
        """全额还清结构化赊账记录时更新原账单结算字段。"""
        skill = SettleDebtSkill()
        context = type("Context", (), {"farm_id": 1})()

        result = await skill.execute(
            {"counterparty": "老王农资店"},
            context,
        )

        assert result.status.value == "success"
        db.refresh(structured_debt)
        assert structured_debt.settled_amount == Decimal("300.00")
        assert structured_debt.unsettled_amount == Decimal("0.00")
        assert structured_debt.settlement_status == "settled"
        assert structured_debt.settled_at is not None

    @pytest.mark.asyncio
    async def test_execute_does_not_settle_already_settled_structured_debt_again(
        self, db: Session, structured_debt: CostRecord
    ):
        """已结清记录不会再次被 service 匹配，Skill 返回失败。"""
        skill = SettleDebtSkill()
        context = type("Context", (), {"farm_id": 1})()

        first = await skill.execute(
            {"counterparty": "老王农资店"},
            context,
        )
        second = await skill.execute(
            {"counterparty": "老王农资店"},
            context,
        )

        assert first.status.value == "success"
        assert second.status.value == "failed"
        assert "未找到" in second.reply
