from decimal import Decimal

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import event
from sqlalchemy.orm import relationship

from app.core.timezone import beijing_now, ensure_beijing_timezone
from app.core.database import Base

ACTIVE_SOURCE_KEY = "active"
PARTIAL = "partial"
SETTLED = "settled"
UNSETTLED = "unsettled"


def _quantize_money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _settlement_status_for(amount: Decimal, settled_amount: Decimal) -> str:
    if settled_amount <= 0:
        return UNSETTLED
    if settled_amount >= amount:
        return SETTLED
    return PARTIAL


class CostRecord(Base):
    """成本记账模型，记录种植周期中的成本与收入。"""

    __tablename__ = "cost_records"
    __table_args__ = (
        UniqueConstraint(
            "farm_id",
            "source_type",
            "source_id",
            "source_active_key",
            name="uq_cost_records_active_source",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True)
    record_type = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False)
    category_id = Column(Integer, ForeignKey("cost_categories.id"), nullable=True)
    category_name_snapshot = Column(String(50), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    settled_amount = Column(Numeric(10, 2), nullable=False, default=0)
    settlement_status = Column(String(20), nullable=False, default="settled")
    record_date = Column(Date, nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=True)
    note = Column(String(500), nullable=True)
    record_subtype = Column(String(50), nullable=True)
    counterparty = Column(String(100), nullable=True)
    due_date = Column(Date, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    parent_record_id = Column(Integer, ForeignKey("cost_records.id"), nullable=True)
    source_type = Column(String(50), nullable=True)
    source_id = Column(Integer, nullable=True)
    source_active_key = Column(String(20), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category_ref = relationship("CostCategory", foreign_keys=[category_id])

    @property
    def unsettled_amount(self) -> Decimal:
        """返回尚未结算金额。"""
        amount = _quantize_money(self.amount or Decimal("0.00"))
        settled_amount = _quantize_money(self.settled_amount or Decimal("0.00"))
        return max(amount - settled_amount, Decimal("0.00"))

    @property
    def source_label(self) -> str | None:
        """返回账单来源标识，供移动端避免重复录入。"""
        if self.source_type == "operation_work_order":
            return "来自农事作业单"
        if self.source_type == "labor_entry":
            return "来自工资记录"
        return None


@event.listens_for(CostRecord, "before_insert")
def _set_default_recorded_at(_mapper, _connection, record: CostRecord) -> None:
    """账务业务时间默认使用北京时间。"""
    record.recorded_at = ensure_beijing_timezone(record.recorded_at) or beijing_now()


@event.listens_for(CostRecord, "before_update")
def _normalize_recorded_at(_mapper, _connection, record: CostRecord) -> None:
    """更新时保持 recorded_at 为北京时间。"""
    record.recorded_at = ensure_beijing_timezone(record.recorded_at)


@event.listens_for(CostRecord, "before_insert")
@event.listens_for(CostRecord, "before_update")
def _sync_source_active_key(_mapper, _connection, record: CostRecord) -> None:
    """保证活动来源账单不会以空 active key 入库。"""
    if record.deleted_at is not None:
        record.source_active_key = None
    elif record.source_type is not None and record.source_id is not None:
        record.source_active_key = ACTIVE_SOURCE_KEY
    else:
        record.source_active_key = None


@event.listens_for(CostRecord, "before_insert")
@event.listens_for(CostRecord, "before_update")
def _sync_settlement_fields(_mapper, _connection, record: CostRecord) -> None:
    """统一派生结算金额和状态，覆盖模型默认值与客户端状态。"""
    amount = _quantize_money(record.amount or Decimal("0.00"))
    if record.record_subtype == "赊账" and record.settled_at is not None:
        record.settled_amount = amount
    elif record.settled_amount is None:
        if record.record_subtype == "赊账":
            record.settled_amount = Decimal("0.00")
        else:
            record.settled_amount = amount
    else:
        record.settled_amount = _quantize_money(record.settled_amount)
    record.settlement_status = _settlement_status_for(amount, record.settled_amount)
