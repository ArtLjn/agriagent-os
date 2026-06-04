"""stabilize labor source idempotency

Revision ID: e7b2c4d6f8a2
Revises: e7b2c4d6f8a1
Create Date: 2026-06-04 23:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision: str = "e7b2c4d6f8a2"
down_revision: Union[str, None] = "e7b2c4d6f8a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "labor_entries" in tables:
        columns = {column["name"] for column in inspector.get_columns("labor_entries")}
        if "client_request_id" not in columns:
            op.add_column(
                "labor_entries",
                sa.Column("client_request_id", sa.String(length=100), nullable=True),
            )

        indexes = {index["name"] for index in inspector.get_indexes("labor_entries")}
        if "ix_labor_entries_client_request_id" in indexes:
            op.drop_index("ix_labor_entries_client_request_id", table_name="labor_entries")
        if "uq_labor_entries_farm_client_request" not in indexes:
            bind.execute(
                text(
                    """
                    UPDATE labor_entries
                    SET client_request_id = NULL
                    WHERE client_request_id IS NOT NULL
                      AND id NOT IN (
                          SELECT kept_id
                          FROM (
                              SELECT MIN(id) AS kept_id
                              FROM labor_entries
                              WHERE client_request_id IS NOT NULL
                              GROUP BY farm_id, client_request_id
                          ) AS kept_labor_entries
                      )
                    """
                )
            )
            op.create_index(
                "uq_labor_entries_farm_client_request",
                "labor_entries",
                ["farm_id", "client_request_id"],
                unique=True,
            )

    if "cost_records" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("cost_records")}
    if "source_active_key" not in columns:
        op.add_column(
            "cost_records",
            sa.Column("source_active_key", sa.String(length=20), nullable=True),
        )

    bind.execute(
        text(
            """
            UPDATE cost_records
            SET source_active_key = 'active'
            WHERE deleted_at IS NULL
              AND source_type IS NOT NULL
              AND source_id IS NOT NULL
              AND source_active_key IS NULL
            """
        )
    )

    indexes = {index["name"] for index in inspector.get_indexes("cost_records")}
    if "uq_cost_records_active_source" not in indexes:
        op.create_index(
            "uq_cost_records_active_source",
            "cost_records",
            ["farm_id", "source_type", "source_id", "source_active_key"],
            unique=True,
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "cost_records" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("cost_records")}
        if "uq_cost_records_active_source" in indexes:
            op.drop_index("uq_cost_records_active_source", table_name="cost_records")

        columns = {column["name"] for column in inspector.get_columns("cost_records")}
        if "source_active_key" in columns:
            op.drop_column("cost_records", "source_active_key")

    if "labor_entries" not in tables:
        return

    indexes = {index["name"] for index in inspector.get_indexes("labor_entries")}
    if "uq_labor_entries_farm_client_request" in indexes:
        op.drop_index("uq_labor_entries_farm_client_request", table_name="labor_entries")

    columns = {column["name"] for column in inspector.get_columns("labor_entries")}
    if "client_request_id" in columns:
        op.drop_column("labor_entries", "client_request_id")
