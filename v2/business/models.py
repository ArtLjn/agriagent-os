"""SQLAlchemy ORM models for v2 business MVP.

只映射 v2 当前 skill 真正用到的 6 张表（与 archive 共用同一 MySQL 实例）：
  farms / crop_templates / crop_cycles / farm_logs / farm_log_workers / workers

不重复定义 archive 已有的字段（参考 archive/backend/app/domains/）。新增 skill
需要更多表时再补对应 model，避免一次定义 30 张表大部分用不上。
"""
from __future__ import annotations

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
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Shared declarative base."""
    pass


class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True)
    uid = Column(String(36), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=True)
    user_id = Column(String(36), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now())


class CropTemplate(Base):
    __tablename__ = "crop_templates"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=True)
    name = Column(String(100), nullable=False)
    variety = Column(String(100), nullable=True)
    category = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    growth_stages = relationship(
        "GrowthStage", back_populates="crop_template", cascade="all, delete-orphan"
    )


class GrowthStage(Base):
    """作物模板的标准生长阶段（不是 cycle_stages，cycle_stages 是某个茬口实例的具体阶段）。"""

    __tablename__ = "growth_stages"

    id = Column(Integer, primary_key=True, index=True)
    crop_template_id = Column(
        Integer, ForeignKey("crop_templates.id"), nullable=False
    )
    name = Column(String(100), nullable=False)
    duration_days = Column(Integer, nullable=False)
    order_index = Column(Integer, nullable=False)
    key_tasks = Column(String(500), nullable=True)

    crop_template = relationship("CropTemplate", back_populates="growth_stages")


class CropCycle(Base):
    __tablename__ = "crop_cycles"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    name = Column(String(100), nullable=False)
    crop_template_id = Column(
        Integer, ForeignKey("crop_templates.id", ondelete="RESTRICT"), nullable=False
    )
    start_date = Column(Date, nullable=False)
    field_name = Column(String(100), nullable=True)
    total_area_mu = Column(Numeric(10, 2), nullable=True)
    season = Column(String(50), nullable=True)
    batch_note = Column(String(500), nullable=True)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, server_default=func.now())

    crop_template = relationship("CropTemplate")
    stages = relationship(
        "CycleStage", back_populates="cycle", cascade="all, delete-orphan"
    )
    farm_logs = relationship("FarmLog", cascade="all, delete-orphan")


class CycleStage(Base):
    """茬口实例的具体阶段（与 growth_stages 区分）。"""

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


class Worker(Base):
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(30), nullable=True)
    default_pay_type = Column(String(20), nullable=False, default="daily")
    default_unit_price = Column(Numeric(10, 2), nullable=True)
    note = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    farm_log_links = relationship("FarmLogWorker", back_populates="worker")


class FarmLog(Base):
    __tablename__ = "farm_logs"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False)
    cycle_id = Column(
        Integer, ForeignKey("crop_cycles.id", ondelete="CASCADE"), nullable=False
    )
    operation_type = Column(String(50), nullable=False)
    operation_date = Column(Date, nullable=False)
    operation_time = Column(DateTime, nullable=True)
    note = Column(String(500), nullable=True)
    photo_urls = Column(String(2000), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    cycle = relationship("CropCycle", overlaps="farm_logs")
    worker_links = relationship(
        "FarmLogWorker",
        back_populates="farm_log",
        cascade="all, delete-orphan",
    )

    @property
    def worker_names(self) -> list[str]:
        return [
            link.worker.name
            for link in self.worker_links
            if link.worker and link.worker.name
        ]


class FarmLogWorker(Base):
    __tablename__ = "farm_log_workers"
    __table_args__ = (
        UniqueConstraint(
            "farm_log_id", "worker_id", name="uq_farm_log_workers_log_worker"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    farm_log_id = Column(
        Integer, ForeignKey("farm_logs.id", ondelete="CASCADE"), nullable=False
    )
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False)
    role = Column(String(50), nullable=True)
    note = Column(String(500), nullable=True)

    farm_log = relationship("FarmLog", back_populates="worker_links")
    worker = relationship("Worker", back_populates="farm_log_links")
