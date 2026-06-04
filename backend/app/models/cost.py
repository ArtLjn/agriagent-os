from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class CostRecord(Base):
    """成本记账模型，记录种植周期中的成本与收入。"""

    __tablename__ = "cost_records"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True)
    record_type = Column(String(20), nullable=False)
    category = Column(String(50), nullable=False)
    category_id = Column(Integer, ForeignKey("cost_categories.id"), nullable=True)
    category_name_snapshot = Column(String(50), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    record_date = Column(Date, nullable=False)
    note = Column(String(500), nullable=True)
    record_subtype = Column(String(50), nullable=True)
    counterparty = Column(String(100), nullable=True)
    due_date = Column(Date, nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    parent_record_id = Column(Integer, ForeignKey("cost_records.id"), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category_ref = relationship("CostCategory", foreign_keys=[category_id])
