"""种植批次单元、农事作业单和轻量用工模型。"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class PlantingUnit(Base):
    """批次下的棚、地块或区域。"""

    __tablename__ = "planting_units"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    cycle_id = Column(
        Integer,
        ForeignKey("crop_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    area_mu = Column(Numeric(10, 2), nullable=True)
    planted_date = Column(Date, nullable=True)
    status = Column(String(20), nullable=False, default="active")
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    cycle = relationship("CropCycle", back_populates="planting_units")
    work_order_links = relationship(
        "OperationWorkOrderUnit",
        back_populates="unit",
        cascade="all, delete-orphan",
    )


class OperationWorkOrder(Base):
    """农事作业单，支持批次级、种植单元级和农场级作业。"""

    __tablename__ = "operation_work_orders"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    cycle_id = Column(Integer, ForeignKey("crop_cycles.id"), nullable=True, index=True)
    operation_type = Column(String(50), nullable=False)
    operation_date = Column(Date, nullable=False, index=True)
    scope_type = Column(String(20), nullable=False, default="cycle")
    note = Column(String(500), nullable=True)
    photo_urls = Column(Text, nullable=True)
    source_type = Column(String(50), nullable=True)
    source_id = Column(Integer, nullable=True)
    labor_cost_record_id = Column(Integer, ForeignKey("cost_records.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    cycle = relationship("CropCycle", back_populates="work_orders")
    unit_links = relationship(
        "OperationWorkOrderUnit",
        back_populates="work_order",
        cascade="all, delete-orphan",
    )
    labor_entries = relationship(
        "LaborEntry",
        back_populates="work_order",
        cascade="all, delete-orphan",
    )
    labor_cost_record = relationship("CostRecord", foreign_keys=[labor_cost_record_id])


class OperationWorkOrderUnit(Base):
    """作业单与种植单元的作用范围关联。"""

    __tablename__ = "operation_work_order_units"
    __table_args__ = (
        UniqueConstraint(
            "work_order_id",
            "unit_id",
            name="uq_operation_work_order_units_order_unit",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    work_order_id = Column(
        Integer,
        ForeignKey("operation_work_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_id = Column(
        Integer,
        ForeignKey("planting_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    work_order = relationship("OperationWorkOrder", back_populates="unit_links")
    unit = relationship("PlantingUnit", back_populates="work_order_links")


class Worker(Base):
    """轻量工人档案。"""

    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(30), nullable=True)
    default_pay_type = Column(String(20), nullable=False, default="daily")
    default_unit_price = Column(Numeric(10, 2), nullable=True)
    note = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    labor_entries = relationship("LaborEntry", back_populates="worker")


class LaborEntry(Base):
    """作业单用工明细。"""

    __tablename__ = "labor_entries"
    __table_args__ = (
        UniqueConstraint(
            "farm_id",
            "client_request_id",
            name="uq_labor_entries_farm_client_request",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, index=True)
    work_order_id = Column(
        Integer,
        ForeignKey("operation_work_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, index=True)
    pay_type = Column(String(20), nullable=False, default="daily")
    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    payable_amount = Column(Numeric(10, 2), nullable=False)
    paid_amount = Column(Numeric(10, 2), nullable=False, default=0)
    unpaid_amount = Column(Numeric(10, 2), nullable=False, default=0)
    settlement_status = Column(String(20), nullable=False, default="unpaid")
    client_request_id = Column(String(100), nullable=True)
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    work_order = relationship("OperationWorkOrder", back_populates="labor_entries")
    worker = relationship("Worker", back_populates="labor_entries")
