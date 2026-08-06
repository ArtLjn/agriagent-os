"""SQLAlchemy ORM models for v2 business.

映射业务数据库全量表（与 archive 共用同一 MySQL 实例）：
  认证域: users / user_settings
  农场域: farms
  种植域: crop_templates / growth_stages / crop_cycles / cycle_stages /
          farm_logs / farm_log_workers / workers /
          planting_units / operation_work_orders / operation_work_order_units / labor_entries
  财务域: cost_categories / cost_records

字段与 archive/backend/app/domains/*/models.py 保持一致，便于直接复用 archive service 代码。
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Shared declarative base."""
    pass


# ─────────────────────────────────────────────────────────────
# 认证与用户域
# ─────────────────────────────────────────────────────────────


class User(Base):
    """用户模型，手机号 + 密码注册。"""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    nickname = Column(String(50), nullable=False, default="农友")
    avatar_url = Column(String(500), nullable=True)
    role = Column(String(20), nullable=False, default="user")
    status = Column(String(20), nullable=False, default="active")
    token_monthly_limit = Column(Integer, nullable=True)
    token_weekly_limit = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserSetting(Base):
    """用户设置，每个用户最多一条记录。"""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        String(36), ForeignKey("users.id"), unique=True, nullable=False, index=True
    )
    default_city = Column(String(50), nullable=True)
    default_lat = Column(Float, nullable=True)
    default_lon = Column(Float, nullable=True)
    assistant_role = Column(
        String(20), nullable=False, default="warm", server_default="warm"
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


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
    planting_units = relationship(
        "PlantingUnit", back_populates="cycle", cascade="all, delete-orphan"
    )
    work_orders = relationship("OperationWorkOrder", back_populates="cycle")


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
    labor_entries = relationship("LaborEntry", back_populates="worker")


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


# ─────────────────────────────────────────────────────────────
# 种植域 - 工单 / 种植单元 / 用工明细
# ─────────────────────────────────────────────────────────────


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
    labor_cost_record_id = Column(
        Integer, ForeignKey("cost_records.id"), nullable=True
    )
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
    labor_cost_record = relationship(
        "CostRecord", foreign_keys=[labor_cost_record_id]
    )


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


class LaborEntry(Base):
    """作业单用工明细（工时与工资记录）。"""

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


# ─────────────────────────────────────────────────────────────
# 财务域
# ─────────────────────────────────────────────────────────────


class CostCategory(Base):
    """成本分类模型，支持按农场隔离的类别管理。"""

    __tablename__ = "cost_categories"

    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"), nullable=False, default=1, index=True)
    name = Column(String(50), nullable=False)
    type = Column(String(10), nullable=False)  # cost 或 income
    icon = Column(String(50), nullable=False, default="tag")
    sort_order = Column(Integer, nullable=False, default=0)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


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
    record_type = Column(String(20), nullable=False)  # cost / income
    category = Column(String(50), nullable=False)
    category_id = Column(Integer, ForeignKey("cost_categories.id"), nullable=True)
    category_name_snapshot = Column(String(50), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    settled_amount = Column(Numeric(10, 2), nullable=False, default=0)
    settlement_status = Column(String(20), nullable=False, default="settled")
    record_date = Column(Date, nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=True)
    note = Column(String(500), nullable=True)
    record_subtype = Column(String(50), nullable=True)  # 赊账等
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
    def unsettled_amount(self):
        """返回尚未结算金额。"""
        from decimal import Decimal

        amount = Decimal(str(self.amount or 0)).quantize(Decimal("0.01"))
        settled = Decimal(str(self.settled_amount or 0)).quantize(Decimal("0.01"))
        return max(amount - settled, Decimal("0.00"))

    @property
    def source_label(self) -> str | None:
        """返回账单来源标识。"""
        if self.source_type == "operation_work_order":
            return "来自农事作业单"
        if self.source_type == "labor_entry":
            return "来自工资记录"
        return None
