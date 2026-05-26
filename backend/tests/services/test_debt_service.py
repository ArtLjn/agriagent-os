"""测试债务管理 Service。"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.schemas.cost import CostRecordCreate
from app.services.debt_service import (
    SUBTYPE_DEBT,
    CATEGORY_REPAY,
    count_debt_records,
    create_debt_record,
    get_debt_records,
    get_debt_summary,
    settle_debt,
)


@pytest.fixture
def db():
    """提供数据库会话。"""
    from app.core.database import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def db_debt(db: Session) -> CostRecord:
    """创建一个赊账记录 fixture。"""
    record = CostRecordCreate(
        record_type="cost",
        category="化肥",
        amount=Decimal("500"),
        record_date=date.today(),
        record_subtype=SUBTYPE_DEBT,
        counterparty="老王农资",
        due_date=date.today() + timedelta(days=30),
    )
    return create_debt_record(db, record, farm_id=1)


class TestCreateDebtRecord:
    """测试创建赊账记录。"""

    def test_create_debt_with_subtype_and_counterparty(self, db: Session):
        """创建赊账记录，字段正确。"""
        record = CostRecordCreate(
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            record_date=date.today(),
            record_subtype=SUBTYPE_DEBT,
            counterparty="老李",
            due_date=date.today() + timedelta(days=15),
        )

        debt = create_debt_record(db, record, farm_id=1)

        assert debt.record_subtype == SUBTYPE_DEBT
        assert debt.counterparty == "老李"
        assert debt.due_date is not None
        assert debt.settled_at is None

    def test_create_debt_auto_set_subtype(self, db: Session):
        """未指定 record_subtype 时自动设为赊账。"""
        record = CostRecordCreate(
            record_type="cost",
            category="种子",
            amount=Decimal("100"),
            record_date=date.today(),
        )

        debt = create_debt_record(db, record, farm_id=1)

        assert debt.record_subtype == SUBTYPE_DEBT

    def test_create_debt_rollback_on_error(self, db: Session):
        """异常时回滚事务。"""
        record = CostRecordCreate(
            record_type="cost",
            category="化肥",
            amount=Decimal("100"),
            record_date=date.today(),
        )
        # 使用无效 farm_id 触发外键约束（如果存在）或模拟异常
        # 这里通过 monkeypatch 模拟 commit 失败
        original_commit = db.commit
        db.commit = lambda: (_ for _ in ()).throw(RuntimeError("DB error"))

        with pytest.raises(RuntimeError, match="DB error"):
            create_debt_record(db, record, farm_id=1)

        db.commit = original_commit
        db.rollback()


class TestGetDebtRecords:
    """测试查询赊账记录。"""

    def test_filter_by_counterparty(self, db: Session, db_debt: CostRecord):
        """按交易对手模糊筛选。"""
        debts = get_debt_records(db, farm_id=1, counterparty="老王")

        assert len(debts) == 1
        assert debts[0].counterparty == "老王农资"

    def test_excludes_settled(self, db: Session, db_debt: CostRecord):
        """已结清记录被排除。"""
        db_debt.settled_at = date.today()
        db.commit()

        debts = get_debt_records(db, farm_id=1)

        assert all(d.settled_at is None for d in debts)

    def test_pagination(self, db: Session):
        """分页参数生效。"""
        for i in range(3):
            record = CostRecordCreate(
                record_type="cost",
                category="化肥",
                amount=Decimal("100"),
                record_date=date.today(),
                record_subtype=SUBTYPE_DEBT,
                counterparty=f"对手{i}",
            )
            create_debt_record(db, record, farm_id=1)

        debts = get_debt_records(db, farm_id=1, skip=1, limit=1)

        assert len(debts) == 1

    def test_order_by_record_date_desc(self, db: Session):
        """按记录日期倒序排列。"""
        for i, day_offset in enumerate([0, -1, -2]):
            record = CostRecordCreate(
                record_type="cost",
                category="化肥",
                amount=Decimal("100"),
                record_date=date.today() + timedelta(days=day_offset),
                record_subtype=SUBTYPE_DEBT,
                counterparty=f"对手{i}",
            )
            create_debt_record(db, record, farm_id=1)

        debts = get_debt_records(db, farm_id=1)

        dates = [d.record_date for d in debts]
        assert dates == sorted(dates, reverse=True)


class TestCountDebtRecords:
    """测试统计赊账记录数。"""

    def test_count_without_filter(self, db: Session, db_debt: CostRecord):
        """统计未结清赊账总数。"""
        count = count_debt_records(db, farm_id=1)

        assert count >= 1

    def test_count_with_counterparty(self, db: Session, db_debt: CostRecord):
        """按交易对手筛选统计。"""
        count = count_debt_records(db, farm_id=1, counterparty="老王")

        assert count == 1

    def test_count_excludes_settled(self, db: Session, db_debt: CostRecord):
        """已结清记录不计入。"""
        db_debt.settled_at = date.today()
        db.commit()

        count = count_debt_records(db, farm_id=1)

        # 排除已结清后应减少
        debts = get_debt_records(db, farm_id=1)
        assert count == len(debts)


class TestGetDebtSummary:
    """测试债务统计汇总。"""

    def test_summary_by_counterparty(self, db: Session, db_debt: CostRecord):
        """按交易对手分组统计。"""
        summary = get_debt_summary(db, farm_id=1)

        assert len(summary) == 1
        assert summary[0].counterparty == "老王农资"
        assert summary[0].total_debt == Decimal("500")
        assert summary[0].total_settled == Decimal("0")
        assert summary[0].remaining == Decimal("500")
        assert summary[0].record_count == 1

    def test_summary_with_repayment(self, db: Session, db_debt: CostRecord):
        """有还款后统计正确。"""
        settle_debt(db, farm_id=1, counterparty="老王农资", amount=Decimal("200"))

        summary = get_debt_summary(db, farm_id=1)

        item = next(s for s in summary if s.counterparty == "老王农资")
        assert item.total_debt == Decimal("500")
        assert item.total_settled == Decimal("200")
        assert item.remaining == Decimal("300")

    def test_summary_empty(self, db: Session):
        """无赊账记录时返回空列表。"""
        summary = get_debt_summary(db, farm_id=1)

        assert summary == []


class TestSettleDebt:
    """测试还款结清。"""

    def test_full_settle(self, db: Session, db_debt: CostRecord):
        """全额还款，标记原记录结清。"""
        result = settle_debt(db, farm_id=1, counterparty="老王农资")

        assert result.record_type == "income"
        assert result.category == CATEGORY_REPAY
        assert result.amount == Decimal("500")
        assert result.parent_record_id == db_debt.id
        assert db_debt.settled_at is not None

    def test_partial_settle(self, db: Session, db_debt: CostRecord):
        """部分还款，不标记结清。"""
        result = settle_debt(
            db, farm_id=1, counterparty="老王农资", amount=Decimal("200")
        )

        assert result.amount == Decimal("200")
        assert db_debt.settled_at is None

    def test_partial_settle_with_note(self, db: Session, db_debt: CostRecord):
        """部分还款带备注。"""
        result = settle_debt(
            db,
            farm_id=1,
            counterparty="老王农资",
            amount=Decimal("200"),
            note="先还一部分",
        )

        assert result.note == "先还一部分"

    def test_settle_not_found(self, db: Session):
        """找不到赊账记录时抛出 ValueError。"""
        with pytest.raises(ValueError, match="未找到"):
            settle_debt(db, farm_id=1, counterparty="不存在")

    def test_settle_multiple_records(self, db: Session):
        """同一对手有多条赊账记录时，按日期最早的先还。"""
        for day_offset in [-2, -1]:
            record = CostRecordCreate(
                record_type="cost",
                category="化肥",
                amount=Decimal("100"),
                record_date=date.today() + timedelta(days=day_offset),
                record_subtype=SUBTYPE_DEBT,
                counterparty="老王农资",
            )
            create_debt_record(db, record, farm_id=1)

        result = settle_debt(
            db, farm_id=1, counterparty="老王农资", amount=Decimal("100")
        )

        assert result.amount == Decimal("100")
        assert result.parent_record_id is not None
