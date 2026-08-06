"""add agent repair packs

Revision ID: 20260617_agent_repair_packs
Revises: 20260612_agent_data_flywheel_prelabels
Create Date: 2026-06-17 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260617_agent_repair_packs"
down_revision: Union[str, None] = "20260612_agent_data_flywheel_prelabels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "agent_repair_packs"
INDEX_COLUMNS = (
    "farm_id",
    "pack_id",
    "fix_target",
    "status",
    "created_by",
    "resolved_by",
    "resolved_at",
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
            sa.Column("pack_id", sa.String(length=80), nullable=False),
            sa.Column("fix_target", sa.String(length=40), nullable=False),
            sa.Column("labels", sa.JSON(), nullable=False),
            sa.Column("source_sample_ids", sa.JSON(), nullable=False),
            sa.Column("source_label_ids", sa.JSON(), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="draft",
            ),
            sa.Column("export_path", sa.Text(), nullable=True),
            sa.Column("manifest_json", sa.JSON(), nullable=True),
            sa.Column("export_error", sa.Text(), nullable=True),
            sa.Column("repair_note", sa.Text(), nullable=True),
            sa.Column("verification_summary", sa.JSON(), nullable=True),
            sa.Column("created_by", sa.String(length=64), nullable=True),
            sa.Column("resolved_by", sa.String(length=64), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
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
                unique=column_name == "pack_id",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if TABLE_NAME not in inspector.get_table_names():
        return

    op.drop_table(TABLE_NAME)
