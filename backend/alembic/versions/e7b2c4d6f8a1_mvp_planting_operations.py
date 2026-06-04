"""mvp planting operations

Revision ID: e7b2c4d6f8a1
Revises: d4a8b9c3e2f1
Create Date: 2026-06-04 21:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "e7b2c4d6f8a1"
down_revision: Union[str, None] = "d4a8b9c3e2f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    _add_crop_cycle_fields(inspector)
    _add_cost_source_fields(inspector)
    _create_planting_tables(inspector)
    _create_indexes(inspector)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    _drop_indexes(inspector)
    _drop_planting_tables(inspector)
    _drop_cost_source_fields(inspector)
    _drop_crop_cycle_fields(inspector)


def _columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _tables(inspector) -> set[str]:
    return set(inspector.get_table_names())


def _indexes(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _add_crop_cycle_fields(inspector) -> None:
    columns = _columns(inspector, "crop_cycles")
    if "total_area_mu" not in columns:
        op.add_column("crop_cycles", sa.Column("total_area_mu", sa.Numeric(10, 2), nullable=True))
    if "season" not in columns:
        op.add_column("crop_cycles", sa.Column("season", sa.String(length=50), nullable=True))
    if "batch_note" not in columns:
        op.add_column("crop_cycles", sa.Column("batch_note", sa.String(length=500), nullable=True))


def _drop_crop_cycle_fields(inspector) -> None:
    columns = _columns(inspector, "crop_cycles")
    for column_name in ["batch_note", "season", "total_area_mu"]:
        if column_name in columns:
            op.drop_column("crop_cycles", column_name)


def _add_cost_source_fields(inspector) -> None:
    columns = _columns(inspector, "cost_records")
    if "source_type" not in columns:
        op.add_column("cost_records", sa.Column("source_type", sa.String(length=50), nullable=True))
    if "source_id" not in columns:
        op.add_column("cost_records", sa.Column("source_id", sa.Integer(), nullable=True))


def _drop_cost_source_fields(inspector) -> None:
    columns = _columns(inspector, "cost_records")
    for column_name in ["source_id", "source_type"]:
        if column_name in columns:
            op.drop_column("cost_records", column_name)


def _create_planting_tables(inspector) -> None:
    tables = _tables(inspector)
    if "planting_units" not in tables:
        op.create_table(
            "planting_units",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("farm_id", sa.Integer(), nullable=False),
            sa.Column("cycle_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("area_mu", sa.Numeric(10, 2), nullable=True),
            sa.Column("planted_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("note", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["cycle_id"], ["crop_cycles.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if "operation_work_orders" not in tables:
        op.create_table(
            "operation_work_orders",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("farm_id", sa.Integer(), nullable=False),
            sa.Column("cycle_id", sa.Integer(), nullable=True),
            sa.Column("operation_type", sa.String(length=50), nullable=False),
            sa.Column("operation_date", sa.Date(), nullable=False),
            sa.Column("scope_type", sa.String(length=20), nullable=False, server_default="cycle"),
            sa.Column("note", sa.String(length=500), nullable=True),
            sa.Column("photo_urls", sa.Text(), nullable=True),
            sa.Column("source_type", sa.String(length=50), nullable=True),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("labor_cost_record_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["cycle_id"], ["crop_cycles.id"]),
            sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
            sa.ForeignKeyConstraint(["labor_cost_record_id"], ["cost_records.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if "operation_work_order_units" not in tables:
        op.create_table(
            "operation_work_order_units",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("work_order_id", sa.Integer(), nullable=False),
            sa.Column("unit_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["unit_id"], ["planting_units.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["work_order_id"], ["operation_work_orders.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "work_order_id",
                "unit_id",
                name="uq_operation_work_order_units_order_unit",
            ),
        )
    if "workers" not in tables:
        op.create_table(
            "workers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("farm_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("phone", sa.String(length=30), nullable=True),
            sa.Column("default_pay_type", sa.String(length=20), nullable=False, server_default="daily"),
            sa.Column("default_unit_price", sa.Numeric(10, 2), nullable=True),
            sa.Column("note", sa.String(length=500), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if "labor_entries" not in tables:
        op.create_table(
            "labor_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("farm_id", sa.Integer(), nullable=False),
            sa.Column("work_order_id", sa.Integer(), nullable=False),
            sa.Column("worker_id", sa.Integer(), nullable=False),
            sa.Column("pay_type", sa.String(length=20), nullable=False, server_default="daily"),
            sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
            sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
            sa.Column("payable_amount", sa.Numeric(10, 2), nullable=False),
            sa.Column("paid_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
            sa.Column("unpaid_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
            sa.Column("settlement_status", sa.String(length=20), nullable=False, server_default="unpaid"),
            sa.Column("note", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
            sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
            sa.ForeignKeyConstraint(["work_order_id"], ["operation_work_orders.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )


def _drop_planting_tables(inspector) -> None:
    tables = _tables(inspector)
    for table_name in [
        "labor_entries",
        "operation_work_order_units",
        "workers",
        "operation_work_orders",
        "planting_units",
    ]:
        if table_name in tables:
            op.drop_table(table_name)


def _create_indexes(inspector) -> None:
    index_specs = [
        ("cost_records", "ix_cost_records_source", ["source_type", "source_id"]),
        ("planting_units", "ix_planting_units_farm_cycle", ["farm_id", "cycle_id"]),
        ("operation_work_orders", "ix_work_orders_farm_date", ["farm_id", "operation_date"]),
        ("operation_work_orders", "ix_work_orders_farm_cycle_date", ["farm_id", "cycle_id", "operation_date"]),
        ("operation_work_order_units", "ix_work_order_units_unit", ["unit_id"]),
        ("workers", "ix_workers_farm_status", ["farm_id", "status"]),
        ("labor_entries", "ix_labor_entries_farm_status", ["farm_id", "settlement_status"]),
        ("labor_entries", "ix_labor_entries_work_order", ["work_order_id"]),
    ]
    for table_name, index_name, columns in index_specs:
        if table_name in _tables(inspector) and index_name not in _indexes(inspector, table_name):
            op.create_index(index_name, table_name, columns, unique=False)


def _drop_indexes(inspector) -> None:
    for table_name, index_name in [
        ("labor_entries", "ix_labor_entries_work_order"),
        ("labor_entries", "ix_labor_entries_farm_status"),
        ("workers", "ix_workers_farm_status"),
        ("operation_work_order_units", "ix_work_order_units_unit"),
        ("operation_work_orders", "ix_work_orders_farm_cycle_date"),
        ("operation_work_orders", "ix_work_orders_farm_date"),
        ("planting_units", "ix_planting_units_farm_cycle"),
        ("cost_records", "ix_cost_records_source"),
    ]:
        if table_name in _tables(inspector) and index_name in _indexes(inspector, table_name):
            op.drop_index(index_name, table_name=table_name)
