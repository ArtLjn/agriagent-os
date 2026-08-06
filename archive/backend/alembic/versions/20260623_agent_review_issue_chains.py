"""add agent review issue chains

Revision ID: 20260623_agent_review_issue_chains
Revises: 20260620_agent_repair_packs_dedup_key
Create Date: 2026-06-23 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260623_agent_review_issue_chains"
down_revision: Union[str, None] = "20260620_agent_repair_packs_dedup_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "agent_review_issue_chains"
INDEX_COLUMNS = (
    "farm_id",
    "chain_id",
    "session_id",
    "trigger_turn_id",
    "status",
    "severity",
    "dominant_signal",
    "reviewer_id",
    "reviewed_at",
    "created_at",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("farm_id", sa.Integer(), nullable=False),
            sa.Column("chain_id", sa.String(length=160), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("trigger_turn_id", sa.Integer(), nullable=False),
            sa.Column("context_turn_ids", sa.JSON(), nullable=False),
            sa.Column("result_turn_ids", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("severity", sa.String(length=20), nullable=False),
            sa.Column("dominant_signal", sa.String(length=32), nullable=False),
            sa.Column("final_labels", sa.JSON(), nullable=False),
            sa.Column("source_label_ids", sa.JSON(), nullable=False),
            sa.Column("root_cause", sa.Text(), nullable=True),
            sa.Column("expected_behavior", sa.Text(), nullable=True),
            sa.Column("false_positive_reason", sa.Text(), nullable=True),
            sa.Column("missing_evidence", sa.JSON(), nullable=True),
            sa.Column("reviewer_id", sa.String(length=64), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["farm_id"], ["farms.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    for column_name in INDEX_COLUMNS:
        index_name = f"ix_{TABLE_NAME}_{column_name}"
        if index_name not in indexes:
            op.create_index(
                index_name,
                TABLE_NAME,
                [column_name],
                unique=column_name == "chain_id",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return

    op.drop_table(TABLE_NAME)
