"""add data flywheel prelabels

Revision ID: 20260612_agent_data_flywheel_prelabels
Revises: 20260612_add_user_assistant_role
Create Date: 2026-06-12 11:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260612_agent_data_flywheel_prelabels"
down_revision: Union[str, None] = "20260612_add_user_assistant_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "agent_data_flywheel_prelabels"
INDEX_COLUMNS = (
    "farm_id",
    "sample_id",
    "sample_type",
    "session_id",
    "turn_id",
    "request_id",
    "source",
    "status",
    "severity",
    "judge_model",
    "prompt_version",
    "reviewed_by",
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
            sa.Column("sample_id", sa.String(length=160), nullable=False),
            sa.Column("sample_type", sa.String(length=40), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=True),
            sa.Column("turn_id", sa.Integer(), nullable=True),
            sa.Column("request_id", sa.String(length=32), nullable=True),
            sa.Column(
                "source",
                sa.String(length=32),
                nullable=False,
                server_default="llm_judge",
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("labels", sa.JSON(), nullable=False),
            sa.Column("root_cause", sa.Text(), nullable=True),
            sa.Column("severity", sa.String(length=20), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("recommended_fix", sa.Text(), nullable=True),
            sa.Column("judge_model", sa.String(length=80), nullable=False),
            sa.Column("prompt_version", sa.String(length=80), nullable=False),
            sa.Column("raw_response", sa.JSON(), nullable=True),
            sa.Column("accepted_label_ids", sa.JSON(), nullable=True),
            sa.Column("reviewed_by", sa.String(length=64), nullable=True),
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
            op.create_index(index_name, TABLE_NAME, [column_name])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return

    op.drop_table(TABLE_NAME)
