"""add cost recorded_at

Revision ID: f2c9a8e1d4b7
Revises: e7b2c4d6f8a3
Create Date: 2026-06-08 17:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision: str = "f2c9a8e1d4b7"
down_revision: Union[str, None] = "e7b2c4d6f8a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "cost_records" not in set(inspector.get_table_names()):
        return

    columns = {column["name"] for column in inspector.get_columns("cost_records")}
    if "recorded_at" not in columns:
        op.add_column(
            "cost_records",
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        )

    bind.execute(
        text(
            """
            UPDATE cost_records
            SET recorded_at = COALESCE(created_at, record_date)
            WHERE recorded_at IS NULL
            """
        )
    )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "cost_records" not in set(inspector.get_table_names()):
        return

    columns = {column["name"] for column in inspector.get_columns("cost_records")}
    if "recorded_at" in columns:
        op.drop_column("cost_records", "recorded_at")
