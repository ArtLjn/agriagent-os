from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.shared.database import Base


class FarmLog(Base):
    """农事日志模型，记录作物周期中的各项农事操作。"""

    __tablename__ = "farm_logs"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
    cycle_id = Column(
        Integer,
        ForeignKey("crop_cycles.id", ondelete="CASCADE"),
        nullable=False,
    )
    operation_type = Column(String(50), nullable=False)
    operation_date = Column(Date, nullable=False)
    operation_time = Column(DateTime, nullable=True)
    note = Column(String(500), nullable=True)
    photo_urls = Column(String(2000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cycle = relationship("CropCycle", overlaps="farm_logs")
