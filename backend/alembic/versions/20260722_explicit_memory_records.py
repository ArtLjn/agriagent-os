"""add explicit memory records

Revision ID: 20260722_explicit_memory_records
Revises: 20260722_agent_task_states
Create Date: 2026-07-22 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260722_explicit_memory_records"
down_revision: Union[str, None] = "20260722_agent_task_states"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "memory_records" in set(inspector.get_table_names()):
        return

    op.create_table(
        "memory_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("memory_id", sa.String(length=64), nullable=False),
        sa.Column("farm_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="confirmed",
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="user_explicit",
        ),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("superseded_by_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("memory_id", name="uq_memory_records_memory_id"),
    )
    op.create_index("ix_memory_records_memory_id", "memory_records", ["memory_id"])
    op.create_index("ix_memory_records_farm_id", "memory_records", ["farm_id"])
    op.create_index("ix_memory_records_user_id", "memory_records", ["user_id"])
    op.create_index("ix_memory_records_type", "memory_records", ["type"])
    op.create_index("ix_memory_records_status", "memory_records", ["status"])
    op.create_index("ix_memory_records_source", "memory_records", ["source"])
    op.create_index(
        "ix_memory_records_context_lookup",
        "memory_records",
        ["farm_id", "user_id", "status", "importance", "updated_at"],
    )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "memory_records" not in set(inspector.get_table_names()):
        return

    op.drop_index("ix_memory_records_context_lookup", table_name="memory_records")
    op.drop_index("ix_memory_records_source", table_name="memory_records")
    op.drop_index("ix_memory_records_status", table_name="memory_records")
    op.drop_index("ix_memory_records_type", table_name="memory_records")
    op.drop_index("ix_memory_records_user_id", table_name="memory_records")
    op.drop_index("ix_memory_records_farm_id", table_name="memory_records")
    op.drop_index("ix_memory_records_memory_id", table_name="memory_records")
    op.drop_table("memory_records")
