from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
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
    work_order_id = Column(
        Integer,
        ForeignKey("operation_work_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    operation_type = Column(String(50), nullable=False)
    operation_date = Column(Date, nullable=False)
    operation_time = Column(DateTime, nullable=True)
    note = Column(String(500), nullable=True)
    photo_urls = Column(String(2000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    cycle = relationship("CropCycle", overlaps="farm_logs")
    work_order = relationship("OperationWorkOrder")
    worker_links = relationship(
        "FarmLogWorker",
        back_populates="farm_log",
        cascade="all, delete-orphan",
    )

    @property
    def worker_ids(self) -> list[int]:
        return [link.worker_id for link in self.worker_links]

    @property
    def worker_names(self) -> list[str]:
        return [
            link.worker.name
            for link in self.worker_links
            if link.worker and link.worker.name
        ]


class FarmLogWorker(Base):
    """农事日志参与人，仅用于追溯，不作为工资主账。"""

    __tablename__ = "farm_log_workers"
    __table_args__ = (
        UniqueConstraint(
            "farm_log_id",
            "worker_id",
            name="uq_farm_log_workers_log_worker",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    farm_log_id = Column(
        Integer,
        ForeignKey("farm_logs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, index=True)
    role = Column(String(50), nullable=True)
    note = Column(String(500), nullable=True)

    farm_log = relationship("FarmLog", back_populates="worker_links")
    worker = relationship("Worker", back_populates="farm_log_links")
