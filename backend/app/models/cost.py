from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, func

from app.core.database import Base


class CostRecord(Base):
    """成本记账模型，记录种植周期中的成本与收入。"""

    __tablename__ = "cost_records"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, nullable=True)
    record_type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    record_date = Column(Date, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
