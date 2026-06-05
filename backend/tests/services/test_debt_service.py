"""测试债务管理 Service。"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.cost import CostRecord
from app.models.farm import Farm
from app.schemas.cost import CostRecordCreate
from app.services.debt_service import (
    CATEGORY_REPAY,
    InvalidSettlementAmountError,
    SUBTYPE_DEBT,
    count_debt_records,
    create_debt_record,
    get_debt_records,
    get_debt_summary,
    settle_debt,
)


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


_test_engine = create_engine(
    "sqlite:///tests/test_debt_service.db",
    connect_args={"check_same_thread": False},
)
event.listen(_test_engine, "connect", _set_sqlite_pragma)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture
def db():
    """提供数据库会话。"""
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    session = _TestSession()
    session.add(Farm(id=1, name="默认农场"))
    session.commit()
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
        assert debt.settled_amount == Decimal("0.00")
        assert debt.settlement_status == "unsettled"

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

    def test_excludes_settled_by_settlement_fields(self, db: Session):
        """settled_at 为空但结算字段已结清的记录被排除。"""
        debt = CostRecord(
            farm_id=1,
            record_type="cost",
            category="化肥",
            amount=Decimal("100"),
            settled_amount=Decimal("100"),
            settlement_status="settled",
            record_date=date.today(),
            record_subtype=SUBTYPE_DEBT,
            counterparty="字段已结",
            settled_at=None,
        )
        db.add(debt)
        db.commit()

        debts = get_debt_records(db, farm_id=1)
        count = count_debt_records(db, farm_id=1)

        assert debts == []
        assert count == 0

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

    def test_summary_excludes_settled_by_settlement_fields(self, db: Session):
        """统计只包含未结清账单，排除结算字段已结清的历史异常记录。"""
        open_debt = CostRecord(
            farm_id=1,
            record_type="cost",
            category="化肥",
            amount=Decimal("100"),
            settled_amount=Decimal("0"),
            settlement_status="unsettled",
            record_date=date.today(),
            record_subtype=SUBTYPE_DEBT,
            counterparty="汇总过滤测试",
            settled_at=None,
        )
        settled_status_debt = CostRecord(
            farm_id=1,
            record_type="cost",
            category="化肥",
            amount=Decimal("200"),
            settled_amount=Decimal("0"),
            settlement_status="unsettled",
            record_date=date.today(),
            record_subtype=SUBTYPE_DEBT,
            counterparty="汇总过滤测试",
            settled_at=None,
        )
        fully_settled_amount_debt = CostRecord(
            farm_id=1,
            record_type="cost",
            category="化肥",
            amount=Decimal("300"),
            settled_amount=Decimal("300"),
            settlement_status="partial",
            record_date=date.today(),
            record_subtype=SUBTYPE_DEBT,
            counterparty="汇总过滤测试",
            settled_at=None,
        )
        db.add_all([open_debt, settled_status_debt, fully_settled_amount_debt])
        db.commit()
        db.execute(
            text(
                "UPDATE cost_records SET settlement_status = 'settled' WHERE id = :id"
            ),
            {"id": settled_status_debt.id},
        )
        db.commit()

        summary = get_debt_summary(db, farm_id=1)

        item = next(s for s in summary if s.counterparty == "汇总过滤测试")
        assert item.total_debt == Decimal("100")
        assert item.total_settled == Decimal("0")
        assert item.remaining == Decimal("100")
        assert item.record_count == 1

    def test_summary_empty(self, db: Session):
        """无赊账记录时返回空列表。"""
        summary = get_debt_summary(db, farm_id=1)

        assert summary == []


class TestSettleDebt:
    """测试还款结清。"""

    def test_full_settle(self, db: Session, db_debt: CostRecord):
        """全额还款，更新原记录结清。"""
        result = settle_debt(db, farm_id=1, counterparty="老王农资")

        assert result.id == db_debt.id
        assert result.record_type == "cost"
        assert result.category == "化肥"
        assert result.amount == Decimal("500")
        assert result.settled_amount == Decimal("500.00")
        assert result.unsettled_amount == Decimal("0.00")
        assert result.settlement_status == "settled"
        assert result.parent_record_id is None
        assert db_debt.settled_at is not None

    def test_partial_settle(self, db: Session, db_debt: CostRecord):
        """部分还款，更新原记录但不标记结清。"""
        result = settle_debt(
            db, farm_id=1, counterparty="老王农资", amount=Decimal("200")
        )

        assert result.id == db_debt.id
        assert result.amount == Decimal("500")
        assert result.settled_amount == Decimal("200.00")
        assert result.unsettled_amount == Decimal("300.00")
        assert result.settlement_status == "partial"
        assert db_debt.settled_at is None

    def test_partial_settle_twice_accumulates_settled_amount(
        self, db: Session, db_debt: CostRecord
    ):
        """连续两次部分还款会累加已结算金额。"""
        first = settle_debt(
            db, farm_id=1, counterparty="老王农资", amount=Decimal("100")
        )
        second = settle_debt(
            db, farm_id=1, counterparty="老王农资", amount=Decimal("150")
        )

        assert first.id == db_debt.id
        assert second.id == db_debt.id
        assert second.settled_amount == Decimal("250.00")
        assert second.unsettled_amount == Decimal("250.00")
        assert second.settlement_status == "partial"
        assert second.settled_at is None

    def test_partial_settle_with_note(self, db: Session, db_debt: CostRecord):
        """部分还款带备注，仍返回原记录。"""
        result = settle_debt(
            db,
            farm_id=1,
            counterparty="老王农资",
            amount=Decimal("200"),
            note="先还一部分",
        )

        assert result.id == db_debt.id
        assert result.settled_amount == Decimal("200.00")
        assert result.note is None
        repayment_records = (
            db.query(CostRecord)
            .filter(CostRecord.record_type == "income")
            .filter(CostRecord.category == "还款")
            .all()
        )
        child_records = (
            db.query(CostRecord)
            .filter(CostRecord.parent_record_id == db_debt.id)
            .all()
        )
        assert repayment_records == []
        assert child_records == []

    def test_settle_not_found(self, db: Session):
        """找不到赊账记录时抛出 ValueError。"""
        with pytest.raises(ValueError, match="未找到"):
            settle_debt(db, farm_id=1, counterparty="不存在")

    def test_settle_ignores_settled_by_settlement_fields(self, db: Session):
        """settled_at 为空但结算字段已结清的记录不能再结算。"""
        debt = CostRecord(
            farm_id=1,
            record_type="cost",
            category="化肥",
            amount=Decimal("100"),
            settled_amount=Decimal("100"),
            settlement_status="settled",
            record_date=date.today(),
            record_subtype=SUBTYPE_DEBT,
            counterparty="字段已结",
            settled_at=None,
        )
        db.add(debt)
        db.commit()

        with pytest.raises(ValueError, match="未找到"):
            settle_debt(db, farm_id=1, counterparty="字段已结")

    def test_settle_rejects_non_positive_amount(
        self, db: Session, db_debt: CostRecord
    ):
        """结算金额必须大于 0。"""
        with pytest.raises(InvalidSettlementAmountError, match="必须大于 0"):
            settle_debt(db, farm_id=1, counterparty="老王农资", amount=Decimal("0"))

    def test_settle_rejects_non_positive_amount_before_lookup(self, db: Session):
        """非正数金额必须先于查找账单报参数错误。"""
        with pytest.raises(InvalidSettlementAmountError, match="必须大于 0"):
            settle_debt(db, farm_id=1, counterparty="不存在", amount=Decimal("-1"))

    @pytest.mark.parametrize(
        "amount",
        [
            "abc",
            Decimal("NaN"),
            Decimal("Infinity"),
        ],
    )
    def test_settle_rejects_invalid_number_before_lookup(self, db: Session, amount):
        """非数字或非有限金额必须先于查找账单报参数错误。"""
        with pytest.raises(InvalidSettlementAmountError, match="有效数字"):
            settle_debt(db, farm_id=1, counterparty="不存在", amount=amount)

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
        assert result.record_date == date.today() + timedelta(days=-2)
        assert result.settled_amount == Decimal("100.00")
        assert result.settlement_status == "settled"
        assert result.parent_record_id is None

    def test_category_repay_kept_for_legacy_imports(self):
        """保留旧还款分类常量，兼容历史测试和调用方导入。"""
        assert CATEGORY_REPAY == "还款"
