"""add farm log worker links

Revision ID: 20260728_farm_log_worker_links
Revises: f2c9a8e1d4b7
Create Date: 2026-07-28 11:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260728_farm_log_worker_links"
down_revision: Union[str, None] = "f2c9a8e1d4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "farm_logs" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("farm_logs")}
    if "work_order_id" not in columns:
        op.add_column(
            "farm_logs",
            sa.Column("work_order_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_farm_logs_work_order_id",
            "farm_logs",
            "operation_work_orders",
            ["work_order_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_farm_logs_work_order_id",
            "farm_logs",
            ["work_order_id"],
            unique=False,
        )

    if "farm_log_workers" not in tables:
        op.create_table(
            "farm_log_workers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("farm_log_id", sa.Integer(), nullable=False),
            sa.Column("worker_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=50), nullable=True),
            sa.Column("note", sa.String(length=500), nullable=True),
            sa.ForeignKeyConstraint(
                ["farm_log_id"], ["farm_logs.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "farm_log_id",
                "worker_id",
                name="uq_farm_log_workers_log_worker",
            ),
        )
        op.create_index(
            "ix_farm_log_workers_farm_log_id",
            "farm_log_workers",
            ["farm_log_id"],
            unique=False,
        )
        op.create_index(
            "ix_farm_log_workers_worker_id",
            "farm_log_workers",
            ["worker_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "farm_log_workers" in tables:
        op.drop_index(
            "ix_farm_log_workers_worker_id",
            table_name="farm_log_workers",
        )
        op.drop_index(
            "ix_farm_log_workers_farm_log_id",
            table_name="farm_log_workers",
        )
        op.drop_table("farm_log_workers")

    if "farm_logs" not in tables:
        return
    columns = {column["name"] for column in inspector.get_columns("farm_logs")}
    indexes = {index["name"] for index in inspector.get_indexes("farm_logs")}
    if "ix_farm_logs_work_order_id" in indexes:
        op.drop_index("ix_farm_logs_work_order_id", table_name="farm_logs")
    if "work_order_id" in columns:
        op.drop_constraint(
            "fk_farm_logs_work_order_id",
            "farm_logs",
            type_="foreignkey",
        )
        op.drop_column("farm_logs", "work_order_id")
