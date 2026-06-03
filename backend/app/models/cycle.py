from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class CropCycle(Base):
    """茬口模型，代表一次具体的种植周期。"""

    __tablename__ = "crop_cycles"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1)
    name = Column(String(100), nullable=False)
    crop_template_id = Column(
        Integer,
        ForeignKey("crop_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_date = Column(Date, nullable=False)
    field_name = Column(String(100), nullable=True)
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    crop_template = relationship("CropTemplate")
    stages = relationship(
        "CycleStage", back_populates="cycle", cascade="all, delete-orphan"
    )
    farm_logs = relationship("FarmLog", cascade="all, delete-orphan")


class CycleStage(Base):
    """茬口阶段模型，代表某个茬口下的具体生长阶段。"""

    __tablename__ = "cycle_stages"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=False)
    name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    order_index = Column(Integer, nullable=False)
    duration_days = Column(Integer, nullable=False)
    key_tasks = Column(String(500), nullable=True)
    is_current = Column(Integer, default=0)

    cycle = relationship("CropCycle", back_populates="stages")
